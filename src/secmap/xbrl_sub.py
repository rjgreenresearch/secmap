"""
xbrl_sub.py

Parses the SEC Financial Statement and Notes Data Sets SUB (Submissions)
table for entity metadata: CIK, name, SIC, country of business/incorporation,
co-registrant CIKs, EIN, former names, and filing metadata.

Data source: SEC EDGAR AQFSN monthly/quarterly archives.
  - Monthly: data/SEC/aqfsn/YYYY_MM_notes/sub.tsv
  - Quarterly ZIP: 2024q4.zip containing sub.txt (tab-delimited)

The SUB table has 40 tab-delimited columns per the notes-metadata.json schema:
  adsh, cik, name, sic, countryba, stprba, cityba, zipba, bas1, bas2, baph,
  countryma, stprma, cityma, zipma, mas1, mas2, countryinc, stprinc, ein,
  former, changed, afs, wksi, fye, form, period, fy, fp, filed, accepted,
  prevrpt, detail, instance, nciks, aciks, pubfloatusd, floatdate, floataxis,
  floatmems

Usage:
    from secmap.xbrl_sub import XBRLSubIndex

    idx = XBRLSubIndex()
    idx.load_directory("data/SEC/aqfsn/2025_01_notes")
    idx.load_all_months("data/SEC/aqfsn")

    subs = idx.by_cik("91388")
    cn_subs = idx.by_country("CN")
    ag_subs = idx.by_sic("0100", prefix=True)
    results = idx.search("smithfield")
    co_regs = idx.co_registrants("1091667")
"""

from __future__ import annotations

import csv
import io
import logging
import os
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Column names from notes-metadata.json (40 columns, 0-indexed)
SUB_COLUMNS = [
    "adsh", "cik", "name", "sic", "countryba", "stprba", "cityba", "zipba",
    "bas1", "bas2", "baph", "countryma", "stprma", "cityma", "zipma",
    "mas1", "mas2", "countryinc", "stprinc", "ein", "former", "changed",
    "afs", "wksi", "fye", "form", "period", "fy", "fp", "filed",
    "accepted", "prevrpt", "detail", "instance", "nciks", "aciks",
    "pubfloatusd", "floatdate", "floataxis", "floatmems",
]

COL_IDX = {name: i for i, name in enumerate(SUB_COLUMNS)}


@dataclass
class SubRecord:
    """A single row from the SUB table."""
    adsh: str
    cik: str
    name: str
    sic: str
    countryba: str
    stprba: str
    cityba: str
    countryma: str
    countryinc: str
    stprinc: str
    ein: str
    former: str
    changed: str
    form: str
    period: str
    filed: str
    nciks: int
    aciks: str  # space-delimited additional CIKs
    source_period: str = ""  # e.g. "2025_01" — which monthly dataset

    @staticmethod
    def from_row(fields: List[str], source_period: str = "") -> Optional[SubRecord]:
        """Parse a tab-split row into a SubRecord. Returns None on bad data."""
        if len(fields) < 36:
            return None
        cik = fields[COL_IDX["cik"]].strip()
        if not cik:
            return None
        try:
            nciks = int(fields[COL_IDX["nciks"]].strip() or "0")
        except ValueError:
            nciks = 0
        return SubRecord(
            adsh=fields[COL_IDX["adsh"]].strip(),
            cik=cik,
            name=fields[COL_IDX["name"]].strip(),
            sic=fields[COL_IDX["sic"]].strip(),
            countryba=fields[COL_IDX["countryba"]].strip(),
            stprba=fields[COL_IDX["stprba"]].strip(),
            cityba=fields[COL_IDX["cityba"]].strip(),
            countryma=fields[COL_IDX["countryma"]].strip(),
            countryinc=fields[COL_IDX["countryinc"]].strip(),
            stprinc=fields[COL_IDX["stprinc"]].strip(),
            ein=fields[COL_IDX["ein"]].strip(),
            former=fields[COL_IDX["former"]].strip(),
            changed=fields[COL_IDX["changed"]].strip(),
            form=fields[COL_IDX["form"]].strip(),
            period=fields[COL_IDX["period"]].strip(),
            filed=fields[COL_IDX["filed"]].strip(),
            nciks=nciks,
            aciks=fields[COL_IDX["aciks"]].strip(),
            source_period=source_period,
        )


@dataclass
class XBRLSubIndex:
    """
    In-memory index of SEC AQFSN SUB table records, indexed by CIK
    for fast lookup. Supports loading from extracted directories or
    ZIP archives, and deduplicates by accession number across quarters.
    """
    _by_cik: Dict[str, List[SubRecord]] = field(default_factory=lambda: defaultdict(list))
    _by_adsh: Dict[str, SubRecord] = field(default_factory=dict)
    _loaded_periods: Set[str] = field(default_factory=set)
    _total_rows: int = 0

    # -----------------------------------------------------------------
    # Loading
    # -----------------------------------------------------------------

    def load_directory(self, dir_path: str) -> int:
        """Load sub.tsv (or sub.txt) from an extracted monthly/quarterly directory."""
        for fname in ("sub.tsv", "sub.txt"):
            path = os.path.join(dir_path, fname)
            if os.path.exists(path):
                period = os.path.basename(dir_path).replace("_notes", "")
                return self._load_file(path, period)
        logger.warning("No sub.tsv or sub.txt in %s", dir_path)
        return 0

    def load_zip(self, zip_path: str) -> int:
        """Load sub.tsv/sub.txt from a ZIP archive."""
        period = os.path.splitext(os.path.basename(zip_path))[0].replace("_notes", "")
        if period in self._loaded_periods:
            logger.debug("Period %s already loaded, skipping", period)
            return 0
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                for name in ("sub.tsv", "sub.txt"):
                    if name in zf.namelist():
                        with zf.open(name) as f:
                            text = io.TextIOWrapper(f, encoding="utf-8", errors="replace")
                            return self._ingest_lines(text, period)
        except Exception as e:
            logger.error("Failed to read ZIP %s: %s", zip_path, e)
        return 0

    def load_all_months(self, base_dir: str) -> int:
        """Load all monthly directories and ZIPs under a base directory."""
        total = 0
        if not os.path.isdir(base_dir):
            logger.error("Directory not found: %s", base_dir)
            return 0

        # Prefer extracted directories over ZIPs (faster, no decompression)
        entries = sorted(os.listdir(base_dir))
        for entry in entries:
            full = os.path.join(base_dir, entry)
            if os.path.isdir(full) and ("_notes" in entry or entry.endswith("q1") or entry.endswith("q2") or entry.endswith("q3") or entry.endswith("q4")):
                total += self.load_directory(full)
            elif entry.endswith(".zip"):
                total += self.load_zip(full)

        logger.info(
            "Loaded %d total records across %d periods, %d unique CIKs",
            self._total_rows, len(self._loaded_periods), len(self._by_cik),
        )
        return total

    def _load_file(self, path: str, period: str) -> int:
        if period in self._loaded_periods:
            logger.debug("Period %s already loaded, skipping", period)
            return 0
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return self._ingest_lines(f, period)
        except Exception as e:
            logger.error("Failed to read %s: %s", path, e)
            return 0

    def _ingest_lines(self, lines, period: str) -> int:
        count = 0
        first_line = True
        self._loaded_periods.add(period)
        for line in lines:
            line = line.rstrip("\n\r")
            if not line:
                continue
            # Skip header row (first line starting with "adsh")
            if first_line:
                first_line = False
                if line.startswith("adsh"):
                    continue
            fields = line.split("\t")
            rec = SubRecord.from_row(fields, source_period=period)
            if rec is None:
                continue
            # Deduplicate by accession number
            if rec.adsh in self._by_adsh:
                continue
            self._by_adsh[rec.adsh] = rec
            self._by_cik[rec.cik].append(rec)
            count += 1
        self._total_rows += count
        logger.info("Loaded %d records from period %s", count, period)
        return count

    # -----------------------------------------------------------------
    # Query methods
    # -----------------------------------------------------------------

    def by_cik(self, cik: str) -> List[SubRecord]:
        """All submissions for a given CIK."""
        return self._by_cik.get(cik.strip(), [])

    def by_country(self, country_code: str) -> List[SubRecord]:
        """All submissions with business address in the given country."""
        cc = country_code.upper()
        return [r for recs in self._by_cik.values() for r in recs if r.countryba == cc]

    def by_country_inc(self, country_code: str) -> List[SubRecord]:
        """All entities incorporated in the given country."""
        cc = country_code.upper()
        return [r for recs in self._by_cik.values() for r in recs if r.countryinc == cc]

    def by_sic(self, sic_code: str, prefix: bool = False) -> List[SubRecord]:
        """All submissions matching a SIC code. If prefix=True, matches the leading digits."""
        if prefix:
            return [r for recs in self._by_cik.values() for r in recs if r.sic.startswith(sic_code)]
        return [r for recs in self._by_cik.values() for r in recs if r.sic == sic_code]

    def by_form(self, form_type: str) -> List[SubRecord]:
        """All submissions of a given form type (e.g. '10-K', '20-F')."""
        ft = form_type.upper()
        return [r for recs in self._by_cik.values() for r in recs if r.form.upper() == ft]

    def co_registrants(self, cik: str) -> List[str]:
        """Parse aciks field to find subsidiary/co-registrant CIKs for a given CIK."""
        ciks = set()
        for rec in self.by_cik(cik):
            if rec.aciks:
                for c in rec.aciks.split():
                    c = c.strip()
                    if c and c != cik:
                        ciks.add(c)
        return sorted(ciks)

    def search(self, name_pattern: str) -> List[SubRecord]:
        """Case-insensitive name search across all submissions. Returns deduplicated by CIK (most recent filing)."""
        q = name_pattern.lower()
        seen_ciks: Dict[str, SubRecord] = {}
        for recs in self._by_cik.values():
            for r in recs:
                if q in r.name.lower() or (r.former and q in r.former.lower()):
                    if r.cik not in seen_ciks or r.filed > seen_ciks[r.cik].filed:
                        seen_ciks[r.cik] = r
        return sorted(seen_ciks.values(), key=lambda r: r.name)

    def unique_ciks(self) -> Set[str]:
        """All unique CIKs in the index."""
        return set(self._by_cik.keys())

    def stats(self) -> Dict[str, int]:
        """Summary statistics."""
        countries = set()
        sics = set()
        forms = set()
        for recs in self._by_cik.values():
            for r in recs:
                if r.countryba:
                    countries.add(r.countryba)
                if r.sic:
                    sics.add(r.sic)
                if r.form:
                    forms.add(r.form)
        return {
            "total_records": self._total_rows,
            "unique_ciks": len(self._by_cik),
            "unique_accessions": len(self._by_adsh),
            "periods_loaded": len(self._loaded_periods),
            "unique_countries": len(countries),
            "unique_sic_codes": len(sics),
            "unique_form_types": len(forms),
        }


# ---------------------------------------------------------------------------
# Standalone testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    data_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join("data", "SEC", "aqfsn")

    idx = XBRLSubIndex()
    idx.load_all_months(data_dir)

    s = idx.stats()
    print(f"\n{'='*60}")
    print(f"XBRL SUB Index Summary")
    print(f"{'='*60}")
    for k, v in s.items():
        print(f"  {k:30s}: {v:,}")

    # Sample queries
    print(f"\n--- China-based entities (countryba=CN) ---")
    cn = idx.by_country("CN")
    print(f"  {len(cn)} submissions")
    for r in cn[:5]:
        print(f"    CIK {r.cik}: {r.name} (SIC {r.sic}, form {r.form}, filed {r.filed})")

    print(f"\n--- Cayman Islands incorporated (countryinc=KY) ---")
    ky = idx.by_country_inc("KY")
    print(f"  {len(ky)} submissions")
    for r in ky[:5]:
        print(f"    CIK {r.cik}: {r.name} (countryba={r.countryba})")

    print(f"\n--- Agriculture SIC 01xx ---")
    ag = idx.by_sic("01", prefix=True)
    print(f"  {len(ag)} submissions")
    for r in ag[:5]:
        print(f"    CIK {r.cik}: {r.name} (SIC {r.sic})")

    print(f"\n--- Co-registrants for Charter Communications (CIK 1091667) ---")
    co = idx.co_registrants("1091667")
    print(f"  {len(co)} co-registrant CIKs: {co}")

    print(f"\n--- Search 'smithfield' ---")
    hits = idx.search("smithfield")
    for r in hits:
        print(f"    CIK {r.cik}: {r.name} (form {r.form}, filed {r.filed})")
