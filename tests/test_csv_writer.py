import os
import tempfile
from unittest.mock import MagicMock

from secmap.csv_writer import (
    sanitize_field,
    format_edge_row,
    write_edges_to_csv,
    COLUMNS,
)


def mock_edge():
    e = MagicMock()
    e.source.cleaned_name = "John Doe"
    e.source.entity_type = "person"
    e.target.cleaned_name = "TestCorp"
    e.target.entity_type = "company"
    e.relationship = "person_role"
    e.relationship_detail = "Director"
    e.filing.accession = "A1"
    e.filing.form = "10-K"
    e.filing.filing_date = "2023-01-01"
    e.method = "role_extraction"
    e.notes = "note1"
    e.source_jurisdiction = "China"
    e.source_risk_tier = "ADVERSARIAL"
    e.target_jurisdiction = "United States"
    e.target_risk_tier = "STANDARD"
    e.state_affiliation = "SOE"
    e.state_affiliation_sub = "PRC"
    e.state_affiliation_detail = "Matched PRC SOE keywords"
    e.role_is_executive = False
    e.role_is_board = True
    e.role_is_ownership = False
    e.role_is_obscuring = False
    e.chain_depth = 1
    return e


def test_sanitize_field_basic():
    assert sanitize_field("Hello|World") == "Hello/World"
    assert sanitize_field('He said "Hi"') == "He said 'Hi'"


def test_format_edge_row():
    row = format_edge_row(mock_edge())
    assert "John Doe" in row
    assert "TestCorp" in row
    assert "ADVERSARIAL" in row
    assert "SOE" in row
    assert row.count("|") == len(COLUMNS) - 1


def test_write_edges_to_csv():
    edge = mock_edge()

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "out.csv")
        write_edges_to_csv([edge], path, root_cik="123456")

        assert os.path.exists(path)

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "SECMap CSV Output" in content
        assert "John Doe" in content
        assert "TestCorp" in content
        # Column header row present
        assert "source|source_type|" in content
        assert "state_affiliation" in content
        assert "chain_depth" in content
