"""
ownership_mapper.py

High-level orchestrator for SECMap:
- Recursively discovers CIKs
- Fetches filings
- Parses filings into sections
- Extracts people, institutions, and SC-13 beneficial owners
- Builds typed ownership/governance edges
- Builds incorporated_in edges from company metadata
- Deduplicates edges
- Returns a structured result object
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import List, Set, Dict, Optional

from .cik_discovery import walk_cik_universe, DiscoveryConfig
from .parse_filings import parse_filing_to_sections
from .sc13_parser import parse_sc13_beneficial_ownership
from .relationship_builder import build_role_relationships_for_filing
from .ownership_edges import (
    OwnershipEdge,
    build_beneficial_owner_edges,
    build_country_association_edges,
    merge_and_deduplicate_edges,
)
from .entity_classification import Entity
from .jurisdiction_inference import get_risk_tier

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SECMapResult:
    root_cik: str
    visited_ciks: Set[str]
    filings_processed: int
    edges: List
    company_info: Dict  # cik -> {"name": ..., "stateOfIncorporation": ...}
    xbrl_enriched: bool = False
    descension_ciks: int = 0
    descension_edges: int = 0
    xbrl_resolved_institutions: int = 0


# US state codes to full names
_STATE_CODES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
    # Canadian provinces
    "ON": "Ontario", "BC": "British Columbia", "AB": "Alberta", "QC": "Quebec",
    # Country codes seen in SEC data (EDGAR stateOfIncorporation field)
    "X2": "United Kingdom", "V8": "British Virgin Islands", "E9": "Cayman Islands",
    "L2": "Bermuda", "Y6": "Bahamas", "D8": "Marshall Islands",
    "F4": "China", "X0": "United Kingdom", "A6": "Canada",
    "C3": "Australia", "U0": "Singapore",
    "J5": "Japan", "K7": "South Korea", "I6": "Israel",
    "G7": "Germany", "I0": "France", "N4": "Netherlands",
    "O9": "Switzerland", "P7": "Sweden", "Q2": "Taiwan",
    "R8": "Russia", "S0": "South Africa", "T2": "Turkey",
    "W4": "Hong Kong", "W0": "Ireland", "M5": "Luxembourg",
    "H6": "India", "B3": "Brazil", "B5": "Belgium",
    "D5": "Denmark", "E8": "Finland", "I3": "Italy",
    "N8": "Norway", "P8": "Spain", "R2": "Singapore",
    "V2": "Bermuda", "V7": "British Virgin Islands",
    # Common abbreviations in entity names
    "NL": "Netherlands", "LUX": "Luxembourg", "HK": "Hong Kong",
    "CH": "Switzerland", "SG": "Singapore", "IE": "Ireland",
    "BE": "Belgium", "FR": "France", "IT": "Italy",
    "ES": "Spain", "SE": "Sweden", "DK": "Denmark",
    "NO": "Norway", "FI": "Finland", "AT": "Austria",
    "PT": "Portugal", "GR": "Greece", "PL": "Poland",
    "CZ": "Czech Republic", "RO": "Romania", "HU": "Hungary",
    "JP": "Japan", "KR": "South Korea", "CN": "China",
    "TW": "Taiwan", "AU": "Australia", "NZ": "New Zealand",
    "BR": "Brazil", "MX": "Mexico", "AR": "Argentina",
    "CL": "Chile", "CO": "Colombia", "PE": "Peru",
    "ZA": "South Africa", "AE": "United Arab Emirates",
    "SA": "Saudi Arabia", "IL": "Israel", "TR": "Turkey",
    "RU": "Russia", "KY": "Cayman Islands", "BM": "Bermuda",
    "VG": "British Virgin Islands", "PA": "Panama",
    "MU": "Mauritius", "SC": "Seychelles", "MH": "Marshall Islands",
    "GG": "Guernsey", "JE": "Jersey", "IM": "Isle of Man",
    "GI": "Gibraltar", "MT": "Malta", "CY": "Cyprus",
    "LI": "Liechtenstein", "MC": "Monaco", "LU": "Luxembourg",
    "BH": "Bahrain", "QA": "Qatar", "KW": "Kuwait",
    "OM": "Oman",
}


def _build_incorporated_in_edges(company_info: Dict, discovery) -> List[OwnershipEdge]:
    """Build incorporated_in edges from company metadata."""
    edges = []
    for cik, info in company_info.items():
        name = info.get("name", f"CIK {cik}")
        state = info.get("stateOfIncorporation", "")
        if not state:
            continue

        # Map state code to full name
        state_full = _STATE_CODES.get(state.upper(), state)

        company_entity = Entity(
            raw_name=name,
            cleaned_name=name,
            entity_type="company",
            notes=f"CIK: {cik}",
        )
        jurisdiction_entity = Entity(
            raw_name=state_full,
            cleaned_name=state_full,
            entity_type="country",
            notes=f"code: {state}",
        )

        # Create a minimal filing-like object for the edge
        class _MetaFiling:
            accession = f"CIK-{cik}"
            form = "company_info"
            filing_date = ""
            depth = 0

        edge = OwnershipEdge(
            source=company_entity,
            target=jurisdiction_entity,
            relationship="incorporated_in",
            relationship_detail=info.get("sicDescription", ""),
            filing=_MetaFiling(),
            method="company_metadata",
            notes=f"SIC: {info.get('sic', '')} — {info.get('sicDescription', '')}",
            target_jurisdiction=state_full,
            target_risk_tier=get_risk_tier(state_full),
        )
        edges.append(edge)

    return edges


def run_secmap(
    root_cik: str,
    form_types: List[str],
    max_depth: int,
    max_filings_per_cik: int,
    issuer_name_override: Optional[str] = None,
    issuer_country_override: Optional[str] = None,
    xbrl_data_dir: str = "",
    enable_descension: bool = False,
    descension_depth: int = 3,
) -> SECMapResult:
    logger.info("Starting SECMap orchestrator for root CIK %s", root_cik)

    # ===================================================================
    # PHASE 1: Ascension — BFS upward through ownership chains
    # ===================================================================
    logger.info("=" * 60)
    logger.info("PHASE 1: Ascension (upward ownership chain traversal)")
    logger.info("=" * 60)

    # Step 1: Discover CIK universe
    try:
        config = DiscoveryConfig(
            form_types=form_types,
            max_depth=max_depth,
            max_filings_per_cik=max_filings_per_cik,
            max_total_ciks=100,
            only_ascend=True,
        )
        discovery = walk_cik_universe(root_cik, config)
    except Exception as e:
        logger.critical("CIK discovery failed: %s", e)
        raise

    logger.info(
        "CIK discovery complete: %d CIKs visited, %d filings found, %d companies identified",
        len(discovery.visited_ciks),
        len(discovery.filings),
        len(discovery.company_info),
    )

    edges = []

    # Step 1b: Build incorporated_in edges from company metadata
    try:
        inc_edges = _build_incorporated_in_edges(discovery.company_info, discovery)
        edges.extend(inc_edges)
        logger.info("Built %d incorporated_in edges", len(inc_edges))
    except Exception as e:
        logger.error("Failed to build incorporated_in edges: %s", e)

    # Step 2: Process each filing
    for filing in discovery.filings:
        logger.debug(
            "Processing filing %s (%s) for CIK %s",
            filing.accession,
            filing.form,
            filing.cik,
        )

        # Use company name from filing or discovery metadata, not raw CIK
        company_name = (
            issuer_name_override
            or filing.company
            or discovery.company_info.get(filing.cik, {}).get("name", "")
            or filing.cik
        )

        issuer_entity = Entity(
            raw_name=company_name,
            cleaned_name=company_name,
            entity_type="company",
            notes=f"CIK: {filing.cik}",
        )

        # Step 2a: Parse filing into sections
        try:
            sections = parse_filing_to_sections(filing.content)
        except Exception as e:
            logger.error("Failed to parse filing %s: %s", filing.accession, e)
            continue

        # Step 2b: Build role-based edges (people + institutions)
        try:
            role_edges = build_role_relationships_for_filing(
                filing=filing,
                sections=sections,
                issuer_name=company_name,
                issuer_country=issuer_country_override,
            )
            edges.extend(role_edges)
        except Exception as e:
            logger.error("Role relationship construction failed: %s", e)

        # Step 2c: SC-13 beneficial ownership edges (include /A amendments)
        if filing.form.upper() in ("SC 13D", "SC 13G", "SC 13D/A", "SC 13G/A"):
            try:
                # Use the cleaned full_text, not raw HTML
                clean_text = sections.get("full_text", "")
                bo_entries = parse_sc13_beneficial_ownership(clean_text)
                bo_edges = build_beneficial_owner_edges(
                    filing=filing,
                    issuer=issuer_entity,
                    bo_entries=bo_entries,
                    issuer_country=issuer_country_override,
                )
                edges.extend(bo_edges)
            except Exception as e:
                logger.error("SC-13 parsing failed for %s: %s", filing.accession, e)

        # Step 2d: Country association edges
        try:
            country_list = sections.get("countries", "").splitlines()
            country_edges = build_country_association_edges(
                issuer=issuer_entity,
                filing=filing,
                countries=country_list,
            )
            edges.extend(country_edges)
        except Exception as e:
            logger.error("Country association edge construction failed: %s", e)

        # Free the parsed sections to release filing content memory
        del sections

    # Release filing content — the DiscoveredFiling objects hold multi-MB
    # HTML strings that are no longer needed after edge extraction.
    # DiscoveryResult is frozen, so we can't delete .filings directly,
    # but we can let the local reference go out of scope after this point.
    filings_processed_count = len(discovery.filings)

    # ===================================================================
    # PHASE 2: XBRL Enrichment — descension + institution cross-reference
    # ===================================================================
    xbrl_enriched = False
    desc_cik_count = 0
    desc_edge_count = 0
    resolved_inst_count = 0

    # Auto-enable descension if xbrl_data_dir is provided
    if xbrl_data_dir and not enable_descension:
        enable_descension = True

    if enable_descension and xbrl_data_dir:
        logger.info("=" * 60)
        logger.info("PHASE 2: XBRL Enrichment (descension + cross-reference)")
        logger.info("=" * 60)

        try:
            from .xbrl_sub import XBRLSubIndex
            from .descension import descend_from_cik

            # Step 2a: Load XBRL SUB data
            sub_index = XBRLSubIndex()
            if os.path.isdir(xbrl_data_dir):
                sub_index.load_all_months(xbrl_data_dir)
            else:
                logger.warning("XBRL data directory not found: %s", xbrl_data_dir)
                sub_index = None

            if sub_index and sub_index._total_rows > 0:
                xbrl_enriched = True
                xbrl_stats = sub_index.stats()
                logger.info(
                    "XBRL SUB loaded: %d records, %d CIKs, %d periods",
                    xbrl_stats["total_records"],
                    xbrl_stats["unique_ciks"],
                    xbrl_stats["periods_loaded"],
                )

                # Step 2b: Run descension from root CIK
                logger.info("Running descension from root CIK %s (depth=%d)", root_cik, descension_depth)
                desc_result = descend_from_cik(
                    root_cik, sub_index,
                    max_depth=descension_depth,
                )
                desc_cik_count = len(desc_result.visited_ciks) - 1  # exclude root
                desc_edge_count = len(desc_result.edges)
                edges.extend(desc_result.edges)

                logger.info(
                    "Descension: %d subsidiary CIKs, %d edges",
                    desc_cik_count, desc_edge_count,
                )

                # Also descend from every CIK visited during ascension
                for visited_cik in discovery.visited_ciks:
                    if visited_cik == root_cik:
                        continue
                    try:
                        sub_desc = descend_from_cik(
                            visited_cik, sub_index,
                            max_depth=max(1, descension_depth - 1),
                        )
                        if sub_desc.edges:
                            edges.extend(sub_desc.edges)
                            desc_cik_count += len(sub_desc.visited_ciks) - 1
                            desc_edge_count += len(sub_desc.edges)
                            logger.debug(
                                "Descension from visited CIK %s: %d edges",
                                visited_cik, len(sub_desc.edges),
                            )
                    except Exception as e:
                        logger.debug("Descension failed for CIK %s: %s", visited_cik, e)

                # Step 2c: Cross-reference institution names against XBRL SUB
                # Find institution entities from ascension edges that can be
                # resolved to CIKs via the XBRL SUB name index
                inst_names = set()
                for edge in edges:
                    if edge.relationship == "institution_role":
                        inst_names.add(edge.source.cleaned_name)

                for inst_name in inst_names:
                    try:
                        matches = sub_index.search(inst_name)
                        if matches and len(matches) == 1:
                            match = matches[0]
                            # Only resolve if the match is a strong name match
                            if match.name.upper() == inst_name.upper():
                                resolved_inst_count += 1
                                logger.debug(
                                    "XBRL resolved institution '%s' -> CIK %s",
                                    inst_name, match.cik,
                                )
                                # If this CIK wasn't visited, descend into it
                                if match.cik not in discovery.visited_ciks:
                                    try:
                                        inst_desc = descend_from_cik(
                                            match.cik, sub_index, max_depth=1,
                                        )
                                        if inst_desc.edges:
                                            edges.extend(inst_desc.edges)
                                            desc_edge_count += len(inst_desc.edges)
                                    except Exception:
                                        pass
                    except Exception as e:
                        logger.debug("XBRL cross-ref failed for '%s': %s", inst_name, e)

                logger.info(
                    "XBRL enrichment complete: %d descension CIKs, %d descension edges, "
                    "%d institutions resolved",
                    desc_cik_count, desc_edge_count, resolved_inst_count,
                )

        except ImportError as e:
            logger.warning("XBRL modules not available, skipping enrichment: %s", e)
        except Exception as e:
            logger.error("XBRL enrichment failed: %s", e)

    # ===================================================================
    # PHASE 3: Deduplication
    # ===================================================================
    logger.info("=" * 60)
    logger.info("PHASE 3: Deduplication")
    logger.info("=" * 60)

    # Step 3: Deduplicate edges
    try:
        deduped_edges = merge_and_deduplicate_edges(edges)
    except Exception as e:
        logger.error("Edge deduplication failed: %s", e)
        deduped_edges = edges

    logger.info(
        "SECMap completed: %d raw edges -> %d deduplicated edges%s",
        len(edges),
        len(deduped_edges),
        f" (incl. {desc_edge_count} descension)" if desc_edge_count else "",
    )

    return SECMapResult(
        root_cik=discovery.root_cik,
        visited_ciks=discovery.visited_ciks,
        filings_processed=filings_processed_count,
        edges=deduped_edges,
        company_info=discovery.company_info,
        xbrl_enriched=xbrl_enriched,
        descension_ciks=desc_cik_count,
        descension_edges=desc_edge_count,
        xbrl_resolved_institutions=resolved_inst_count,
    )
