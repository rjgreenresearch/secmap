"""
relationship_builder.py

Extracts people, institutions, and their roles from filing sections,
then constructs typed role relationships for the ownership_edges layer.

Enhancements:
- Full logging
- Input validation
- Exception-safe extraction
- Deterministic behavior
- Clear separation of concerns
"""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

from .entity_classification import Entity
from .role_taxonomy import classify_role, RoleClassification
from .people_extractor import extract_people_from_signatures, extract_people_from_narrative
from .institution_extractor import extract_institutions_from_narrative
from .ownership_edges import (
    build_person_role_edges,
    build_institution_role_edges,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_extract_people(sections: Dict[str, str]) -> List[Tuple[Entity, RoleClassification]]:
    """
    Extract people from signature and narrative sections.
    Exception-safe wrapper.
    """
    results: List[Tuple[Entity, RoleClassification]] = []

    try:
        # Search for /s/ patterns in both the signature section AND full text,
        # since HTML stripping often prevents clean signature block extraction
        sig_text = sections.get("signatures", "")
        full_text = sections.get("full_text", "")
        combined_sig_text = sig_text + "\n" + full_text if full_text != sig_text else sig_text
        sig_people = extract_people_from_signatures(combined_sig_text)
        logger.debug("Extracted %d people from signatures", len(sig_people))
    except Exception as e:
        logger.error("Failed to extract people from signatures: %s", e)
        sig_people = []

    try:
        narrative_people = extract_people_from_narrative(sections.get("narrative", ""))
        logger.debug("Extracted %d people from narrative", len(narrative_people))
    except Exception as e:
        logger.error("Failed to extract people from narrative: %s", e)
        narrative_people = []

    # Combine and classify roles
    for person in sig_people + narrative_people:
        try:
            context = sections.get("full_text", "") or sections.get("narrative", "")
            role = classify_role(person.raw_name, context)
            results.append((person, role))
        except Exception as e:
            logger.error("Role classification failed for %s: %s", person.raw_name, e)

    return results


def _safe_extract_institutions(sections: Dict[str, str]) -> List[Tuple[Entity, RoleClassification]]:
    """
    Extract institutions from narrative sections.
    Exception-safe wrapper.
    """
    try:
        inst = extract_institutions_from_narrative(sections.get("narrative", ""))
        logger.debug("Extracted %d institutions from narrative", len(inst))
        return inst
    except Exception as e:
        logger.error("Failed to extract institutions: %s", e)
        return []


# ---------------------------------------------------------------------------
# Main API
# ---------------------------------------------------------------------------

def build_role_relationships_for_filing(
    filing,
    sections: Dict[str, str],
    issuer_name: str | None = None,
    issuer_country: str | None = None,
):
    """
    Build all role-based edges (people + institutions) for a single filing.

    Returns:
        List[OwnershipEdge]
    """
    if not filing or not sections:
        logger.warning("build_role_relationships_for_filing() received empty input")
        return []

    logger.debug(
        "Building role relationships for filing %s (%s)",
        filing.accession,
        filing.form,
    )

    # Construct issuer entity
    issuer_clean = issuer_name or filing.cik
    issuer_entity = Entity(
        raw_name=issuer_clean,
        cleaned_name=issuer_clean,
        entity_type="company",
        notes=None,
    )

    # Extract people and institutions
    people = _safe_extract_people(sections)
    institutions = _safe_extract_institutions(sections)

    logger.debug(
        "Total extracted: %d people, %d institutions",
        len(people),
        len(institutions),
    )

    # Build edges
    edges = []

    try:
        person_edges = build_person_role_edges(
            filing=filing,
            issuer=issuer_entity,
            people=people,
            issuer_country=issuer_country,
        )
        edges.extend(person_edges)
    except Exception as e:
        logger.error("Failed to build person role edges: %s", e)

    try:
        inst_edges = build_institution_role_edges(
            filing=filing,
            issuer=issuer_entity,
            institutions=institutions,
            issuer_country=issuer_country,
        )
        edges.extend(inst_edges)
    except Exception as e:
        logger.error("Failed to build institution role edges: %s", e)

    logger.debug(
        "Built %d role edges for filing %s",
        len(edges),
        filing.accession,
    )

    return edges
