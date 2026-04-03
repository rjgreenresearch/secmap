"""
tests/test_golden_regression.py

Golden regression test: validates that a known synthetic SC-13 input
produces structurally correct CSV output with expected content fields.

This is distinct from:
  - test_integration_sc13.py (validates pipeline wiring / mock calls)
  - test_reproducibility.py (validates byte-for-byte determinism)

The golden test validates OUTPUT CONTENT CORRECTNESS:
  - Metadata header present with correct root CIK
  - Column header row present with all 25 fields
  - Person role edge contains expected name and role
  - Beneficial owner edge contains expected name and percentage
  - Pipe delimiter count matches column count
"""

import os
import tempfile
from unittest.mock import patch, MagicMock

from secmap.ownership_mapper import run_secmap
from secmap.csv_writer import write_edges_to_csv, COLUMNS


def test_golden_sc13_output_content():
    """Known SC-13 input produces CSV with correct structure and content."""

    filing = MagicMock()
    filing.accession = "GOLDEN-SC13D-001"
    filing.form = "SC 13D"
    filing.cik = "555555"
    filing.filing_date = "2024-01-01"
    filing.content = "BENEFICIAL OWNERSHIP\nJohn Doe 12.5%\nSIGNATURES\n/s/ John Doe"

    discovery = MagicMock()
    discovery.root_cik = "555555"
    discovery.visited_ciks = {"555555"}
    discovery.filings = [filing]

    sections = {
        "full_text": filing.content,
        "signatures": "/s/ John Doe",
        "narrative": "John Doe, Director",
        "countries": "United States",
    }

    role_edge = MagicMock()
    role_edge.source.cleaned_name = "John Doe"
    role_edge.source.entity_type = "person"
    role_edge.source.notes = None
    role_edge.target.cleaned_name = "GOLDEN TEST CORP"
    role_edge.target.entity_type = "company"
    role_edge.target.notes = "CIK: 555555"
    role_edge.relationship = "person_role"
    role_edge.relationship_detail = "Director"
    role_edge.filing.accession = "GOLDEN-SC13D-001"
    role_edge.filing.form = "SC 13D"
    role_edge.filing.filing_date = "2024-01-01"
    role_edge.method = "role_extraction"
    role_edge.notes = "method: signature_or_narrative"
    role_edge.source_jurisdiction = None
    role_edge.source_risk_tier = None
    role_edge.target_jurisdiction = "United States"
    role_edge.target_risk_tier = "STANDARD"
    role_edge.state_affiliation = None
    role_edge.state_affiliation_sub = None
    role_edge.state_affiliation_detail = None
    role_edge.role_is_executive = False
    role_edge.role_is_board = True
    role_edge.role_is_ownership = False
    role_edge.role_is_obscuring = False
    role_edge.chain_depth = 0

    bo_edge = MagicMock()
    bo_edge.source.cleaned_name = "John Doe"
    bo_edge.source.entity_type = "person"
    bo_edge.source.notes = None
    bo_edge.target.cleaned_name = "GOLDEN TEST CORP"
    bo_edge.target.entity_type = "company"
    bo_edge.target.notes = "CIK: 555555"
    bo_edge.relationship = "beneficial_owner"
    bo_edge.relationship_detail = "12.5%"
    bo_edge.filing.accession = "GOLDEN-SC13D-001"
    bo_edge.filing.form = "SC 13D"
    bo_edge.filing.filing_date = "2024-01-01"
    bo_edge.method = "sc13"
    bo_edge.notes = "method: sc13_parser"
    bo_edge.source_jurisdiction = None
    bo_edge.source_risk_tier = None
    bo_edge.target_jurisdiction = "United States"
    bo_edge.target_risk_tier = "STANDARD"
    bo_edge.state_affiliation = None
    bo_edge.state_affiliation_sub = None
    bo_edge.state_affiliation_detail = None
    bo_edge.role_is_executive = False
    bo_edge.role_is_board = False
    bo_edge.role_is_ownership = True
    bo_edge.role_is_obscuring = False
    bo_edge.chain_depth = 0

    with patch("secmap.ownership_mapper.walk_cik_universe", return_value=discovery), \
         patch("secmap.ownership_mapper.parse_filing_to_sections", return_value=sections), \
         patch("secmap.ownership_mapper.parse_sc13_beneficial_ownership", return_value=[MagicMock()]), \
         patch("secmap.ownership_mapper.build_role_relationships_for_filing", return_value=[role_edge]), \
         patch("secmap.ownership_mapper.build_beneficial_owner_edges", return_value=[bo_edge]), \
         patch("secmap.ownership_mapper.merge_and_deduplicate_edges", return_value=[role_edge, bo_edge]):

        result = run_secmap("555555", ["SC 13D"], 1, 5)

        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "golden_output.csv")
            write_edges_to_csv(result.edges, out_path, root_cik="555555")

            with open(out_path, "r", encoding="utf-8") as f:
                content = f.read()
                lines = content.strip().split("\n")

            # --- Metadata header ---
            assert "# SECMap CSV Output" in content
            assert "# Root CIK: 555555" in content
            assert "# Delimiter: |" in content

            # --- Column header row ---
            header_line = [l for l in lines if not l.startswith("#") and "|" in l][0]
            header_fields = header_line.split("|")
            assert len(header_fields) == len(COLUMNS)
            assert header_fields[0] == "source"
            assert "chain_depth" in header_fields

            # --- Data rows ---
            data_lines = [l for l in lines if not l.startswith("#") and "|" in l][1:]
            assert len(data_lines) == 2  # role_edge + bo_edge

            # --- Content correctness ---
            assert "John Doe" in content
            assert "GOLDEN TEST CORP" in content
            assert "person_role" in content
            assert "beneficial_owner" in content
            assert "12.5%" in content
            assert "Director" in content
            assert "GOLDEN-SC13D-001" in content

            # --- Structural correctness ---
            for data_line in data_lines:
                fields = data_line.split("|")
                assert len(fields) == len(COLUMNS), (
                    f"Expected {len(COLUMNS)} fields, got {len(fields)}"
                )
