"""
people_extractor.py

Extracts person entities from SEC filings using POSITIONAL extraction —
names are only pulled from specific structural locations where person
names are expected to appear:

1. Signature blocks: /s/ Name, By: Name
2. Name, age XX patterns (director/officer sections)
3. Title-adjacent patterns (Name, Title or Title: Name)

This avoids the false-positive problem of scanning the entire filing
text with generic capitalized-word regexes.
"""

from __future__ import annotations

import logging
import re
from typing import List, Tuple, Optional

from .entity_classification import make_entity, Entity

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Organization suffixes — reject if present
# ---------------------------------------------------------------------------

_ORG_SUFFIXES = {
    "llc", "l.l.c.", "lp", "l.p.", "llp", "l.l.p.",
    "inc", "inc.", "incorporated", "corp", "corp.", "corporation",
    "ltd", "ltd.", "limited", "co", "co.", "company",
    "partners", "capital", "holdings", "group", "fund", "trust",
    "bank", "gmbh", "s.a.", "b.v.", "n.v.", "ag",
    "management", "advisors", "association",
}

# ---------------------------------------------------------------------------
# Name validation
# ---------------------------------------------------------------------------

def _is_valid_person_name(name: str) -> bool:
    if not name:
        return False

    n = re.sub(r"\s+", " ", name).strip().rstrip(".,;:")

    if len(n) < 4 or len(n) > 60:
        return False

    # Must have at least 2 tokens
    parts = n.split()
    if len(parts) < 2:
        return False

    # Reject digits
    if any(ch.isdigit() for ch in n):
        return False

    # Reject non-name characters
    if re.search(r"[^A-Za-z.\-' ]", n):
        return False

    # Reject if any token is an org suffix
    if any(tok.lower() in _ORG_SUFFIXES for tok in parts):
        return False

    # Reject if first token is a single letter (stray initial)
    if len(parts[0]) == 1 and not parts[0].endswith("."):
        return False

    # Reject broken Roman numeral fragments (e.g., "Spencer F Iii")
    roman = {"ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "jr", "sr"}
    if parts[-1].lower().rstrip(".") in roman and len(parts) >= 2 and len(parts[-2]) <= 2:
        return False

    return True


# ---------------------------------------------------------------------------
# Signature block extraction: /s/ Name and By: Name
# ---------------------------------------------------------------------------

# Title keywords that commonly follow names in /s/ blocks (no space separator)
_TITLE_STOPS = [
    "Chief", "President", "Director", "Chairman", "Chairwoman",
    "Secretary", "Treasurer", "Officer", "Principal", "Attorney",
    "Managing", "General", "Deputy", "Senior", "Executive",
    "Vice", "Supervisory", "Auditor", "Controller", "Comptroller",
    "Partner", "Trustee", "Counsel",
    "Name", "Title", "Date", "March", "April", "May", "June",
    "July", "August", "September", "October", "November",
    "December", "January", "February",
    "Pursuant", "We ", "The ",
]
_TITLE_STOP_PATTERN = "|".join(re.escape(t) for t in _TITLE_STOPS)

# /s/ Name — name ends at a title keyword, date, or newline
_SIG_RE = re.compile(
    r"/s/\s*([A-Z][A-Za-z.\-' ]{2,50}?)(?=" + _TITLE_STOP_PATTERN + r"|\n|\r|\(|$)",
)

# By: Name
_BY_RE = re.compile(
    r"By:\s*/?s?/?\s*([A-Z][A-Za-z.\-' ]{2,50}?)(?=" + _TITLE_STOP_PATTERN + r"|\n|\r|\(|$)",
)


def _extract_from_signatures(text: str) -> List[str]:
    """Extract names from /s/ and By: patterns."""
    names = []
    for pattern in [_SIG_RE, _BY_RE]:
        for m in pattern.finditer(text):
            name = m.group(1).strip().rstrip(".,;:")
            if _is_valid_person_name(name):
                names.append(name)
    return names


# ---------------------------------------------------------------------------
# Name, age XX pattern (director/officer bios)
# ---------------------------------------------------------------------------

_NAME_AGE_RE = re.compile(
    r"([A-Z][a-z]+(?:\s[A-Z]\.?)?\s(?:[A-Z][a-z]+\s?)+)\s*,\s*(?:age\s+|Age\s+|AGE\s+)?(\d{2})\s*[,.]",
)


def _extract_from_name_age(text: str) -> List[str]:
    """Extract names from 'Name, age XX' patterns in director sections."""
    names = []
    for m in _NAME_AGE_RE.finditer(text):
        name = m.group(1).strip()
        if _is_valid_person_name(name):
            names.append(name)
    return names


# ---------------------------------------------------------------------------
# Title-adjacent patterns (limited to known title keywords)
# ---------------------------------------------------------------------------

_TITLE_KEYWORDS = [
    "chief executive officer", "chief financial officer",
    "chief operating officer", "chief technology officer",
    "chairman", "chairwoman", "chairperson",
    "director", "president", "vice president",
    "secretary", "treasurer", "general counsel",
    "managing director", "general manager",
    "deputy general manager", "deputy director",
    "deputy chairman", "deputy president",
]

_TITLE_PATTERN = "|".join(re.escape(t) for t in _TITLE_KEYWORDS)

# Name, Title
_NAME_TITLE_RE = re.compile(
    rf"([A-Z][a-z]+(?:\s[A-Z]\.?)?\s(?:[A-Z][a-z]+\s?){{1,3}})\s*[,\-\u2014\u2013]+\s*({_TITLE_PATTERN})",
    re.IGNORECASE,
)

# Title: Name
_TITLE_NAME_RE = re.compile(
    rf"({_TITLE_PATTERN})\s*[:\-\u2014\u2013]+\s*([A-Z][a-z]+(?:\s[A-Z]\.?)?\s(?:[A-Z][a-z]+\s?){{1,3}})",
    re.IGNORECASE,
)


def _extract_from_title_adjacency(text: str) -> List[str]:
    """Extract names that appear adjacent to known title keywords."""
    names = []
    for m in _NAME_TITLE_RE.finditer(text):
        name = m.group(1).strip()
        if _is_valid_person_name(name):
            names.append(name)
    for m in _TITLE_NAME_RE.finditer(text):
        name = m.group(2).strip()
        if _is_valid_person_name(name):
            names.append(name)
    return names


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _dedupe(names: List[str]) -> List[str]:
    seen = set()
    unique = []
    for n in names:
        n = n.strip()
        key = n.lower()
        if key not in seen:
            seen.add(key)
            unique.append(n)
    return unique


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_people_from_signatures(text: str) -> List[Entity]:
    """Extract people from signature blocks using /s/ and By: patterns."""
    if not text:
        return []

    try:
        names = _extract_from_signatures(text)
        names = _dedupe(names)
        entities = [make_entity(n, explicit_type="person") for n in names]
        logger.debug("Signature extraction produced %d people", len(entities))
        return entities
    except Exception as e:
        logger.error("extract_people_from_signatures() failed: %s", e)
        return []


def extract_people_from_narrative(text: str) -> List[Entity]:
    """Extract people from narrative sections using structural patterns."""
    if not text:
        return []

    try:
        names = []
        names.extend(_extract_from_name_age(text))
        names.extend(_extract_from_title_adjacency(text))
        names = _dedupe(names)
        entities = [make_entity(n, explicit_type="person") for n in names]
        logger.debug("Narrative extraction produced %d people", len(entities))
        return entities
    except Exception as e:
        logger.error("extract_people_from_narrative() failed: %s", e)
        return []
