import os
import tempfile
from unittest.mock import patch, MagicMock

from secmap.ownership_mapper import run_secmap
from secmap.csv_writer import write_edges_to_csv


def test_end_to_end_sc13_integration():
    """
    Full pipeline integration test for SC-13 filings.
    """

    filing = MagicMock()
    filing.accession = "SC13D1"
    filing.form = "SC 13D"
    filing.cik = "888888"
    filing.filing_date = "2024-01-01"
    filing.content = (
        "BENEFICIAL OWNERSHIP\n"
        "Reporting Person: John Doe\n"
        "Percent Owned: 12.5%\n"
        "SIGNATURES\n"
        "/s/ John Doe\n"
    )

    discovery = MagicMock()
    discovery.root_cik = "888888"
    discovery.visited_ciks = {"888888"}
    discovery.filings = [filing]

    sections = {
        "signatures": "/s/ John Doe",
        "narrative": "John Doe, Director",
        "countries": "United States",
    }

    bo_entry = MagicMock()
    bo_entry.name = "John Doe"
    bo_entry.percent = 12.5

    role_edge = MagicMock()
    role_edge.source.cleaned_name = "John Doe"
    role_edge.source.entity_type = "person"
    role_edge.target.cleaned_name = "888888"
    role_edge.target.entity_type = "company"
    role_edge.relationship = "person_role"
    role_edge.relationship_detail = "Director"
    role_edge.filing.accession = "SC13D1"
    role_edge.filing.form = "SC 13D"
    role_edge.filing.filing_date = "2024-01-01"
    role_edge.notes = "method: signature_or_narrative"

    with patch("secmap.ownership_mapper.walk_cik_universe", return_value=discovery), \
         patch("secmap.ownership_mapper.parse_filing_to_sections", return_value=sections), \
         patch("secmap.ownership_mapper.parse_sc13_beneficial_ownership", return_value=[bo_entry]) as mock_sc13, \
         patch("secmap.ownership_mapper.build_role_relationships_for_filing", return_value=[role_edge]), \
         patch("secmap.ownership_mapper.build_beneficial_owner_edges") as mock_bo_edges, \
         patch("secmap.ownership_mapper.merge_and_deduplicate_edges") as mock_dedupe:

        bo_edge = MagicMock()
        bo_edge.source.cleaned_name = "John Doe"
        bo_edge.source.entity_type = "person"
        bo_edge.target.cleaned_name = "888888"
        bo_edge.target.entity_type = "company"
        bo_edge.relationship = "beneficial_owner"
        bo_edge.relationship_detail = "12.5%"
        bo_edge.filing.accession = "SC13D1"
        bo_edge.filing.form = "SC 13D"
        bo_edge.filing.filing_date = "2024-01-01"
        bo_edge.notes = "method: sc13_parser"

        mock_bo_edges.return_value = [bo_edge]
        mock_dedupe.return_value = [role_edge, bo_edge]

        result = run_secmap(
            root_cik="888888",
            form_types=["SC 13D"],
            max_depth=1,
            max_filings_per_cik=5,
        )

        mock_sc13.assert_called_once()

        assert result.filings_processed == 1
        assert len(result.edges) == 2

        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "sc13_out.csv")
            write_edges_to_csv(result.edges, out_path, root_cik="888888")

            assert os.path.exists(out_path)

            with open(out_path, "r", encoding="utf-8") as f:
                content = f.read()

            assert "SECMap CSV Output" in content
            assert "Root CIK: 888888" in content
            assert "Delimiter: |" in content
            assert "John Doe" in content
            assert "beneficial_owner" in content
            assert "12.5%" in content
            assert content.count("|") >= 9
