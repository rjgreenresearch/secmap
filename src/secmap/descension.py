"""
descension.py

Downward ownership chain traversal — given a parent CIK, discover all
entities that parent OWNS or CONTROLS.

SECMap's existing pipeline ascends: CIK -> who owns it -> who owns THEM.
The descension engine does the opposite: CIK -> what it owns -> what THOSE own.

Data source (this module): XBRL co-registrants (aciks field).
When a parent files a consolidated financial statement, the aciks field lists
the CIKs of all co-registrants included in the consolidation — these are
direct subsidiaries or controlled entities.

Future data sources (not yet implemented):
  - Exhibit 21 subsidiary listings from 10-K filings
  - Cross-referencing institution names against XBRL SUB by name

Produces OwnershipEdge objects with:
  relationship = "consolidated_subsidiary"
  method       = "xbrl_co_registrant"

Usage:
    from secmap.xbrl_sub import XBRLSubIndex
    from secmap.descension import descend_from_cik

    idx = XBRLSubIndex()
    idx.load_all_months("data/SEC/aqfsn")

    result = descend_from_cik("1091667", idx, max_depth=5)
    for edge in result.edges:
        print(f"{edge.source.cleaned_name} -> {edge.target.cleaned_name}")
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Set, Tuple

from .entity_classification import Entity
from .jurisdiction_inference import infer_jurisdiction_with_risk, get_risk_tier
from .ownership_edges import OwnershipEdge
from .state_affiliation import classify_state_affiliation
from .xbrl_sub import SubRecord, XBRLSubIndex

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class DescensionResult:
    """Result of a downward ownership chain traversal."""
    root_cik: str
    root_name: str
    edges: List[OwnershipEdge]
    visited_ciks: Set[str]
    tree: Dict[str, List[str]]  # parent_cik -> [child_cik, ...]
    entity_info: Dict[str, Dict]  # cik -> {name, countryba, countryinc, sic, ...}


# ---------------------------------------------------------------------------
# Stub filing object for OwnershipEdge compatibility
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _XBRLFiling:
    """Minimal filing-like object so OwnershipEdge.filing.accession works."""
    accession: str
    form: str
    filing_date: str
    depth: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _best_record(records: List[SubRecord]) -> Optional[SubRecord]:
    """Pick the most informative SubRecord for a CIK — prefer 10-K/20-F, then most recent."""
    if not records:
        return None
    preferred = [r for r in records if r.form in ("10-K", "20-F", "10-K/A")]
    pool = preferred if preferred else records
    return max(pool, key=lambda r: r.filed or "")


def _entity_info_from_record(rec: SubRecord) -> Dict:
    return {
        "name": rec.name,
        "cik": rec.cik,
        "sic": rec.sic,
        "countryba": rec.countryba,
        "stprba": rec.stprba,
        "cityba": rec.cityba,
        "countryinc": rec.countryinc,
        "stprinc": rec.stprinc,
        "former": rec.former,
        "ein": rec.ein,
    }


def _resolve_jurisdiction(name: str, country_code: str = ""):
    """Return (country, risk_tier) using jurisdiction inference + country override."""
    result = infer_jurisdiction_with_risk(name, issuer_country=country_code or None)
    if result:
        return result.country, result.risk_tier
    if country_code:
        return country_code, get_risk_tier(country_code)
    return None, None


def _build_edge(
    parent_info: Dict,
    child_info: Dict,
    filing: _XBRLFiling,
    depth: int,
) -> OwnershipEdge:
    """Build a consolidated_subsidiary OwnershipEdge from parent -> child."""
    parent_name = parent_info.get("name", f"CIK {parent_info.get('cik', '?')}")
    child_name = child_info.get("name", f"CIK {child_info.get('cik', '?')}")

    parent_entity = Entity(
        raw_name=parent_name,
        cleaned_name=parent_name,
        entity_type="company",
        notes=f"CIK: {parent_info.get('cik', '')}",
    )
    child_entity = Entity(
        raw_name=child_name,
        cleaned_name=child_name,
        entity_type="company",
        notes=f"CIK: {child_info.get('cik', '')}",
    )

    src_jur, src_tier = _resolve_jurisdiction(parent_name, parent_info.get("countryba", ""))
    tgt_jur, tgt_tier = _resolve_jurisdiction(child_name, child_info.get("countryba", ""))

    # State affiliation on the child (the discovered subsidiary)
    sa = classify_state_affiliation(name=child_name, role=None, issuer_country=tgt_jur)
    sa_cat = sa.category if sa.category != "None" else None
    sa_sub = sa.subcategory if sa_cat else None
    sa_detail = sa.details if sa_cat else None

    inc_country = child_info.get("countryinc", "")
    inc_state = child_info.get("stprinc", "")
    sic = child_info.get("sic", "")

    notes_parts = []
    if inc_country:
        notes_parts.append(f"incorporated: {inc_country}")
        if inc_state:
            notes_parts[-1] += f"/{inc_state}"
    if sic:
        notes_parts.append(f"SIC: {sic}")
    if child_info.get("former"):
        notes_parts.append(f"former: {child_info['former']}")
    if sa_cat:
        notes_parts.append(f"state_affiliation: {sa_cat}")

    return OwnershipEdge(
        source=parent_entity,
        target=child_entity,
        relationship="consolidated_subsidiary",
        relationship_detail=f"co-registrant in consolidated filing",
        filing=filing,
        method="xbrl_co_registrant",
        notes="; ".join(notes_parts) if notes_parts else None,
        source_jurisdiction=src_jur,
        source_risk_tier=src_tier,
        target_jurisdiction=tgt_jur,
        target_risk_tier=tgt_tier,
        state_affiliation=sa_cat,
        state_affiliation_sub=sa_sub,
        state_affiliation_detail=sa_detail,
        role_is_ownership=True,
        chain_depth=depth,
    )


# ---------------------------------------------------------------------------
# BFS descension engine
# ---------------------------------------------------------------------------

def descend_from_cik(
    root_cik: str,
    sub_index: XBRLSubIndex,
    max_depth: int = 5,
    max_total_ciks: int = 500,
) -> DescensionResult:
    """
    Breadth-first downward traversal from root_cik through XBRL co-registrants.

    At each level, queries the XBRLSubIndex for the CIK's submissions,
    extracts co-registrant CIKs from the aciks field, and recurses.

    Args:
        root_cik: Starting parent CIK.
        sub_index: Loaded XBRLSubIndex with SUB table data.
        max_depth: Maximum descent levels (default 5).
        max_total_ciks: Hard cap on total CIKs visited.

    Returns:
        DescensionResult with edges, tree structure, and entity metadata.
    """
    root_cik = root_cik.strip()
    visited: Set[str] = set()
    edges: List[OwnershipEdge] = []
    tree: Dict[str, List[str]] = {}
    entity_info: Dict[str, Dict] = {}

    # Resolve root entity info
    root_records = sub_index.by_cik(root_cik)
    root_rec = _best_record(root_records)
    root_name = root_rec.name if root_rec else f"CIK {root_cik}"
    if root_rec:
        entity_info[root_cik] = _entity_info_from_record(root_rec)
    else:
        entity_info[root_cik] = {"name": root_name, "cik": root_cik}

    queue: Deque[Tuple[str, int]] = deque([(root_cik, 0)])

    logger.info(
        "Descension: starting from %s (%s), max_depth=%d",
        root_cik, root_name, max_depth,
    )

    while queue:
        current_cik, depth = queue.popleft()

        if current_cik in visited:
            continue
        if len(visited) >= max_total_ciks:
            logger.warning("Reached max_total_ciks (%d), stopping descension.", max_total_ciks)
            break

        visited.add(current_cik)

        # Get all submissions for this CIK
        records = sub_index.by_cik(current_cik)
        if not records and current_cik != root_cik:
            logger.debug("No XBRL SUB records for CIK %s", current_cik)
            continue

        # Populate entity info if not already present
        if current_cik not in entity_info:
            rec = _best_record(records)
            if rec:
                entity_info[current_cik] = _entity_info_from_record(rec)
            else:
                entity_info[current_cik] = {"name": f"CIK {current_cik}", "cik": current_cik}

        # Collect all co-registrant CIKs across all filings for this CIK
        child_ciks: Set[str] = set()
        best_filing_rec: Optional[SubRecord] = None

        for rec in records:
            if rec.aciks:
                for c in rec.aciks.split():
                    c = c.strip()
                    if c and c != current_cik:
                        child_ciks.add(c)
                        if best_filing_rec is None or rec.filed > (best_filing_rec.filed or ""):
                            best_filing_rec = rec

        if not child_ciks:
            logger.debug("CIK %s has no co-registrants", current_cik)
            continue

        tree[current_cik] = sorted(child_ciks)

        # Build a filing stub from the best record
        if best_filing_rec is None:
            best_filing_rec = _best_record(records)
        filing_stub = _XBRLFiling(
            accession=best_filing_rec.adsh if best_filing_rec else "",
            form=best_filing_rec.form if best_filing_rec else "",
            filing_date=best_filing_rec.filed if best_filing_rec else "",
            depth=depth,
        )

        parent_info = entity_info[current_cik]

        for child_cik in sorted(child_ciks):
            # Resolve child entity info
            child_records = sub_index.by_cik(child_cik)
            child_rec = _best_record(child_records)
            if child_rec:
                entity_info[child_cik] = _entity_info_from_record(child_rec)
            else:
                entity_info[child_cik] = {"name": f"CIK {child_cik}", "cik": child_cik}

            child_info = entity_info[child_cik]

            edge = _build_edge(parent_info, child_info, filing_stub, depth)
            edges.append(edge)

            logger.debug(
                "  depth %d: %s -> %s (%s)",
                depth, parent_info.get("name", "?"), child_info.get("name", "?"), child_cik,
            )

            # Enqueue child for further descent
            if depth + 1 <= max_depth and child_cik not in visited:
                queue.append((child_cik, depth + 1))

    logger.info(
        "Descension complete: root=%s, visited=%d CIKs, %d edges, max_depth_reached=%d",
        root_cik, len(visited), len(edges),
        max(e.chain_depth for e in edges) if edges else 0,
    )

    return DescensionResult(
        root_cik=root_cik,
        root_name=root_name,
        edges=edges,
        visited_ciks=visited,
        tree=tree,
        entity_info=entity_info,
    )


def print_tree(result: DescensionResult, indent: int = 0, cik: str = "") -> None:
    """Pretty-print the descension tree to stdout."""
    if not cik:
        cik = result.root_cik
    info = result.entity_info.get(cik, {})
    name = info.get("name", f"CIK {cik}")
    country = info.get("countryba", "")
    inc = info.get("countryinc", "")
    sic = info.get("sic", "")
    prefix = "  " * indent + ("|-- " if indent > 0 else "")
    meta = []
    if country:
        meta.append(country)
    if inc and inc != country:
        meta.append(f"inc:{inc}")
    if sic:
        meta.append(f"SIC:{sic}")
    meta_str = f" ({', '.join(meta)})" if meta else ""
    print(f"{prefix}{name} [CIK {cik}]{meta_str}")
    for child in result.tree.get(cik, []):
        print_tree(result, indent + 1, child)


# ---------------------------------------------------------------------------
# Standalone testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    data_dir = sys.argv[2] if len(sys.argv) > 2 else "data/SEC/aqfsn"
    target_cik = sys.argv[1] if len(sys.argv) > 1 else "1091667"  # Charter Communications

    idx = XBRLSubIndex()
    idx.load_all_months(data_dir)

    result = descend_from_cik(target_cik, idx, max_depth=5)

    print(f"\n{'='*60}")
    print(f"Descension Tree: {result.root_name} (CIK {result.root_cik})")
    print(f"{'='*60}")
    print_tree(result)

    print(f"\n--- Edges ({len(result.edges)}) ---")
    for e in result.edges:
        sa = f" [{e.state_affiliation}]" if e.state_affiliation else ""
        print(
            f"  depth {e.chain_depth}: {e.source.cleaned_name} -> "
            f"{e.target.cleaned_name} "
            f"(tgt_country={e.target_jurisdiction}{sa})"
        )

    print(f"\n--- Summary ---")
    print(f"  CIKs visited: {len(result.visited_ciks)}")
    print(f"  Edges: {len(result.edges)}")
    print(f"  Tree branches: {len(result.tree)}")
