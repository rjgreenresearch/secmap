import os
import tempfile
from unittest.mock import patch, MagicMock

from secmap.ownership_mapper import run_secmap
from secmap.csv_writer import write_edges_to_csv


def test_end_to_end_integration():
    """
    Full pipeline integration test:
    - Mock CIK discovery
    - Mock filing content + parsed sections
    - Run run_secmap()
    - Write CSV
    - Assert metadata + row structure
    """

    filing = MagicMock()
    filing.accession = "A1"
    filing.form = "10-K"
    filing.cik = "123456"
    filing.filing_date = "2023-01-01"
    filing.content = "SIGNATURES\nJohn Doe\nBoard of Directors"

    discovery = MagicMock()
    discovery.root_cik = "123456"
    discovery.visited_ciks = {"123456"}
    discovery.filings = [filing]

    sections = {
        "signatures": "SIGNATURES\nJohn Doe",
        "narrative": "John Doe, Director",
        "countries": "United States",
    }

    mock_edge = MagicMock()
    mock_edge.source.cleaned_name = "John Doe"
    mock_edge.source.entity_type = "person"
    mock_edge.target.cleaned_name = "123456"
    mock_edge.target.entity_type = "company"
    mock_edge.relationship = "person_role"
    mock_edge.relationship_detail = "Director"
    mock_edge.filing.accession = "A1"
    mock_edge.filing.form = "10-K"
    mock_edge.filing.filing_date = "2023-01-01"
    mock_edge.notes = "method: signature_or_narrative"

    with patch("secmap.ownership_mapper.walk_cik_universe", return_value=discovery), \
         patch("secmap.ownership_mapper.parse_filing_to_sections", return_value=sections), \
         patch("secmap.ownership_mapper.build_role_relationships_for_filing", return_value=[mock_edge]), \
         patch("secmap.ownership_mapper.merge_and_deduplicate_edges", return_value=[mock_edge]):

        result = run_secmap(
            root_cik="123456",
            form_types=["10-K"],
            max_depth=1,
            max_filings_per_cik=5,
        )

        assert result.filings_processed == 1
        assert len(result.edges) == 1

        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "out.csv")
            write_edges_to_csv(result.edges, out_path, root_cik="123456")

            assert os.path.exists(out_path)

            with open(out_path, "r", encoding="utf-8") as f:
                content = f.read()

            assert "SECMap CSV Output" in content
            assert "Root CIK: 123456" in content
            assert "Delimiter: |" in content
            assert "John Doe" in content
            assert "person_role" in content
            assert content.count("|") >= 9
