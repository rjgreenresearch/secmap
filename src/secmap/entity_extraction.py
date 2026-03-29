"""
Entity extraction, person/org classification, and name cleanup.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .role_taxonomy import RoleClassification


ORG_KEYWORDS = [
    "institute",
    "foundation",
    "society",
    "university",
    "college",
    "research",
    "center",
    "centre",
    "bank",
    "group",
    "co.",
    "company",
    "corp",
    "corporation",
    "limited",
    "ltd",
    "inc",
    "holding",
    "holdings",
    "committee",
    "commission",
    "bureau",
    "ministry",
    "department",
    "office",
    "academy",
    "association",
    "council",
]


TITLE_PREFIXES = [
    "the",
    "chief",
    "deputy",
    "vice",
    "senior",
    "executive",
    "assistant",
    "associate",
    "acting",
    "interim",
    "supervisors",
    "foundation",
    "society",
    "institute",
    "committee",
    "board",
    "stock",
    "sales",
    "product",
    "mix",
    "total",
]

TITLE_SUFFIXES = [
    "chairman",
    "director",
    "supervisor",
    "president",
    "economist",
    "officer",
    "secretary",
    "member",
    "partner",
    "trustee",
    "counsel",
]


@dataclass
class Entity:
    raw_name: str
    cleaned_name: str
    entity_type: str  # "person", "organization", "institution", "government", "unknown"
    notes: Optional[str] = None


def _normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def clean_person_name(raw_name: str) -> str:
    """
    Normalize person names:
    - strip 'Name' artifacts
    - trim whitespace and punctuation
    - reject obvious non-name patterns by returning empty string
    """
    if not raw_name:
        return ""

    n = _normalize_whitespace(raw_name)
    n = n.rstrip(".,;:")

    # Remove leading "Name:" or "Name -"
    n = re.sub(r"^(name\s*[:\-]\s*)", "", n, flags=re.IGNORECASE)

    # Remove trailing "Name"
    tokens = n.split()
    if tokens and tokens[-1].lower() == "name":
        n = " ".join(tokens[:-1]).strip()

    n = n.strip().rstrip(".,;:")

    # Reject too short or too long
    if len(n) < 3 or len(n) > 80:
        return ""

    # Reject digits
    if any(ch.isdigit() for ch in n):
        return ""

    # Reject weird characters
    if re.search(r"[^A-Za-z\.\-\' ]", n):
        return ""

    parts = n.split()
    if len(parts) < 2:
        # Single-token names are too ambiguous for this pipeline
        return ""

    # Reject if starts with a title-like prefix
    if parts[0].lower() in TITLE_PREFIXES:
        return ""

    # Reject if ends with a title-like suffix
    if parts[-1].lower() in TITLE_SUFFIXES:
        return ""

    return n


def _looks_like_org(raw_name: str) -> bool:
    n = _normalize_whitespace(raw_name).lower()
    return any(k in n for k in ORG_KEYWORDS)


def infer_entity_type(
    raw_name: str,
    role: Optional[RoleClassification] = None,
) -> str:
    """
    Infer 'person' vs 'organization' vs 'institution' vs 'government' using
    org keywords and role context.
    """
    if not raw_name:
        return "unknown"

    n = _normalize_whitespace(raw_name)

    # Government-ish hints
    gov_tokens = [
        "ministry",
        "bureau",
        "commission",
        "department",
        "office",
        "municipal",
        "provincial",
        "people's government",
    ]
    lower = n.lower()
    if any(t in lower for t in gov_tokens):
        return "government"

    # Org/institution hints
    if _looks_like_org(n):
        # Distinguish institution vs commercial org lightly
        inst_tokens = [
            "institute",
            "foundation",
            "society",
            "academy",
            "association",
            "university",
            "college",
            "research",
            "center",
            "centre",
        ]
        if any(t in lower for t in inst_tokens):
            return "institution"
        return "organization"

    # Role context: if role is clearly corporate, default to person
    if role is not None:
        if role.is_executive or role.is_board or role.is_supervisory:
            return "person"
        if role.is_state_affiliated:
            # Could be government or person; we bias to person here
            return "person"

    # Fallback: try to clean as a person name
    cleaned = clean_person_name(n)
    if cleaned:
        return "person"

    return "unknown"


def classify_entity(
    raw_name: str,
    role: Optional[RoleClassification] = None,
) -> Entity:
    """
    Return a fully classified Entity object.
    """
    entity_type = infer_entity_type(raw_name, role)

    if entity_type == "person":
        cleaned = clean_person_name(raw_name)
    else:
        cleaned = _normalize_whitespace(raw_name)

    return Entity(
        raw_name=raw_name,
        cleaned_name=cleaned,
        entity_type=entity_type,
        notes=None,
    )
