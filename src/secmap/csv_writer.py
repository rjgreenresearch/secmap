"""
csv_writer.py

Responsible for writing OwnershipEdge objects to a structurally perfect,
pipe-delimited CSV file with metadata headers.

Output columns now include full chain-analysis fields:
- Source/target jurisdiction and risk tier
- State affiliation category, subcategory, and detail
- Role semantic flags
- Chain depth

Enhancements:
- Full logging
- Exception-safe writing
- Deterministic field ordering
- Robust sanitization (quotes, pipes, control chars)
- Metadata header block
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import List

from .ownership_edges import OwnershipEdge

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Column definitions (order matters -- this is the CSV schema)
# ---------------------------------------------------------------------------

COLUMNS = [
    "source",
    "source_type",
    "source_jurisdiction",
    "source_risk_tier",
    "target",
    "target_type",
    "target_jurisdiction",
    "target_risk_tier",
    "relationship",
    "detail",
    "company_name",
    "company_cik",
    "state_affiliation",
    "state_affiliation_sub",
    "state_affiliation_detail",
    "role_is_executive",
    "role_is_board",
    "role_is_ownership",
    "role_is_obscuring",
    "chain_depth",
    "filing_accession",
    "filing_form",
    "filing_date",
    "method",
    "notes",
]


# ---------------------------------------------------------------------------
# Sanitization
# ---------------------------------------------------------------------------

_CONTROL_CHARS = re.compile(r"[^\x09\x0A\x0D\x20-\x7E]")

def sanitize_field(value) -> str:
    if value is None:
        return ""
    try:
        value = str(value)
        value = _CONTROL_CHARS.sub(" ", value)
        value = value.replace("|", "/")
        value = value.replace('"', "'")
        return value.strip()
    except Exception as e:
        logger.error("sanitize_field() failed for %r: %s", value, e)
        return ""


# ---------------------------------------------------------------------------
# Metadata header block
# ---------------------------------------------------------------------------

def build_metadata_header(root_cik: str) -> str:
    ts = datetime.utcnow().isoformat()
    header = [
        "# SECMap CSV Output",
        f"# Generated: {ts} UTC",
        f"# Root CIK: {root_cik}",
        "# Delimiter: |",
        f"# Fields: {' | '.join(COLUMNS)}",
        "",
    ]
    return "\n".join(header)


# ---------------------------------------------------------------------------
# Row formatting
# ---------------------------------------------------------------------------

def _bool_str(val: bool) -> str:
    return "Y" if val else ""


def format_edge_row(edge: OwnershipEdge) -> str:
    try:
        # Extract company name and CIK from the target entity's notes
        company_name = ""
        company_cik = ""
        target_notes = getattr(edge.target, "notes", "") or ""
        source_notes = getattr(edge.source, "notes", "") or ""
        if target_notes.startswith("CIK:"):
            company_cik = target_notes.replace("CIK: ", "").strip()
            company_name = edge.target.cleaned_name
        elif source_notes.startswith("CIK:"):
            company_cik = source_notes.replace("CIK: ", "").strip()
            company_name = edge.source.cleaned_name

        fields = [
            sanitize_field(edge.source.cleaned_name),
            sanitize_field(edge.source.entity_type),
            sanitize_field(edge.source_jurisdiction),
            sanitize_field(edge.source_risk_tier),
            sanitize_field(edge.target.cleaned_name),
            sanitize_field(edge.target.entity_type),
            sanitize_field(edge.target_jurisdiction),
            sanitize_field(edge.target_risk_tier),
            sanitize_field(edge.relationship),
            sanitize_field(edge.relationship_detail),
            sanitize_field(company_name),
            sanitize_field(company_cik),
            sanitize_field(edge.state_affiliation),
            sanitize_field(edge.state_affiliation_sub),
            sanitize_field(edge.state_affiliation_detail),
            _bool_str(edge.role_is_executive),
            _bool_str(edge.role_is_board),
            _bool_str(edge.role_is_ownership),
            _bool_str(edge.role_is_obscuring),
            sanitize_field(edge.chain_depth),
            sanitize_field(edge.filing.accession),
            sanitize_field(edge.filing.form),
            sanitize_field(edge.filing.filing_date),
            sanitize_field(edge.method),
            sanitize_field(edge.notes or ""),
        ]
        return "|".join(fields)
    except Exception as e:
        logger.error("format_edge_row() failed for edge %r: %s", edge, e)
        return ""


def format_column_header() -> str:
    return "|".join(COLUMNS)


# ---------------------------------------------------------------------------
# Main writer
# ---------------------------------------------------------------------------

def write_edges_to_csv(
    edges: List[OwnershipEdge],
    output_path: str,
    root_cik: str,
) -> None:
    """
    Write edges to a pipe-delimited CSV file with metadata header.
    """
    if not output_path:
        logger.error("write_edges_to_csv() received empty output_path")
        return

    try:
        dirname = os.path.dirname(output_path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
    except Exception as e:
        logger.error("Failed to create output directory: %s", e)
        return

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(build_metadata_header(root_cik))
            f.write(format_column_header() + "\n")

            for edge in edges:
                row = format_edge_row(edge)
                if row:
                    f.write(row + "\n")

        logger.info("Wrote %d edges to CSV: %s", len(edges), output_path)

    except Exception as e:
        logger.critical("Failed to write CSV file %s: %s", output_path, e)
