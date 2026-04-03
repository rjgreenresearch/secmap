"""
cik_discovery.py

Recursive discovery of related CIKs from SEC filings.

Enhancements:
- Full logging coverage
- Input validation
- Graceful exception handling
- Deterministic BFS traversal
- Protection against malformed filings
- Configurable recursion and filing limits
"""

from __future__ import annotations

import logging
import re
from collections import deque
from dataclasses import dataclass
from typing import Iterable, List, Set, Deque, Dict, Optional

from .sec_fetch import fetch_filings_for_cik, fetch_company_submissions, fetch_filing_by_accession
from .parse_filings import parse_filing_to_sections

logger = logging.getLogger(__name__)

# CIK pattern: "CIK 0000123456" or "CIK: 123456"
_CIK_TOKEN = re.compile(r"\bCIK\s*[:#]?\s*0*([0-9]{3,10})\b", re.IGNORECASE)
# CIK in URLs: /CIK0000123456.json or /data/123456/
_CIK_URL = re.compile(r"/CIK0*([0-9]{5,10})\.json", re.IGNORECASE)
# Accession number prefix encodes the filer CIK: 0000921895-13-001960 -> 921895
_ACCESSION_CIK = re.compile(r"^0*(\d{5,10})-\d{2}-\d{6}$")

# Known filing agent CIKs -- these are entities that file documents on behalf
# of companies (law firms, financial printers, filing agents). They appear in
# accession number prefixes but don't have their own company submissions.
# Fetching their submissions returns 404.
_FILING_AGENT_CIKS = {
    "1144204",  # Edgar Online / R.R. Donnelley
    "950159",   # Donnelley Financial Solutions
    "1213900",  # EastBridge Financial
    "1628280",  # Toppan Merrill
    "1410578",  # SEC filing agent
    "1341004",  # SEC filing agent
    "1275287",  # SEC filing agent
    "1258897",  # SEC filing agent
    "1145549",  # SEC filing agent
    "1013762",  # SEC filing agent
    "1683168",  # SEC filing agent
    "1406774",  # SEC filing agent
    "922423",   # SEC filing agent
    "950170",   # Donnelley Financial
    "1193125",  # SEC filing agent
    "1104659",  # SEC filing agent
    "1140361",  # SEC filing agent
    "1437749",  # SEC filing agent
    "1493152",  # SEC filing agent
    "1477932",  # SEC filing agent
    "1171843",  # SEC filing agent
    "1185185",  # SEC filing agent
    "1554795",  # SEC filing agent
    "1558370",  # SEC filing agent
    "1580642",  # SEC filing agent
    "1829126",  # SEC filing agent
    "1903596",  # SEC filing agent
    "1445546",  # SEC filing agent
    "1214659",  # SEC filing agent
    "1539497",  # SEC filing agent
    "1062993",  # SEC filing agent
    "1079973",  # SEC filing agent
}


# ---------------------------------------------------------------------------
# Configuration dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DiscoveryConfig:
    form_types: List[str]
    max_depth: int = 2
    max_filings_per_cik: int = 10
    max_total_ciks: int = 50          # hard cap on total CIKs visited
    only_ascend: bool = True          # only follow ownership UPWARD (filer -> subject)
    skip_filing_agents: bool = True   # skip law firms / filing agents


@dataclass(frozen=True)
class DiscoveredFiling:
    cik: str
    accession: str
    form: str
    filing_date: str
    content: str
    depth: int
    company: str = ""


@dataclass(frozen=True)
class DiscoveryResult:
    root_cik: str
    visited_ciks: Set[str]
    filings: List[DiscoveredFiling]
    company_info: Dict  # cik -> {"name": ..., "stateOfIncorporation": ..., "sic": ...}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_cik(cik: str) -> str:
    try:
        return str(int(cik))
    except Exception:
        logger.warning("Invalid CIK encountered during normalization: %r", cik)
        return ""


def extract_ciks_from_text(text: str) -> List[str]:
    """Extract CIK-like tokens from filing text."""
    if not text:
        return []

    found: List[str] = []
    for m in _CIK_TOKEN.finditer(text):
        cik = _normalize_cik(m.group(1))
        if cik:
            found.append(cik)
    for m in _CIK_URL.finditer(text):
        cik = _normalize_cik(m.group(1))
        if cik:
            found.append(cik)

    seen = set()
    unique = []
    for c in found:
        if c not in seen:
            seen.add(c)
            unique.append(c)

    logger.debug("Extracted %d CIKs from text", len(unique))
    return unique


def extract_filer_cik_from_accession(accession: str) -> Optional[str]:
    """Extract the filer's CIK from an accession number prefix."""
    m = _ACCESSION_CIK.match(accession)
    if m:
        return _normalize_cik(m.group(1))
    return None


def discover_related_ciks_from_filing(content: str, accession: str = "", subject_cik: str = "") -> List[str]:
    """
    Given filing content and metadata, extract related CIKs from:
    1. SGML headers (CENTRAL INDEX KEY for filer and subject)
    2. CIK tokens in the filing text
    3. CIK patterns in URLs
    """
    if not content:
        logger.warning("Empty filing content encountered during CIK extraction")
        return []

    found = []

    try:
        # 1. SGML headers (present in .txt bundles)
        header = content[:10000]
        for m in re.finditer(r"CENTRAL INDEX KEY:\s*0*(\d{5,10})", header):
            cik = _normalize_cik(m.group(1))
            if cik and cik != subject_cik:
                found.append(cik)

        # 2. Filing text CIK tokens
        sections = parse_filing_to_sections(content)
        text = sections.get("full_text", "") or content
        found.extend(extract_ciks_from_text(text))

        # 3. Filer CIK from accession number
        if accession:
            filer = extract_filer_cik_from_accession(accession)
            if filer and filer != subject_cik:
                found.append(filer)

    except Exception as e:
        logger.error("Error extracting CIKs from filing: %s", e)

    # Deduplicate, remove self-references
    seen = set()
    unique = []
    for c in found:
        if c and c not in seen and c != subject_cik:
            seen.add(c)
            unique.append(c)

    return unique


# ---------------------------------------------------------------------------
# BFS traversal of CIK universe
# ---------------------------------------------------------------------------

def walk_cik_universe(
    root_cik: str,
    config: DiscoveryConfig,
) -> DiscoveryResult:
    """
    Breadth-first walk of related CIKs starting from root_cik.

    For each CIK:
      - Fetch recent filings of specified form types
      - Extract related CIKs from those filings
      - Enqueue new CIKs up to max_depth
    """
    root = _normalize_cik(root_cik)
    if not root:
        raise ValueError(f"Invalid root CIK: {root_cik}")

    visited: Set[str] = set()
    filings: List[DiscoveredFiling] = []
    company_info: Dict[str, Dict] = {}
    queue: Deque[tuple[str, int]] = deque([(root, 0)])

    logger.info(
        "Starting CIK discovery from root %s (max_depth=%d)",
        root,
        config.max_depth,
    )

    while queue:
        current_cik, depth = queue.popleft()

        if current_cik in visited:
            logger.debug("Skipping already visited CIK %s", current_cik)
            continue

        # Hard cap on total CIKs to prevent exponential explosion
        if len(visited) >= config.max_total_ciks:
            logger.warning(
                "Reached max_total_ciks limit (%d). Stopping discovery.",
                config.max_total_ciks,
            )
            break

        visited.add(current_cik)
        logger.info("Processing CIK %s at depth %d (%d/%d visited)",
                    current_cik, depth, len(visited), config.max_total_ciks)

        # Fetch company metadata for this CIK
        try:
            submissions = fetch_company_submissions(current_cik)
            if submissions:
                company_info[current_cik] = {
                    "name": submissions.get("name", ""),
                    "stateOfIncorporation": submissions.get("stateOfIncorporation", ""),
                    "sic": submissions.get("sic", ""),
                    "sicDescription": submissions.get("sicDescription", ""),
                }
        except Exception as e:
            logger.error("Error fetching company info for CIK %s: %s", current_cik, e)

        # Fetch filings for this CIK
        try:
            fetched = fetch_filings_for_cik(
                current_cik,
                form_types=config.form_types,
                limit=config.max_filings_per_cik,
            )
        except Exception as e:
            logger.error("Error fetching filings for CIK %s: %s", current_cik, e)
            continue

        for f in fetched:
            df = DiscoveredFiling(
                cik=current_cik,
                accession=f["accession"],
                form=f["form"],
                filing_date=f["filing_date"],
                content=f["content"],
                depth=depth,
                company=f.get("company", ""),
            )
            filings.append(df)

            # Extract related CIKs from filing text and accession
            related = discover_related_ciks_from_filing(
                f["content"], accession=f["accession"], subject_cik=current_cik,
            )

            # For SC-13 filings, also fetch the .txt bundle to get SGML headers
            # which contain the filer's CENTRAL INDEX KEY
            if f["form"].startswith("SC 13"):
                try:
                    bundle = fetch_filing_by_accession(current_cik, f["accession"])
                    if bundle:
                        sgml_ciks = discover_related_ciks_from_filing(
                            bundle, accession=f["accession"], subject_cik=current_cik,
                        )
                        for c in sgml_ciks:
                            if c not in related:
                                related.append(c)
                except Exception as e:
                    logger.debug("Failed to fetch .txt bundle for %s: %s", f["accession"], e)

            # Filter: only_ascend means we only follow the ownership chain
            # UPWARD. At depth > 0, we only enqueue CIKs that were found
            # as FILERS of SC-13 filings about the current CIK (i.e., entities
            # that OWN the current CIK). We skip CIKs found in the current
            # CIK's own SC-13 filings about OTHER companies (sideways).
            if config.only_ascend and depth > 0:
                # Only keep CIKs extracted from SGML headers (filer CIKs)
                # and accession-based CIKs -- these are entities that filed
                # ABOUT the current CIK, i.e., they own it.
                # Drop CIKs found in the text of filings BY the current CIK
                # about other companies (those go sideways).
                filer_ciks = set()
                for ff in fetched:
                    fc = extract_filer_cik_from_accession(ff["accession"])
                    if fc and fc != current_cik:
                        filer_ciks.add(fc)
                    # Also get SGML header CIKs
                    if ff["form"].startswith("SC 13"):
                        try:
                            bundle = fetch_filing_by_accession(current_cik, ff["accession"])
                            if bundle:
                                for m in re.finditer(r"CENTRAL INDEX KEY:\s*0*(\d{5,10})", bundle[:10000]):
                                    c = _normalize_cik(m.group(1))
                                    if c and c != current_cik:
                                        filer_ciks.add(c)
                        except Exception:
                            pass
                related = [c for c in related if c in filer_ciks]

            logger.debug(
                "Found %d related CIKs in filing %s (%s)",
                len(related),
                f["accession"],
                current_cik,
            )

            # Enqueue next layer (skip known filing agents)
            if depth + 1 <= config.max_depth:
                for rc in related:
                    if rc not in visited and rc not in _FILING_AGENT_CIKS:
                        queue.append((rc, depth + 1))

    logger.info(
        "CIK discovery complete. Root=%s, visited=%d, filings=%d",
        root,
        len(visited),
        len(filings),
    )

    return DiscoveryResult(
        root_cik=root,
        visited_ciks=visited,
        filings=filings,
        company_info=company_info,
    )
