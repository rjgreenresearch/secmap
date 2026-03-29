import pytest
from unittest.mock import patch, MagicMock

from secmap.cli import main


@patch("secmap.cli.run_secmap")
@patch("secmap.cli.write_edges_to_csv")
def test_cli_success(mock_write, mock_run):
    mock_result = MagicMock()
    mock_result.edges = ["e1"]
    mock_result.root_cik = "123456"
    mock_run.return_value = mock_result

    code = main([
        "run",
        "--cik", "123456",
        "--forms", "10-K",
        "--depth", "1",
        "--limit", "5",
        "--out", "out.csv",
    ])

    assert code == 0
    mock_run.assert_called_once()
    mock_write.assert_called_once()


@patch("secmap.cli.run_secmap", side_effect=Exception("boom"))
def test_cli_discovery_failure(mock_run):
    code = main([
        "run",
        "--cik", "123456",
        "--forms", "10-K",
        "--depth", "1",
        "--limit", "5",
        "--out", "out.csv",
    ])
    assert code == 2


@patch("secmap.cli.run_secmap")
@patch("secmap.cli.write_edges_to_csv", side_effect=Exception("write fail"))
def test_cli_write_failure(mock_write, mock_run):
    mock_result = MagicMock()
    mock_result.edges = []
    mock_result.root_cik = "123456"
    mock_run.return_value = mock_result

    code = main([
        "run",
        "--cik", "123456",
        "--forms", "10-K",
        "--depth", "1",
        "--limit", "5",
        "--out", "out.csv",
    ])
    assert code == 3
