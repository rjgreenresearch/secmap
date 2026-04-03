"""
sc13_parser.py

Parses Schedule 13D / 13G filings to extract beneficial ownership
information from the structured cover page format.

SC 13D/G filings have a repeating cover page structure:
  1. NAME OF REPORTING PERSON
     {name}
  2. CHECK THE APPROPRIATE BOX...
  ...
  11. PERCENT OF CLASS
     {percent}%
  ...
  13. TITLE OF CLASS
     {class title}

Each reporting person gets their own cover page block.
This parser extracts the name from field 1, percent from field 11,
and class title from field 13 for each cover page.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List, Optional

from .entity_classification import Entity

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BeneficialOwnershipEntry:
    reporting_person: Entity
    percent_of_class: Optional[float]
    class_title: Optional[str]
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Cover page block extraction
# ---------------------------------------------------------------------------

# Find each "NAME OF REPORTING PERSON" block -- the name is on the
# next non-empty, non-label line (may be separated by IRS ID line, blanks)
_COVER_PAGE_RE = re.compile(
    r"NAME\s+OF\s+REPORTING\s+PERSON[S]?"
    r"(?:\s*(?:I\.?R\.?S\.?\s*IDENTIFICATION[^\n]*)?)"
    r"[\s\n]*"
    r"([^\n]{4,80})",
    re.IGNORECASE,
)

# Also try simpler format without IRS line
_REPORTING_PERSON_ALT_RE = re.compile(
    r"(?:^|\n)\s*(?:1[.\s)]*)?NAME\s+OF\s+REPORTING\s+PERSON[S]?\s*[:\n]+\s*([^\n]{4,80})",
    re.IGNORECASE,
)

# Issuer name
_ISSUER_RE = re.compile(
    r"(?:NAME\s+OF\s+ISSUER|ISSUER|SUBJECT\s+COMPANY)\s*[\n\r:]+\s*(.+?)(?:\n|\r)",
    re.IGNORECASE,
)

# Percent of class
_PERCENT_RE = re.compile(
    r"(?:PERCENT\s+OF\s+CLASS|PERCENT\s+OF\s+CLASS\s+REPRESENTED)\s*[\n\r:]+\s*([0-9]+\.?[0-9]*)\s*%?",
    re.IGNORECASE,
)

# Class title
_CLASS_TITLE_RE = re.compile(
    r"(?:TITLE\s+OF\s+CLASS\s+OF\s+SECURITIES|CLASS\s+OF\s+SECURITIES)\s*[\n\r:]+\s*(.+?)(?:\n|\r)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _is_valid_reporting_person(name: str) -> bool:
    """Reject share counts, fund source codes, and other noise."""
    if not name:
        return False

    name = name.strip()

    # Strip trailing IRS number pattern (" - 23-1945930")
    name = re.sub(r"\s*-\s*\d{2}-\d{7}\s*$", "", name).strip()

    # Too short (codes like CO, OO, PN, IN, HC)
    if len(name) <= 3:
        return False

    # Too long (sentence fragments)
    if len(name) > 100:
        return False

    # Is purely numeric or starts with digits (share counts)
    if re.match(r"^[\d,.*]+$", name):
        return False

    # Is a known form field label
    labels = {
        "check the appropriate", "sec use only", "source of funds",
        "citizenship", "sole voting", "shared voting", "sole dispositive",
        "shared dispositive", "aggregate amount", "check box",
        "type of reporting", "has ceased", "not applicable",
        "i.r.s.", "identification no", "percent of class",
        "title of class", "cusip", "date of event",
    }
    lower = name.lower()
    if any(label in lower for label in labels):
        return False

    # Must have at least 4 alpha characters
    alpha = re.sub(r"[^A-Za-z]", "", name)
    if len(alpha) < 4:
        return False

    return True


def _clean_reporting_person(name: str) -> str:
    """Clean up extracted reporting person name."""
    # Strip trailing IRS number
    name = re.sub(r"\s*-\s*\d{2}-\d{7}\s*$", "", name).strip()
    # Strip leading colons, numbers, whitespace
    name = re.sub(r"^[:\s\d.]+", "", name).strip()
    # Strip trailing whitespace and punctuation
    name = name.strip().rstrip(".,;:")
    return name


def _safe_float(value: str) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_sc13_beneficial_ownership(text: str) -> List[BeneficialOwnershipEntry]:
    """
    Parse SC 13D/G filing text and extract beneficial ownership entries.

    Strategy:
    1. Find all "NAME OF REPORTING PERSON" occurrences
    2. For each, extract the name on the next line
    3. Validate the name (reject share counts, codes, labels)
    4. Find percent and class title from the filing
    """
    if not text:
        logger.warning("parse_sc13_beneficial_ownership() received empty text")
        return []

    entries: List[BeneficialOwnershipEntry] = []
    seen_names = set()

    try:
        # Extract all reporting person names
        names = []
        for pattern in [_COVER_PAGE_RE, _REPORTING_PERSON_ALT_RE]:
            for m in pattern.finditer(text):
                raw_name = m.group(1).strip().rstrip(".,;:")
                name = _clean_reporting_person(raw_name)
                if _is_valid_reporting_person(name) and name not in seen_names:
                    seen_names.add(name)
                    names.append(name)

        # Extract percent values and class titles (global -- may not align 1:1)
        percents = [_safe_float(m) for m in _PERCENT_RE.findall(text)]
        class_titles = [c.strip() for c in _CLASS_TITLE_RE.findall(text) if c.strip()]

        # Also try to find the issuer name
        issuer_match = _ISSUER_RE.search(text)
        issuer_name = issuer_match.group(1).strip() if issuer_match else None

        logger.debug(
            "SC-13 parse: %d reporting persons, %d percents, %d class titles, issuer=%s",
            len(names), len(percents), len(class_titles), issuer_name,
        )

        # Build entries -- each unique reporting person gets one entry
        for i, name in enumerate(names):
            pct = percents[i] if i < len(percents) else None
            cls = class_titles[0] if class_titles else None  # class title is usually the same for all

            entity = Entity(
                raw_name=name,
                cleaned_name=name,
                entity_type="person_or_institution",
                notes=None,
            )

            entry = BeneficialOwnershipEntry(
                reporting_person=entity,
                percent_of_class=pct,
                class_title=cls,
                notes=f"issuer: {issuer_name}" if issuer_name else None,
            )
            entries.append(entry)

    except Exception as e:
        logger.error("parse_sc13_beneficial_ownership() failed: %s", e)
        return []

    logger.debug("Parsed %d beneficial ownership entries", len(entries))
    return entries
