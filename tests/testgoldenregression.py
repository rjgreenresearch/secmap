import os
import tempfile
from unittest.mock import patch, MagicMock

from secmap.ownership_mapper import run_secmap
from secmap.csv_writer import write_edges_to_csv


def test_sc13_golden_regression():
    """
    Ensures SECMap output for a known SC-13 synthetic fixture
    produces structurally valid CSV with expected content.
    """

    filing = MagicMock()
    filing.accession = "SC13D1"
    filing.form = "SC 13D"
    filing.cik = "555555"
    filing.filing_date = "2024-01-01"
    filing.content = "BENEFICIAL OWNERSHIP\nJohn Doe 12.5%\nSIGNATURES\n/s/ John Doe"

    discovery = MagicMock()
    discovery.root_cik = "555555"
    discovery.visited_ciks = {"555555"}
    discovery.filings = [filing]

    sections = {
        "signatures": "/s/ John Doe",
        "narrative": "John Doe, Director",
        "countries": "United States",
    }

    role_edge = MagicMock()
    role_edge.source.cleaned_name = "John Doe"
    role_edge.source.entity_type = "person"
    role_edge.target.cleaned_name = "555555"
    role_edge.target.entity_type = "company"
    role_edge.relationship = "person_role"
    role_edge.relationship_detail = "Director"
    role_edge.filing.accession = "SC13D1"
    role_edge.filing.form = "SC 13D"
    role_edge.filing.filing_date = "2024-01-01"
    role_edge.notes = "method: signature_or_narrative"

    bo_edge = MagicMock()
    bo_edge.source.cleaned_name = "John Doe"
    bo_edge.source.entity_type = "person"
    bo_edge.target.cleaned_name = "555555"
    bo_edge.target.entity_type = "company"
    bo_edge.relationship = "beneficial_owner"
    bo_edge.relationship_detail = "12.5%"
    bo_edge.filing.accession = "SC13D1"
    bo_edge.filing.form = "SC 13D"
    bo_edge.filing.filing_date = "2024-01-01"
    bo_edge.notes = "method: sc13_parser"

    with patch("secmap.ownership_mapper.walk_cik_universe", return_value=discovery), \
         patch("secmap.ownership_mapper.parse_filing_to_sections", return_value=sections), \
         patch("secmap.ownership_mapper.parse_sc13_beneficial_ownership", return_value=[MagicMock()]), \
         patch("secmap.ownership_mapper.build_role_relationships_for_filing", return_value=[role_edge]), \
         patch("secmap.ownership_mapper.build_beneficial_owner_edges", return_value=[bo_edge]), \
         patch("secmap.ownership_mapper.merge_and_deduplicate_edges", return_value=[role_edge, bo_edge]):

        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "out.csv")

            result = run_secmap("555555", ["SC 13D"], 1, 5)
            write_edges_to_csv(result.edges, out_path, root_cik="555555")

            with open(out_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Structural validation
            assert "SECMap CSV Output" in content
            assert "Root CIK: 555555" in content
            assert "John Doe" in content
            assert "person_role" in content
            assert "beneficial_owner" in content
            assert "12.5%" in content
            assert content.count("|") >= 18  # at least 2 rows x 9 delimiters
