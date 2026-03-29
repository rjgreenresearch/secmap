"""
ownership_edges.py

Defines the OwnershipEdge dataclass and helper functions for constructing
edges between entities (people, institutions, companies, countries) based on
parsed SEC filings.

Each edge now carries full chain-analysis metadata:
- Source jurisdiction and risk tier
- State affiliation category and subcategory
- Role semantic flags (executive, board, ownership, obscuring)
- Chain depth from the filing

Enhancements:
- Full logging
- Input validation
- Exception-safe edge construction
- Deterministic deduplication
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple

from .entity_classification import Entity
from .role_taxonomy import RoleClassification
from .jurisdiction_inference import (
    infer_jurisdiction,
    infer_jurisdiction_with_risk,
    get_risk_tier,
)
from .state_affiliation import classify_state_affiliation
from .sc13_parser import BeneficialOwnershipEntry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclass representing a single ownership or governance relationship
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OwnershipEdge:
    source: Entity
    target: Entity
    relationship: str
    relationship_detail: str
    filing: object
    method: Optional[str] = None
    notes: Optional[str] = None
    # --- chain-analysis fields ---
    source_jurisdiction: Optional[str] = None
    source_risk_tier: Optional[str] = None
    target_jurisdiction: Optional[str] = None
    target_risk_tier: Optional[str] = None
    state_affiliation: Optional[str] = None
    state_affiliation_sub: Optional[str] = None
    state_affiliation_detail: Optional[str] = None
    role_is_executive: bool = False
    role_is_board: bool = False
    role_is_ownership: bool = False
    role_is_obscuring: bool = False
    chain_depth: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_jurisdiction(name: str, country_override: Optional[str] = None):
    """Return (country, risk_tier) tuple."""
    result = infer_jurisdiction_with_risk(name, issuer_country=country_override)
    if result:
        return result.country, result.risk_tier
    return None, None


def _build_state_fields(name: str, role, issuer_country: Optional[str]):
    """Return (category, subcategory, detail) from state affiliation."""
    aff = classify_state_affiliation(name=name, role=role, issuer_country=issuer_country)
    if aff.category != "None":
        return aff.category, aff.subcategory, aff.details
    return None, None, None


# ---------------------------------------------------------------------------
# Person -> Issuer role edges
# ---------------------------------------------------------------------------

def build_person_role_edges(
    filing,
    issuer: Entity,
    people: List[Tuple[Entity, RoleClassification]],
    issuer_country: Optional[str] = None,
) -> List[OwnershipEdge]:
    edges: List[OwnershipEdge] = []

    if not people:
        logger.debug("No people provided for person_role edges")
        return edges

    target_jur, target_tier = _resolve_jurisdiction(issuer.cleaned_name, issuer_country)

    for person_entity, role_cls in people:
        try:
            src_jur, src_tier = _resolve_jurisdiction(person_entity.cleaned_name)
            sa_cat, sa_sub, sa_detail = _build_state_fields(
                person_entity.cleaned_name, role_cls, target_jur,
            )

            notes_parts = ["method: signature_or_narrative"]
            if sa_cat:
                notes_parts.append(f"state_affiliation: {sa_cat}")
                if sa_sub:
                    notes_parts.append(f"subcategory: {sa_sub}")
                if sa_detail:
                    notes_parts.append(sa_detail)

            depth = getattr(filing, "depth", 0)

            edge = OwnershipEdge(
                source=person_entity,
                target=issuer,
                relationship="person_role",
                relationship_detail=role_cls.canonical_role,
                filing=filing,
                method="role_extraction",
                notes="; ".join(notes_parts),
                source_jurisdiction=src_jur,
                source_risk_tier=src_tier,
                target_jurisdiction=target_jur,
                target_risk_tier=target_tier,
                state_affiliation=sa_cat,
                state_affiliation_sub=sa_sub,
                state_affiliation_detail=sa_detail,
                role_is_executive=role_cls.is_executive,
                role_is_board=role_cls.is_board,
                role_is_ownership=role_cls.is_ownership,
                role_is_obscuring=role_cls.is_obscuring,
                chain_depth=depth,
            )
            edges.append(edge)

        except Exception as e:
            logger.error("Failed to build person_role edge for %s: %s", person_entity.cleaned_name, e)

    logger.debug("Built %d person_role edges", len(edges))
    return edges


# ---------------------------------------------------------------------------
# Institution -> Issuer role edges
# ---------------------------------------------------------------------------

def build_institution_role_edges(
    filing,
    issuer: Entity,
    institutions: List[Tuple[Entity, RoleClassification]],
    issuer_country: Optional[str] = None,
) -> List[OwnershipEdge]:
    edges: List[OwnershipEdge] = []

    if not institutions:
        logger.debug("No institutions provided for institution_role edges")
        return edges

    target_jur, target_tier = _resolve_jurisdiction(issuer.cleaned_name, issuer_country)

    for inst_entity, role_cls in institutions:
        try:
            src_jur, src_tier = _resolve_jurisdiction(inst_entity.cleaned_name)
            sa_cat, sa_sub, sa_detail = _build_state_fields(
                inst_entity.cleaned_name, role_cls, target_jur,
            )

            notes_parts = ["method: signature_or_narrative"]
            if sa_cat:
                notes_parts.append(f"state_affiliation: {sa_cat}")
                if sa_sub:
                    notes_parts.append(f"subcategory: {sa_sub}")
                if sa_detail:
                    notes_parts.append(sa_detail)

            depth = getattr(filing, "depth", 0)

            edge = OwnershipEdge(
                source=inst_entity,
                target=issuer,
                relationship="institution_role",
                relationship_detail=role_cls.canonical_role,
                filing=filing,
                method="role_extraction",
                notes="; ".join(notes_parts),
                source_jurisdiction=src_jur,
                source_risk_tier=src_tier,
                target_jurisdiction=target_jur,
                target_risk_tier=target_tier,
                state_affiliation=sa_cat,
                state_affiliation_sub=sa_sub,
                state_affiliation_detail=sa_detail,
                role_is_executive=role_cls.is_executive,
                role_is_board=role_cls.is_board,
                role_is_ownership=role_cls.is_ownership,
                role_is_obscuring=role_cls.is_obscuring,
                chain_depth=depth,
            )
            edges.append(edge)

        except Exception as e:
            logger.error("Failed to build institution_role edge for %s: %s", inst_entity.cleaned_name, e)

    logger.debug("Built %d institution_role edges", len(edges))
    return edges


# ---------------------------------------------------------------------------
# Beneficial Owner (SC 13D/G) edges
# ---------------------------------------------------------------------------

def build_beneficial_owner_edges(
    filing,
    issuer: Entity,
    bo_entries: List[BeneficialOwnershipEntry],
    issuer_country: Optional[str] = None,
) -> List[OwnershipEdge]:
    edges: List[OwnershipEdge] = []

    if not bo_entries:
        logger.debug("No beneficial ownership entries provided")
        return edges

    target_jur, target_tier = _resolve_jurisdiction(issuer.cleaned_name, issuer_country)

    for entry in bo_entries:
        try:
            holder = entry.reporting_person
            src_jur, src_tier = _resolve_jurisdiction(holder.cleaned_name)
            sa_cat, sa_sub, sa_detail = _build_state_fields(
                holder.cleaned_name, None, target_jur,
            )

            notes_parts = ["method: sc13"]
            if entry.notes:
                notes_parts.append(entry.notes)
            if sa_cat:
                notes_parts.append(f"state_affiliation: {sa_cat}")
                if sa_sub:
                    notes_parts.append(f"subcategory: {sa_sub}")
                if sa_detail:
                    notes_parts.append(sa_detail)

            detail = ""
            if entry.percent_of_class is not None:
                detail = f"{entry.percent_of_class}%"
                if entry.class_title:
                    detail += f" of {entry.class_title}"

            depth = getattr(filing, "depth", 0)

            edge = OwnershipEdge(
                source=holder,
                target=issuer,
                relationship="beneficial_owner",
                relationship_detail=detail,
                filing=filing,
                method="sc13",
                notes="; ".join(notes_parts),
                source_jurisdiction=src_jur,
                source_risk_tier=src_tier,
                target_jurisdiction=target_jur,
                target_risk_tier=target_tier,
                state_affiliation=sa_cat,
                state_affiliation_sub=sa_sub,
                state_affiliation_detail=sa_detail,
                role_is_ownership=True,
                chain_depth=depth,
            )
            edges.append(edge)

        except Exception as e:
            logger.error("Failed to build beneficial_owner edge: %s", e)

    logger.debug("Built %d beneficial_owner edges", len(edges))
    return edges


# ---------------------------------------------------------------------------
# Country association edges
# ---------------------------------------------------------------------------

def build_country_association_edges(
    issuer: Entity,
    filing,
    countries: List[str],
) -> List[OwnershipEdge]:
    edges: List[OwnershipEdge] = []

    if not countries:
        logger.debug("No countries provided for country_association edges")
        return edges

    for country in countries:
        try:
            country_entity = Entity(
                raw_name=country,
                cleaned_name=country,
                entity_type="country",
                notes=None,
            )

            country_tier = get_risk_tier(country)
            depth = getattr(filing, "depth", 0)

            edge = OwnershipEdge(
                source=issuer,
                target=country_entity,
                relationship="country_association",
                relationship_detail="",
                filing=filing,
                method="country_extraction",
                notes=None,
                target_jurisdiction=country,
                target_risk_tier=country_tier,
                chain_depth=depth,
            )
            edges.append(edge)

        except Exception as e:
            logger.error("Failed to build country_association edge for %s: %s", country, e)

    logger.debug("Built %d country_association edges", len(edges))
    return edges


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def merge_and_deduplicate_edges(edges: List[OwnershipEdge]) -> List[OwnershipEdge]:
    """Deduplicate edges using a deterministic key."""
    if not edges:
        return []

    seen: Dict[Tuple, OwnershipEdge] = {}

    for e in edges:
        try:
            key = (
                e.source.cleaned_name,
                e.source.entity_type,
                e.target.cleaned_name,
                e.target.entity_type,
                e.relationship,
                e.relationship_detail,
                e.filing.accession,
            )

            if key in seen:
                existing = seen[key]
                if e.notes and e.notes not in (existing.notes or ""):
                    merged = existing.notes + "; " + e.notes if existing.notes else e.notes
                    seen[key] = OwnershipEdge(
                        source=existing.source,
                        target=existing.target,
                        relationship=existing.relationship,
                        relationship_detail=existing.relationship_detail,
                        filing=existing.filing,
                        method=existing.method,
                        notes=merged,
                        source_jurisdiction=existing.source_jurisdiction or e.source_jurisdiction,
                        source_risk_tier=existing.source_risk_tier or e.source_risk_tier,
                        target_jurisdiction=existing.target_jurisdiction or e.target_jurisdiction,
                        target_risk_tier=existing.target_risk_tier or e.target_risk_tier,
                        state_affiliation=existing.state_affiliation or e.state_affiliation,
                        state_affiliation_sub=existing.state_affiliation_sub or e.state_affiliation_sub,
                        state_affiliation_detail=existing.state_affiliation_detail or e.state_affiliation_detail,
                        role_is_executive=existing.role_is_executive or e.role_is_executive,
                        role_is_board=existing.role_is_board or e.role_is_board,
                        role_is_ownership=existing.role_is_ownership or e.role_is_ownership,
                        role_is_obscuring=existing.role_is_obscuring or e.role_is_obscuring,
                        chain_depth=min(existing.chain_depth, e.chain_depth),
                    )
            else:
                seen[key] = e

        except Exception as ex:
            logger.error("Failed to deduplicate edge %r: %s", e, ex)

    logger.info("Deduplicated %d -> %d edges", len(edges), len(seen))
    return list(seen.values())
