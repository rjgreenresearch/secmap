"""
institution_extractor.py

Extracts institution entities from narrative sections of SEC filings.

Enhancements:
- Full logging
- Deterministic regex-based extraction
- Robust handling of corporate suffixes
- Conservative filtering to avoid false positives
- Exception-safe fallbacks
"""

from __future__ import annotations

import logging
import re
from typing import List, Tuple

from .entity_classification import make_entity, Entity
from .role_taxonomy import RoleClassification

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Corporate suffix patterns
# ---------------------------------------------------------------------------

_CORPORATE_SUFFIXES = [
    "LLC", "L.L.C.",
    "LP", "L.P.",
    "LLP", "L.L.P.",
    "Inc", "Inc.", "Incorporated",
    "Corp", "Corp.", "Corporation",
    "Ltd", "Ltd.", "Limited",
    "Co", "Co.", "Company",
    "Partners", "Capital", "Holdings",
    "Asset Management", "Management",
    "Trust", "Bank", "Group",
]

# Build a regex that matches institution-like names
# Example: "ABC Capital Partners LP", "XYZ Asset Management Co., Ltd."
_SUFFIX_PATTERN = r"(?:{})(?:\b|$)".format("|".join([re.escape(s) for s in _CORPORATE_SUFFIXES]))

_INSTITUTION_RE = re.compile(
    rf"\b([A-Z][A-Za-z0-9&.,'()\- ]+?\s{_SUFFIX_PATTERN})",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_institution_names(text: str) -> List[str]:
    if not text:
        return []

    try:
        matches = _INSTITUTION_RE.findall(text)
        names = []

        for m in matches:
            if isinstance(m, tuple):
                names.append(m[0])
            else:
                names.append(m)

        # Deduplicate, length-filter, and reject sentence fragments
        seen = set()
        unique = []
        for n in names:
            cleaned = n.strip()
            # Reject too long (sentence fragments) or too short
            if len(cleaned) > 80 or len(cleaned) < 5:
                continue
            # Reject if it starts with a lowercase word (sentence fragment)
            if cleaned[0].islower():
                continue
            # Reject if it contains common sentence starters
            lower = cleaned.lower()
            if any(lower.startswith(p) for p in [
                "indicate ", "see ", "if ", "the ", "this ", "and ",
                "or ", "we ", "our ", "a ", "an ", "as ",
                "named ", "makes ", "time ", "effect ",
                "employee ", "revoked ",
            ]):
                continue
            if cleaned not in seen:
                seen.add(cleaned)
                unique.append(cleaned)

        logger.debug("Extracted %d unique institution names", len(unique))
        return unique

    except Exception as e:
        logger.error("Institution regex extraction failed: %s", e)
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_institutions_from_narrative(text: str) -> List[Tuple[Entity, RoleClassification]]:
    """
    Extract institutions from narrative sections.

    Returns:
        List of (Entity, RoleClassification)
    """
    if not text:
        return []

    try:
        names = _extract_institution_names(text)

        # Institutions do not have roles until role_taxonomy classifies them
        # We attach a placeholder RoleClassification("Unknown")
        results = [
            (make_entity(n, explicit_type="institution"), RoleClassification("Unknown"))
            for n in names
        ]

        logger.debug("Narrative extraction produced %d institutions", len(results))
        return results

    except Exception as e:
        logger.error("extract_institutions_from_narrative() failed: %s", e)
        return []
