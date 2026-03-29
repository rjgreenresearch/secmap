"""
entity_classification.py

Defines the Entity dataclass and basic classification / normalization
utilities for SECMap.

Enhancements:
- Full logging
- Deterministic normalization
- Simple, explicit classification heuristics
- Exception-safe helpers
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Entity:
    raw_name: str
    cleaned_name: str
    entity_type: str  # "person", "company", "institution", "country", etc.
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """
    Normalize an entity name:
    - Strip leading/trailing whitespace
    - Collapse internal whitespace
    """
    if not name:
        logger.warning("normalize_name() received empty name")
        return ""

    try:
        name = name.strip()
        name = _WHITESPACE_RE.sub(" ", name)
        return name
    except Exception as e:
        logger.error("normalize_name() failed for %r: %s", name, e)
        return name.strip()


# ---------------------------------------------------------------------------
# Classification heuristics
# ---------------------------------------------------------------------------

_INSTITUTION_KEYWORDS = [
    "BANK",
    "TRUST",
    "FUND",
    "CAPITAL",
    "PARTNERS",
    "LLC",
    "LTD",
    "LIMITED",
    "CORP",
    "CORPORATION",
    "INC",
    "HOLDINGS",
    "INVESTMENT",
    "ASSET MANAGEMENT",
]

_PERSON_LIKE_PATTERN = re.compile(r"^[A-Z][a-z]+(?: [A-Z]\.)?(?: [A-Z][a-z]+)+$")


def classify_entity_type(name: str) -> str:
    """
    Classify an entity as 'person', 'institution', or 'unknown'
    using simple, deterministic heuristics.
    """
    cleaned = normalize_name(name)
    if not cleaned:
        return "unknown"

    upper = cleaned.upper()

    # Institution keywords
    for kw in _INSTITUTION_KEYWORDS:
        if kw in upper:
            return "institution"

    # Person-like pattern (First Last, First M. Last, etc.)
    if _PERSON_LIKE_PATTERN.match(cleaned):
        return "person"

    return "unknown"


def make_entity(name: str, explicit_type: Optional[str] = None, notes: Optional[str] = None) -> Entity:
    """
    Factory to create an Entity with normalized name and classified type.

    If explicit_type is provided, it is used as-is; otherwise, heuristics
    are applied via classify_entity_type().
    """
    cleaned = normalize_name(name)
    if explicit_type:
        etype = explicit_type
    else:
        etype = classify_entity_type(cleaned)

    return Entity(
        raw_name=name,
        cleaned_name=cleaned,
        entity_type=etype,
        notes=notes,
    )
