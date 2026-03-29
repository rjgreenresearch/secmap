import pytest
from unittest.mock import patch, MagicMock

from secmap.relationship_builder import build_role_relationships_for_filing


@pytest.fixture
def mock_filing():
    f = MagicMock()
    f.accession = "A1"
    f.form = "10-K"
    f.cik = "123456"
    return f


def test_empty_input_returns_empty():
    assert build_role_relationships_for_filing(None, {}) == []
    assert build_role_relationships_for_filing("x", None) == []


@patch("secmap.relationship_builder.extract_people_from_signatures")
@patch("secmap.relationship_builder.extract_people_from_narrative")
@patch("secmap.relationship_builder.extract_institutions_from_narrative")
@patch("secmap.relationship_builder.classify_role")
def test_build_role_relationships_basic(
    mock_classify,
    mock_inst,
    mock_narr,
    mock_sig,
    mock_filing,
):
    # Mock people
    person_entity = MagicMock()
    person_entity.raw_name = "John Doe"
    mock_sig.return_value = [person_entity]
    mock_narr.return_value = []

    # Mock institutions
    inst_entity = MagicMock()
    inst_role = MagicMock()
    mock_inst.return_value = [(inst_entity, inst_role)]

    # Mock role classification
    mock_classify.return_value = MagicMock()

    sections = {
        "signatures": "SIGNATURES\nJohn Doe",
        "narrative": "Board of Directors",
    }

    edges = build_role_relationships_for_filing(mock_filing, sections)
    assert len(edges) == 2  # one person edge + one institution edge


@patch("secmap.relationship_builder.extract_people_from_signatures", side_effect=Exception("boom"))
def test_people_extraction_failure(mock_sig, mock_filing):
    sections = {"signatures": "x", "narrative": "y"}
    edges = build_role_relationships_for_filing(mock_filing, sections)
    assert isinstance(edges, list)


@patch("secmap.relationship_builder.extract_institutions_from_narrative", side_effect=Exception("boom"))
def test_institution_extraction_failure(mock_inst, mock_filing):
    sections = {"signatures": "x", "narrative": "y"}
    edges = build_role_relationships_for_filing(mock_filing, sections)
    assert isinstance(edges, list)
