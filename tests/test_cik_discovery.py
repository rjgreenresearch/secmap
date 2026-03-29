import pytest
from unittest.mock import patch, MagicMock

from secmap.cik_discovery import (
    extract_ciks_from_text,
    discover_related_ciks_from_filing,
    walk_cik_universe,
    DiscoveryConfig,
)


def test_extract_ciks_from_text_basic():
    text = "This references CIK 0000123456 and CIK: 987654."
    result = extract_ciks_from_text(text)
    assert result == ["123456", "987654"]


def test_extract_ciks_from_text_empty():
    assert extract_ciks_from_text("") == []


def test_discover_related_ciks_from_filing_parses_sections():
    with patch("secmap.cik_discovery.parse_filing_to_sections") as mock_parse:
        mock_parse.return_value = {"full_text": "CIK 123456"}
        result = discover_related_ciks_from_filing("dummy")
        assert result == ["123456"]


def test_discover_related_ciks_from_filing_handles_exception():
    with patch("secmap.cik_discovery.parse_filing_to_sections", side_effect=Exception("boom")):
        result = discover_related_ciks_from_filing("dummy")
        assert result == []


@patch("secmap.cik_discovery.fetch_filings_for_cik")
def test_walk_cik_universe_single_cik(mock_fetch):
    mock_fetch.side_effect = [
        [
            {
                "accession": "A1",
                "form": "10-K",
                "filing_date": "2023-01-01",
                "content": "No related CIKs here",
            }
        ],
    ]

    config = DiscoveryConfig(form_types=["10-K"], max_depth=1)
    result = walk_cik_universe("123456", config)

    assert result.root_cik == "123456"
    assert "123456" in result.visited_ciks
    assert len(result.filings) == 1


@patch("secmap.cik_discovery.fetch_filings_for_cik")
def test_walk_cik_universe_recurses(mock_fetch):
    mock_fetch.side_effect = [
        [
            {
                "accession": "A1",
                "form": "10-K",
                "filing_date": "2023-01-01",
                "content": "CIK 555555",
            }
        ],
        []
    ]

    config = DiscoveryConfig(form_types=["10-K"], max_depth=2)
    result = walk_cik_universe("123456", config)

    assert "123456" in result.visited_ciks
    assert "555555" in result.visited_ciks
    assert len(result.filings) == 1


def test_walk_cik_universe_invalid_root():
    config = DiscoveryConfig(form_types=["10-K"])
    with pytest.raises(ValueError):
        walk_cik_universe("not_a_cik", config)
