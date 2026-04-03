"""
exhibit21_parser.py

Parses Exhibit 21 (Subsidiary Listing) from SEC 10-K annual reports.

Exhibit 21 is the most complete single-document source for a company's
downward ownership structure. It lists all significant subsidiaries with
their jurisdiction of incorporation and sometimes ownership percentage.

Formats vary widely between filers:
  - HTML tables (most common since ~2020, handled by BeautifulSoup)
  - Plain text with tab/space alignment (fallback regex parser)
  - Tree structures showing parent-child nesting
  - "100% owned" or "wholly-owned" annotations

Each parsed entry feeds into the descension engine as a potential
"subsidiary" edge in the ownership graph.

Usage:
    from secmap.exhibit21_parser import fetch_exhibit21

    entries = fetch_exhibit21("91388")  # Smithfield Foods
    for e in entries:
        print(f"{e.name} -> {e.jurisdiction} ({e.ownership_pct or '?'}%)")

    # With XBRL cross-reference
    from secmap.xbrl_sub import XBRLSubIndex
    idx = XBRLSubIndex()
    idx.load_all_months("data/SEC/aqfsn")
    entries = fetch_exhibit21("91388", sub_index=idx)
    for e in entries:
        if e.matched_cik:
            print(f"{e.name} -> CIK {e.matched_cik}")
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup

from .sec_fetch import (
    _fetch_text,
    fetch_company_submissions,
    fetch_latest_filings,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Exhibit21Entry:
    """A single subsidiary from an Exhibit 21 listing."""
    name: str
    jurisdiction: str
    ownership_pct: Optional[float] = None
    parent_name: str = ""          # if tree structure indicates a parent
    matched_cik: Optional[str] = None  # resolved via XBRL SUB cross-ref
    raw_text: str = ""             # original text before cleaning


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EXHIBIT_21_TYPES = {"EX-21", "EX-21.1", "EX-21.01"}

# Header patterns that indicate the start of subsidiary data
_HEADER_PATTERNS = [
    re.compile(r"name\s+of\s+subsidiar", re.IGNORECASE),
    re.compile(r"subsidiar(?:y|ies)\s+(?:name|list)", re.IGNORECASE),
    re.compile(r"jurisdiction\s+of\s+(?:organization|incorporation)", re.IGNORECASE),
    re.compile(r"state\s+or\s+(?:other\s+)?jurisdiction", re.IGNORECASE),
]

# Ownership percentage patterns
_PCT_RE = re.compile(
    r"(\d{1,3}(?:\.\d+)?)\s*%"
    r"|wholly[- ]owned"
    r"|100\s*%\s*owned"
    r"|indirect(?:ly)?\s+(?:wholly[- ])?owned",
    re.IGNORECASE,
)

# Noise lines to skip
_NOISE_PATTERNS = [
    re.compile(r"^\s*(?:page|continued|see\s+note|exhibit\s+21)", re.IGNORECASE),
    re.compile(r"^\s*\d+\s*$"),  # bare page numbers
    re.compile(r"^\s*[-=_]{5,}\s*$"),  # separator lines
]

# Jurisdiction normalization -- common abbreviations
_JURISDICTION_ALIASES = {
    "DE": "Delaware", "VA": "Virginia", "NC": "North Carolina",
    "NY": "New York", "CA": "California", "TX": "Texas",
    "PA": "Pennsylvania", "OH": "Ohio", "IL": "Illinois",
    "GA": "Georgia", "MD": "Maryland", "NJ": "New Jersey",
    "FL": "Florida", "MA": "Massachusetts", "CT": "Connecticut",
    "WI": "Wisconsin", "MN": "Minnesota", "MO": "Missouri",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "OK": "Oklahoma", "CO": "Colorado", "OR": "Oregon",
    "WA": "Washington", "NV": "Nevada", "WY": "Wyoming",
    "SD": "South Dakota", "ND": "North Dakota",
    "SC": "South Carolina", "TN": "Tennessee", "KY": "Kentucky",
    "LA": "Louisiana", "AR": "Arkansas", "MS": "Mississippi",
    "AL": "Alabama", "NE": "Nebraska", "UT": "Utah",
    "AZ": "Arizona", "NM": "New Mexico", "HI": "Hawaii",
    "AK": "Alaska", "ME": "Maine", "NH": "New Hampshire",
    "VT": "Vermont", "RI": "Rhode Island", "MT": "Montana",
    "ID": "Idaho", "WV": "West Virginia", "DC": "District of Columbia",
}


# ---------------------------------------------------------------------------
# Exhibit 21 document locator
# ---------------------------------------------------------------------------

def _find_exhibit21_url(cik: str) -> Optional[Tuple[str, str, str]]:
    """
    Find the Exhibit 21 document URL from the most recent 10-K filing.

    Returns (exhibit_url, accession, filing_date) or None.
    """
    filings = fetch_latest_filings(cik, ["10-K", "10-K/A"], limit=3)
    if not filings:
        logger.debug("No 10-K filings found for CIK %s", cik)
        return None

    for filing in filings:
        acc = filing["accession"]
        acc_folder = acc.replace("-", "")
        date = filing.get("filing_date", "")

        # Fetch the filing index page
        index_url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik}/"
            f"{acc_folder}/{acc}-index.htm"
        )
        index_html = _fetch_text(index_url)
        if not index_html:
            continue

        # Parse the index to find EX-21 document
        soup = BeautifulSoup(index_html, "html.parser")
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 4:
                continue
            doc_type = cells[3].get_text(strip=True).upper()
            if doc_type in _EXHIBIT_21_TYPES:
                link = cells[2].find("a")
                if link and link.get("href"):
                    href = link["href"]
                    if not href.startswith("http"):
                        href = "https://www.sec.gov" + href
                    # Strip /ix?doc= wrapper if present
                    if "/ix?doc=" in href:
                        href = "https://www.sec.gov" + href.split("/ix?doc=")[1]
                    logger.info("Found Exhibit 21: %s (acc %s)", href, acc)
                    return href, acc, date

        # Also check Description column (index 1) for "EX-21"
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            desc = cells[1].get_text(strip=True).upper()
            if any(t in desc for t in _EXHIBIT_21_TYPES):
                link = cells[2].find("a")
                if link and link.get("href"):
                    href = link["href"]
                    if not href.startswith("http"):
                        href = "https://www.sec.gov" + href
                    if "/ix?doc=" in href:
                        href = "https://www.sec.gov" + href.split("/ix?doc=")[1]
                    logger.info("Found Exhibit 21 (via desc): %s", href)
                    return href, acc, date

    logger.debug("No Exhibit 21 found in recent 10-K filings for CIK %s", cik)
    return None


# ---------------------------------------------------------------------------
# HTML table parser (primary strategy)
# ---------------------------------------------------------------------------

def _is_header_row(cells: List[str]) -> bool:
    """Check if a row of cell texts looks like a header."""
    joined = " ".join(cells).lower()
    return any(p.search(joined) for p in _HEADER_PATTERNS)


def _is_noise(text: str) -> bool:
    return any(p.match(text) for p in _NOISE_PATTERNS)


def _extract_ownership_pct(text: str) -> Optional[float]:
    """Extract ownership percentage from text."""
    if not text:
        return None
    lower = text.lower()
    if "wholly" in lower and "owned" in lower:
        return 100.0
    if "100%" in text or "100 %" in text:
        return 100.0
    m = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", text)
    if m:
        val = float(m.group(1))
        if 0 < val <= 100:
            return val
    return None


def _clean_subsidiary_name(name: str) -> str:
    """Clean and normalize a subsidiary name."""
    # Remove leading bullets, numbers, dashes, asterisks
    name = re.sub(r"^[\s\-\*\u2022\u2013\u2014\u25cf\u25cb]+", "", name)
    # Remove trailing footnote markers
    name = re.sub(r"\s*[\(\[][0-9a-z]+[\)\]]\s*$", "", name)
    name = re.sub(r"\s*\*+\s*$", "", name)
    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _normalize_jurisdiction(jur: str) -> str:
    """Normalize jurisdiction text."""
    jur = jur.strip().rstrip(".,;:")
    jur = re.sub(r"\s+", " ", jur).strip()
    # Check abbreviation lookup
    upper = jur.upper().strip()
    if upper in _JURISDICTION_ALIASES:
        return _JURISDICTION_ALIASES[upper]
    return jur


def _parse_html_table(html_content: str) -> List[Exhibit21Entry]:
    """Parse Exhibit 21 from HTML table structure using BeautifulSoup."""
    soup = BeautifulSoup(html_content, "html.parser")
    entries = []
    header_seen = False

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            # Filter empty cells
            cells = [c for c in cells if c]

            if not cells:
                continue

            # Detect and skip header rows
            if _is_header_row(cells):
                header_seen = True
                continue

            if not header_seen:
                # Before we see a header, check if this looks like data anyway
                if len(cells) >= 2 and not _is_header_row(cells):
                    header_seen = True
                else:
                    continue

            if _is_noise(cells[0]):
                continue

            if len(cells) >= 2:
                name = _clean_subsidiary_name(cells[0])
                jurisdiction = _normalize_jurisdiction(cells[1])
                pct = None

                # Check for ownership percentage in a third column or in the name/jurisdiction text
                if len(cells) >= 3:
                    pct = _extract_ownership_pct(cells[2])
                if pct is None:
                    pct = _extract_ownership_pct(cells[0] + " " + cells[1])

                if name and len(name) >= 3 and jurisdiction:
                    entries.append(Exhibit21Entry(
                        name=name,
                        jurisdiction=jurisdiction,
                        ownership_pct=pct,
                        raw_text=" | ".join(cells),
                    ))

            elif len(cells) == 1:
                # Single-cell row -- might be a continuation or a combined name+jurisdiction
                text = cells[0]
                # Try to split on common delimiters
                for sep in ["\t", "   ", " - ", "  "]:
                    parts = [p.strip() for p in text.split(sep) if p.strip()]
                    if len(parts) >= 2:
                        name = _clean_subsidiary_name(parts[0])
                        jurisdiction = _normalize_jurisdiction(parts[-1])
                        pct = _extract_ownership_pct(text)
                        if name and len(name) >= 3:
                            entries.append(Exhibit21Entry(
                                name=name,
                                jurisdiction=jurisdiction,
                                ownership_pct=pct,
                                raw_text=text,
                            ))
                        break

    return entries


# ---------------------------------------------------------------------------
# Plain text fallback parser
# ---------------------------------------------------------------------------

# Pattern: "Company Name" followed by whitespace/tab then "Jurisdiction"
_TEXT_LINE_RE = re.compile(
    r"^(.{5,80}?)\s{3,}(.{3,50}?)(?:\s{3,}(.+?))?$"
)


def _parse_plain_text(text: str) -> List[Exhibit21Entry]:
    """Fallback parser for plain-text Exhibit 21 documents."""
    entries = []
    header_seen = False

    for line in text.split("\n"):
        line = line.rstrip()
        if not line.strip():
            continue

        if _is_noise(line.strip()):
            continue

        if any(p.search(line) for p in _HEADER_PATTERNS):
            header_seen = True
            continue

        if not header_seen:
            continue

        m = _TEXT_LINE_RE.match(line)
        if m:
            name = _clean_subsidiary_name(m.group(1))
            jurisdiction = _normalize_jurisdiction(m.group(2))
            pct_text = m.group(3) or ""
            pct = _extract_ownership_pct(pct_text) or _extract_ownership_pct(line)

            if name and len(name) >= 3 and jurisdiction:
                entries.append(Exhibit21Entry(
                    name=name,
                    jurisdiction=jurisdiction,
                    ownership_pct=pct,
                    raw_text=line.strip(),
                ))

    return entries


# ---------------------------------------------------------------------------
# XBRL cross-reference
# ---------------------------------------------------------------------------

def _cross_reference_xbrl(entries: List[Exhibit21Entry], sub_index) -> int:
    """
    Attempt to match subsidiary names against the XBRL SUB table.
    Returns count of resolved matches.
    """
    if sub_index is None:
        return 0

    resolved = 0
    for entry in entries:
        try:
            matches = sub_index.search(entry.name)
            if not matches:
                continue
            # Exact match (case-insensitive)
            for m in matches:
                if m.name.upper() == entry.name.upper():
                    entry_obj = entry  # dataclass is not frozen, can mutate
                    # Use object.__setattr__ since we want to keep it simple
                    object.__setattr__(entry, "matched_cik", m.cik)
                    resolved += 1
                    logger.debug("XBRL match: '%s' -> CIK %s", entry.name, m.cik)
                    break
        except Exception as e:
            logger.debug("XBRL cross-ref failed for '%s': %s", entry.name, e)

    return resolved


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_exhibit21(
    cik: str,
    sub_index=None,
) -> List[Exhibit21Entry]:
    """
    Fetch and parse Exhibit 21 from the most recent 10-K filing for a CIK.

    Args:
        cik: SEC Central Index Key.
        sub_index: Optional XBRLSubIndex for CIK cross-referencing.

    Returns:
        List of Exhibit21Entry objects.
    """
    cik = cik.strip()
    logger.info("Fetching Exhibit 21 for CIK %s", cik)

    # Step 1: Locate the Exhibit 21 document
    result = _find_exhibit21_url(cik)
    if not result:
        logger.info("No Exhibit 21 found for CIK %s", cik)
        return []

    exhibit_url, accession, filing_date = result

    # Step 2: Fetch the exhibit content
    content = _fetch_text(exhibit_url)
    if not content:
        logger.error("Failed to fetch Exhibit 21 content from %s", exhibit_url)
        return []

    logger.info("Fetched Exhibit 21: %d chars from %s", len(content), exhibit_url)

    # Step 3: Parse -- try HTML table first, fall back to plain text
    entries = _parse_html_table(content)

    if not entries:
        # Strip HTML and try plain text parser
        from .parse_filings import strip_html, normalize_text
        plain = normalize_text(strip_html(content))
        entries = _parse_plain_text(plain)
        if entries:
            logger.info("Parsed %d entries via plain-text fallback", len(entries))

    logger.info(
        "Exhibit 21 for CIK %s: %d subsidiaries (acc %s, filed %s)",
        cik, len(entries), accession, filing_date,
    )

    # Step 4: XBRL cross-reference
    if sub_index and entries:
        resolved = _cross_reference_xbrl(entries, sub_index)
        logger.info("XBRL cross-reference: %d of %d resolved to CIKs", resolved, len(entries))

    return entries


def parse_exhibit21_text(content: str, sub_index=None) -> List[Exhibit21Entry]:
    """
    Parse Exhibit 21 content directly (without fetching from EDGAR).
    Useful when the content is already available from the cache or pipeline.
    """
    if not content:
        return []

    entries = _parse_html_table(content)
    if not entries:
        # Try plain text directly first (preserves column alignment)
        entries = _parse_plain_text(content)
    if not entries:
        # Last resort: strip HTML then try plain text
        from .parse_filings import strip_html, normalize_text
        plain = normalize_text(strip_html(content))
        entries = _parse_plain_text(plain)

    if sub_index and entries:
        _cross_reference_xbrl(entries, sub_index)

    return entries


# ---------------------------------------------------------------------------
# Standalone testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    cik = sys.argv[1] if len(sys.argv) > 1 else "91388"  # Smithfield Foods
    data_dir = sys.argv[2] if len(sys.argv) > 2 else ""

    sub_index = None
    if data_dir and os.path.isdir(data_dir):
        from .xbrl_sub import XBRLSubIndex
        sub_index = XBRLSubIndex()
        sub_index.load_all_months(data_dir)

    entries = fetch_exhibit21(cik, sub_index=sub_index)

    print(f"\n{'='*70}")
    print(f"Exhibit 21 Subsidiaries for CIK {cik}: {len(entries)} entries")
    print(f"{'='*70}")
    for i, e in enumerate(entries, 1):
        pct = f" ({e.ownership_pct}%)" if e.ownership_pct else ""
        xbrl = f" [CIK {e.matched_cik}]" if e.matched_cik else ""
        print(f"  {i:3d}. {e.name:50s} {e.jurisdiction}{pct}{xbrl}")
