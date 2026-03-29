import pytest
from unittest.mock import patch, MagicMock

from secmap.ownership_mapper import run_secmap, SECMapResult


@pytest.fixture
def mock_discovery():
    filing = MagicMock()
    filing.accession = "A1"
    filing.form = "10-K"
    filing.cik = "123456"
    filing.content = "SIGNATURES\nJohn Doe\nEXHIBIT"

    discovery = MagicMock()
    discovery.root_cik = "123456"
    discovery.visited_ciks = {"123456"}
    discovery.filings = [filing]
    return discovery


@patch("secmap.ownership_mapper.walk_cik_universe")
@patch("secmap.ownership_mapper.parse_filing_to_sections")
@patch("secmap.ownership_mapper.build_role_relationships_for_filing")
@patch("secmap.ownership_mapper.merge_and_deduplicate_edges")
def test_run_secmap_basic(
    mock_dedupe,
    mock_roles,
    mock_parse,
    mock_discovery_fn,
    mock_discovery,
):
    mock_discovery_fn.return_value = mock_discovery
    mock_parse.return_value = {
        "full_text": "text",
        "signatures": "SIGNATURES\nJohn Doe",
        "narrative": "Board of Directors",
        "countries": "United States",
    }
    mock_roles.return_value = ["edge1"]
    mock_dedupe.return_value = ["edge1"]

    result = run_secmap(
        root_cik="123456",
        form_types=["10-K"],
        max_depth=1,
        max_filings_per_cik=5,
    )

    assert isinstance(result, SECMapResult)
    assert result.filings_processed == 1
    assert result.edges == ["edge1"]


@patch("secmap.ownership_mapper.walk_cik_universe", side_effect=Exception("boom"))
def test_run_secmap_discovery_failure(mock_discovery):
    with pytest.raises(Exception):
        run_secmap("123456", ["10-K"], 1, 5)


@patch("secmap.ownership_mapper.walk_cik_universe")
@patch("secmap.ownership_mapper.parse_filing_to_sections", side_effect=Exception("bad parse"))
def test_run_secmap_parse_failure(mock_parse, mock_discovery_fn, mock_discovery):
    mock_discovery_fn.return_value = mock_discovery
    result = run_secmap("123456", ["10-K"], 1, 5)
    assert result.edges == []


@patch("secmap.ownership_mapper.walk_cik_universe")
@patch("secmap.ownership_mapper.build_role_relationships_for_filing", side_effect=Exception("bad roles"))
def test_run_secmap_role_failure(mock_roles, mock_discovery_fn, mock_discovery):
    mock_discovery_fn.return_value = mock_discovery
    result = run_secmap("123456", ["10-K"], 1, 5)
    assert result.edges == []
