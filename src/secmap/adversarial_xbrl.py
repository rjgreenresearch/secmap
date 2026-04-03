"""
adversarial_xbrl.py

Deterministic adversarial-nation entity identification using structured
ISO 3166-1 country codes from the SEC XBRL SUB table.

Unlike adversarial_search.py (which uses fuzzy name matching against the
SEC company tickers endpoint), this module uses the three country fields
in the SUB table -- countryba, countryinc, countryma -- to identify entities
with zero false positives.

The three-field approach catches intermediary patterns invisible to
single-field analysis:
  - Incorporated in CN but business address in US (PRC-controlled US entity)
  - Business address in US but mailing address in HK (conduit routing)
  - Incorporated in KY but business address in CN (offshore PRC shell)

Risk tiers follow jurisdiction_inference.py:
  ADVERSARIAL: CN, RU, IR, KP, BY, MM, CU, VE, SY, NI
  CONDUIT:     HK, SG, AE, KY, VG, BM, PA, CY

Usage:
    from secmap.xbrl_sub import XBRLSubIndex
    from secmap.adversarial_xbrl import adversarial_scan

    idx = XBRLSubIndex()
    idx.load_all_months("data/SEC/aqfsn")

    result = adversarial_scan(idx, include_conduit=True)
    print(result.summary_table())
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from .xbrl_sub import SubRecord, XBRLSubIndex

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Country code classifications (ISO 3166-1 alpha-2)
# ---------------------------------------------------------------------------

ADVERSARIAL_CODES: Dict[str, str] = {
    "CN": "China",
    "RU": "Russia",
    "IR": "Iran",
    "KP": "North Korea",
    "BY": "Belarus",
    "MM": "Myanmar",
    "CU": "Cuba",
    "VE": "Venezuela",
    "SY": "Syria",
    "NI": "Nicaragua",
}

CONDUIT_CODES: Dict[str, str] = {
    "HK": "Hong Kong",
    "SG": "Singapore",
    "AE": "United Arab Emirates",
    "KY": "Cayman Islands",
    "VG": "British Virgin Islands",
    "BM": "Bermuda",
    "PA": "Panama",
    "CY": "Cyprus",
}

FIELD_NAMES = {
    "countryba": "Business Address",
    "countryinc": "Incorporation",
    "countryma": "Mailing Address",
}


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MatchedEntity:
    """A single CIK matched by adversarial/conduit country codes."""
    cik: str
    name: str
    sic: str
    countryba: str
    countryinc: str
    countryma: str
    matched_fields: FrozenSet[str]  # {"countryba", "countryinc", "countryma"}
    matched_codes: FrozenSet[str]   # {"CN", "HK", ...}
    matched_tier: str               # "ADVERSARIAL" or "CONDUIT"
    forms: Tuple[str, ...]          # all filing form types
    filing_dates: Tuple[str, ...]   # all filing dates
    former_name: str = ""


@dataclass
class AdversarialScanResult:
    """Complete result of an adversarial XBRL scan."""
    entities: List[MatchedEntity]
    include_conduit: bool
    total_ciks_scanned: int
    periods_loaded: int

    # --- pre-computed analytics ---
    by_country: Dict[str, List[MatchedEntity]] = field(default_factory=dict)
    by_field: Dict[str, List[MatchedEntity]] = field(default_factory=dict)
    intermediary_patterns: List[MatchedEntity] = field(default_factory=list)

    def summary_table(self) -> str:
        """Generate a markdown summary table suitable for academic citation."""
        lines = []
        lines.append("# Adversarial-Nation XBRL Entity Scan")
        lines.append("")
        lines.append("## Method")
        lines.append("")
        lines.append("Deterministic identification using ISO 3166-1 country codes from the")
        lines.append("SEC XBRL Financial Statement and Notes Data Sets SUB table.")
        lines.append(f"Three fields scanned: countryba (business address), countryinc (incorporation), countryma (mailing address).")
        lines.append(f"Zero false positives -- matched on structured country codes, not entity names.")
        lines.append("")

        # Overview
        lines.append("## Overview")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|---|---|")
        lines.append(f"| Total CIKs scanned | {self.total_ciks_scanned:,} |")
        lines.append(f"| Periods loaded | {self.periods_loaded} |")
        lines.append(f"| Unique adversarial CIKs | {len([e for e in self.entities if e.matched_tier == 'ADVERSARIAL']):,} |")
        if self.include_conduit:
            lines.append(f"| Unique conduit CIKs | {len([e for e in self.entities if e.matched_tier == 'CONDUIT']):,} |")
        lines.append(f"| **Total matched CIKs** | **{len(self.entities):,}** |")
        lines.append("")

        # By country
        lines.append("## Unique CIKs by Country")
        lines.append("")
        lines.append("| Code | Country | Tier | Unique CIKs |")
        lines.append("|---|---|---|---|")
        for code in sorted(self.by_country.keys(), key=lambda c: (-len(self.by_country[c]), c)):
            entities = self.by_country[code]
            name = ADVERSARIAL_CODES.get(code, CONDUIT_CODES.get(code, code))
            tier = "ADVERSARIAL" if code in ADVERSARIAL_CODES else "CONDUIT"
            lines.append(f"| {code} | {name} | {tier} | {len(entities):,} |")
        lines.append("")

        # By field
        lines.append("## Matches by Country Field")
        lines.append("")
        lines.append("| Field | Description | Unique CIKs |")
        lines.append("|---|---|---|")
        for fld in ("countryba", "countryinc", "countryma"):
            desc = FIELD_NAMES[fld]
            count = len(self.by_field.get(fld, []))
            lines.append(f"| {fld} | {desc} | {count:,} |")
        lines.append("")

        # By country × field breakdown
        lines.append("## Country x Field Breakdown")
        lines.append("")
        lines.append("| Country | Business Addr | Incorporation | Mailing Addr |")
        lines.append("|---|---|---|---|")
        all_codes = sorted(self.by_country.keys(), key=lambda c: (-len(self.by_country[c]), c))
        for code in all_codes:
            name = ADVERSARIAL_CODES.get(code, CONDUIT_CODES.get(code, code))
            ba = sum(1 for e in self.by_country[code] if "countryba" in e.matched_fields)
            inc = sum(1 for e in self.by_country[code] if "countryinc" in e.matched_fields)
            ma = sum(1 for e in self.by_country[code] if "countryma" in e.matched_fields)
            lines.append(f"| {name} ({code}) | {ba:,} | {inc:,} | {ma:,} |")
        lines.append("")

        # Intermediary patterns
        if self.intermediary_patterns:
            lines.append("## Intermediary Patterns")
            lines.append("")
            lines.append("Entities where an adversarial/conduit code appears in ONE field")
            lines.append("but a different country (typically US) appears in another -- the")
            lines.append("classic intermediary/layering structure.")
            lines.append("")
            lines.append(f"**{len(self.intermediary_patterns):,} entities** exhibit intermediary patterns.")
            lines.append("")
            lines.append("| CIK | Name | Business | Incorp. | Mailing | Pattern |")
            lines.append("|---|---|---|---|---|---|")
            for e in self.intermediary_patterns[:50]:
                pattern = _describe_intermediary_pattern(e)
                lines.append(
                    f"| {e.cik} | {e.name[:50]} | {e.countryba} | {e.countryinc} | {e.countryma} | {pattern} |"
                )
            if len(self.intermediary_patterns) > 50:
                lines.append(f"| ... | *({len(self.intermediary_patterns) - 50} more)* | | | | |")
            lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _describe_intermediary_pattern(entity: MatchedEntity) -> str:
    """Describe the intermediary pattern for a matched entity."""
    countries = {entity.countryba, entity.countryinc, entity.countryma} - {""}
    target_codes = set(ADVERSARIAL_CODES.keys()) | set(CONDUIT_CODES.keys())
    flagged = countries & target_codes
    clean = countries - target_codes

    if not flagged or not clean:
        return ""

    flagged_names = [ADVERSARIAL_CODES.get(c, CONDUIT_CODES.get(c, c)) for c in sorted(flagged)]
    clean_names = sorted(clean)

    parts = []
    if entity.countryinc in target_codes and entity.countryba not in target_codes:
        parts.append(f"inc:{','.join(flagged_names)} but operates in {','.join(clean_names)}")
    elif entity.countryba in target_codes and entity.countryinc not in target_codes:
        parts.append(f"based in {','.join(flagged_names)} but inc:{','.join(clean_names)}")
    elif entity.countryma in target_codes and entity.countryba not in target_codes:
        parts.append(f"mail:{','.join(flagged_names)} but based in {','.join(clean_names)}")
    else:
        parts.append(f"mixed: {','.join(flagged_names)} + {','.join(clean_names)}")

    return "; ".join(parts)


# ---------------------------------------------------------------------------
# Core scan
# ---------------------------------------------------------------------------

def adversarial_scan(
    sub_index: XBRLSubIndex,
    include_conduit: bool = False,
) -> AdversarialScanResult:
    """
    Scan all entities in the XBRL SUB index for adversarial (and optionally
    conduit) nation country codes across all three country fields.

    Args:
        sub_index: Loaded XBRLSubIndex.
        include_conduit: If True, also flag conduit jurisdiction codes.

    Returns:
        AdversarialScanResult with matched entities and analytics.
    """
    target_codes = dict(ADVERSARIAL_CODES)
    if include_conduit:
        target_codes.update(CONDUIT_CODES)

    target_set = set(target_codes.keys())

    matched: Dict[str, MatchedEntity] = {}  # cik -> MatchedEntity
    stats = sub_index.stats()

    for cik, records in sub_index._by_cik.items():
        # Collect all country codes and filing metadata across all records for this CIK
        all_ba: Set[str] = set()
        all_inc: Set[str] = set()
        all_ma: Set[str] = set()
        forms: Set[str] = set()
        dates: Set[str] = set()
        best_rec: Optional[SubRecord] = None

        for rec in records:
            if rec.countryba:
                all_ba.add(rec.countryba)
            if rec.countryinc:
                all_inc.add(rec.countryinc)
            if rec.countryma:
                all_ma.add(rec.countryma)
            if rec.form:
                forms.add(rec.form)
            if rec.filed:
                dates.add(rec.filed)
            if best_rec is None or rec.filed > (best_rec.filed or ""):
                best_rec = rec

        # Check for matches
        matched_fields: Set[str] = set()
        matched_codes: Set[str] = set()

        hits_ba = all_ba & target_set
        hits_inc = all_inc & target_set
        hits_ma = all_ma & target_set

        if hits_ba:
            matched_fields.add("countryba")
            matched_codes.update(hits_ba)
        if hits_inc:
            matched_fields.add("countryinc")
            matched_codes.update(hits_inc)
        if hits_ma:
            matched_fields.add("countryma")
            matched_codes.update(hits_ma)

        if not matched_codes:
            continue

        # Determine tier -- adversarial wins over conduit
        tier = "CONDUIT"
        for code in matched_codes:
            if code in ADVERSARIAL_CODES:
                tier = "ADVERSARIAL"
                break

        entity = MatchedEntity(
            cik=cik,
            name=best_rec.name if best_rec else "",
            sic=best_rec.sic if best_rec else "",
            countryba=best_rec.countryba if best_rec else "",
            countryinc=best_rec.countryinc if best_rec else "",
            countryma=best_rec.countryma if best_rec else "",
            matched_fields=frozenset(matched_fields),
            matched_codes=frozenset(matched_codes),
            matched_tier=tier,
            forms=tuple(sorted(forms)),
            filing_dates=tuple(sorted(dates)),
            former_name=best_rec.former if best_rec else "",
        )
        matched[cik] = entity

    entities = sorted(matched.values(), key=lambda e: (e.matched_tier, e.name))

    # Build analytics
    by_country: Dict[str, List[MatchedEntity]] = defaultdict(list)
    by_field: Dict[str, List[MatchedEntity]] = defaultdict(list)
    intermediary_patterns: List[MatchedEntity] = []

    for e in entities:
        for code in e.matched_codes:
            by_country[code].append(e)
        for fld in e.matched_fields:
            by_field[fld].append(e)

        # Intermediary pattern: adversarial/conduit code in one field,
        # different (non-target) country in another
        country_set = {e.countryba, e.countryinc, e.countryma} - {""}
        has_target = bool(country_set & target_set)
        has_non_target = bool(country_set - target_set)
        if has_target and has_non_target:
            intermediary_patterns.append(e)

    logger.info(
        "Adversarial scan: %d matched CIKs (%d adversarial, %d conduit), "
        "%d intermediary patterns, from %d total CIKs",
        len(entities),
        sum(1 for e in entities if e.matched_tier == "ADVERSARIAL"),
        sum(1 for e in entities if e.matched_tier == "CONDUIT"),
        len(intermediary_patterns),
        stats["unique_ciks"],
    )

    return AdversarialScanResult(
        entities=entities,
        include_conduit=include_conduit,
        total_ciks_scanned=stats["unique_ciks"],
        periods_loaded=stats["periods_loaded"],
        by_country=dict(by_country),
        by_field=dict(by_field),
        intermediary_patterns=intermediary_patterns,
    )


# ---------------------------------------------------------------------------
# Standalone execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    data_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join("data", "SEC", "aqfsn")
    include_conduit = "--conduit" in sys.argv

    idx = XBRLSubIndex()
    idx.load_all_months(data_dir)

    result = adversarial_scan(idx, include_conduit=include_conduit)

    print(result.summary_table())

    # Write to file
    out_path = os.path.join("output", "adversarial_xbrl_scan.md")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result.summary_table())
    print(f"\nReport written to: {out_path}")
