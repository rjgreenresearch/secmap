"""
parse_filings.py

Normalization and sectioning of SEC filings into structured text blocks
consumable by the extraction and relationship-building layers.

Enhancements:
- Full logging
- Exception-safe parsing
- Stronger HTML stripping
- More robust signature block heuristics
- Input validation
"""

from __future__ import annotations

import html
import logging
import re
from typing import Dict, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTML / markup cleaning
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_BR_RE = re.compile(r"(?i)<\s*br\s*/?\s*>")
_P_RE = re.compile(r"(?i)<\s*/?\s*p[^>]*>")


def strip_html(raw: str) -> str:
    """
    Lightweight HTML stripper suitable for SEC filings.

    - Converts <br> and <p> to newlines
    - Removes all tags
    - Unescapes HTML entities
    """
    if not raw:
        logger.warning("strip_html() received empty input")
        return ""

    try:
        text = _BR_RE.sub("\n", raw)
        text = _P_RE.sub("\n", text)
        text = _TAG_RE.sub("", text)
        text = html.unescape(text)
        return text
    except Exception as e:
        logger.error("strip_html() failed: %s", e)
        return raw  # fallback to raw text


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

def normalize_text(raw: str) -> str:
    """
    Normalize whitespace and control characters.

    - Normalize line endings
    - Remove control characters
    - Collapse repeated spaces and blank lines
    """
    if not raw:
        logger.warning("normalize_text() received empty input")
        return ""

    try:
        text = raw.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[^\x09\x0A\x0D\x20-\x7E]", " ", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
    except Exception as e:
        logger.error("normalize_text() failed: %s", e)
        return raw.strip()


# ---------------------------------------------------------------------------
# Signature block extraction
# ---------------------------------------------------------------------------

_SIGNATURE_HEADER = re.compile(r"^\s*SIGNATURES?\s*$", re.IGNORECASE | re.MULTILINE)
_SIGNATURE_END_HINTS = [
    "POWER OF ATTORNEY",
    "EXHIBIT",
    "INDEX TO EXHIBITS",
    "TABLE OF CONTENTS",
]


def extract_signature_block(text: str) -> str:
    """
    Extract the primary signature block from a filing.

    Heuristic:
      - Find SIGNATURE or SIGNATURES header
      - Take text until a common end marker or EOF
    """
    if not text:
        return ""

    try:
        m = _SIGNATURE_HEADER.search(text)
        if not m:
            logger.debug("No signature header found")
            return ""

        start = m.end()
        tail = text[start:]

        # Find earliest end hint
        upper_tail = tail.upper()
        end_idx = len(tail)
        for hint in _SIGNATURE_END_HINTS:
            pos = upper_tail.find(hint)
            if pos != -1 and pos < end_idx:
                end_idx = pos

        block = tail[:end_idx].strip()
        logger.debug("Extracted signature block length: %d", len(block))
        return block
    except Exception as e:
        logger.error("extract_signature_block() failed: %s", e)
        return ""


# ---------------------------------------------------------------------------
# Narrative section extraction
# ---------------------------------------------------------------------------

_NARRATIVE_HEADINGS = [
    "DIRECTORS AND EXECUTIVE OFFICERS",
    "BOARD OF DIRECTORS",
    "MANAGEMENT",
    "EXECUTIVE OFFICERS",
    "CORPORATE GOVERNANCE",
]


def extract_narrative_section(text: str) -> str:
    """
    Extract a narrative section likely to contain role descriptions.
    """
    if not text:
        return ""

    try:
        upper = text.upper()
        best_pos = None

        for heading in _NARRATIVE_HEADINGS:
            pos = upper.find(heading)
            if pos != -1 and (best_pos is None or pos < best_pos):
                best_pos = pos

        if best_pos is None:
            logger.debug("No narrative heading found")
            return ""

        window = text[best_pos:]
        max_len = 20000
        if len(window) > max_len:
            window = window[:max_len]

        logger.debug("Extracted narrative section length: %d", len(window))
        return window.strip()

    except Exception as e:
        logger.error("extract_narrative_section() failed: %s", e)
        return ""


# ---------------------------------------------------------------------------
# Country mention extraction
# ---------------------------------------------------------------------------

_COUNTRY_TOKENS = [
    "United States", "U.S.", "USA",
    "China", "People's Republic of China", "PRC",
    "Hong Kong", "Taiwan", "Japan", "Korea",
    "India", "Canada", "Mexico", "Brazil",
    "Germany", "France", "United Kingdom", "UK",
    "Russia", "Singapore", "United Arab Emirates", "UAE",
    "Saudi Arabia", "Australia", "New Zealand",
]


def extract_country_mentions(text: str) -> List[str]:
    """
    Extract a de-duplicated list of country names mentioned in the text.
    """
    if not text:
        return []

    try:
        found = []
        upper = text.upper()

        for token in _COUNTRY_TOKENS:
            if token.upper() in upper:
                found.append(token)

        # Deduplicate
        seen = set()
        unique = []
        for c in found:
            if c not in seen:
                seen.add(c)
                unique.append(c)

        logger.debug("Extracted %d country mentions", len(unique))
        return unique

    except Exception as e:
        logger.error("extract_country_mentions() failed: %s", e)
        return []


# ---------------------------------------------------------------------------
# High-level API
# ---------------------------------------------------------------------------

def parse_filing_to_sections(raw_content: str) -> Dict[str, str]:
    """
    Convert raw filing content (HTML or text) into normalized sections.

    Returns:
      {
        "full_text": ...,
        "signatures": ...,
        "narrative": ...,
        "countries": ...
      }
    """
    if not raw_content:
        logger.warning("parse_filing_to_sections() received empty content")
        return {
            "full_text": "",
            "signatures": "",
            "narrative": "",
            "countries": "",
        }

    try:
        stripped = strip_html(raw_content)
        normalized = normalize_text(stripped)

        signatures = extract_signature_block(normalized)
        narrative = extract_narrative_section(normalized)
        countries = extract_country_mentions(normalized)

        return {
            "full_text": normalized,
            "signatures": signatures,
            "narrative": narrative,
            "countries": "\n".join(countries),
        }

    except Exception as e:
        logger.error("parse_filing_to_sections() failed: %s", e)
        return {
            "full_text": raw_content,
            "signatures": "",
            "narrative": "",
            "countries": "",
        }
