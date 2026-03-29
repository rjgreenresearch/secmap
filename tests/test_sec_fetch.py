import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from secmap import sec_fetch


@patch("secmap.sec_fetch.requests.get")
def test_http_get_success(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "OK"
    mock_get.return_value = mock_resp

    result = sec_fetch._http_get("http://example.com", use_cache=False)
    assert result is not None
    assert result.text == "OK"


@patch("secmap.sec_fetch.requests.get")
def test_http_get_rate_limit_retry(mock_get):
    resp1 = MagicMock()
    resp1.status_code = 429

    resp2 = MagicMock()
    resp2.status_code = 200
    resp2.text = "OK"

    mock_get.side_effect = [resp1, resp2]

    result = sec_fetch._http_get("http://example.com", use_cache=False)
    assert result is not None
    assert result.text == "OK"
    assert mock_get.call_count == 2


@patch("secmap.sec_fetch.requests.get")
def test_http_get_failure(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_get.return_value = mock_resp

    result = sec_fetch._http_get("http://example.com", use_cache=False)
    assert result is None


@patch("secmap.sec_fetch._fetch_json")
def test_fetch_company_submissions_parses_json(mock_fetch):
    mock_fetch.return_value = {"filings": {"recent": {"form": []}}}
    result = sec_fetch.fetch_company_submissions("1234567890")
    assert "filings" in result


@patch("secmap.sec_fetch._fetch_json")
def test_fetch_company_submissions_returns_none_on_failure(mock_fetch):
    mock_fetch.return_value = None
    result = sec_fetch.fetch_company_submissions("1234567890")
    assert result is None


@patch("secmap.sec_fetch.fetch_company_submissions")
def test_fetch_latest_filings_filters_forms(mock_submissions):
    mock_submissions.return_value = {
        "name": "Test Corp",
        "filings": {
            "recent": {
                "form": ["10-K", "8-K", "10-K"],
                "accessionNumber": ["A1", "A2", "A3"],
                "filingDate": ["2023-01-01", "2023-01-02", "2023-01-03"],
                "primaryDocument": ["doc1.htm", "doc2.htm", "doc3.htm"],
            }
        }
    }

    results = sec_fetch.fetch_latest_filings("1234567890", ["10-K"])
    assert len(results) == 2
    assert results[0]["accession"] == "A1"
    assert results[1]["accession"] == "A3"


def test_cache_write_and_read():
    with tempfile.TemporaryDirectory() as tmp:
        original_cache = sec_fetch.CACHE_DIR
        sec_fetch.CACHE_DIR = tmp
        try:
            path = sec_fetch._cache_path("http://example.com/test")
            sec_fetch._write_cache(path, "cached content")
            result = sec_fetch._read_cache(path)
            assert result == "cached content"
        finally:
            sec_fetch.CACHE_DIR = original_cache


def test_cache_miss_returns_none():
    result = sec_fetch._read_cache("/nonexistent/path/file.txt")
    assert result is None
