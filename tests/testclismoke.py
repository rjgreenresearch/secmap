import pytest
from unittest.mock import patch, MagicMock

from secmap.cli import main


@patch("secmap.cli.run_secmap")
@patch("secmap.cli.write_edges_to_csv")
def test_cli_smoke(mock_write, mock_run):
    """
    Ensures the CLI runs end-to-end with mocks and exits cleanly.
    """
    mock_result = MagicMock()
    mock_result.edges = ["edge1"]
    mock_result.root_cik = "123456"
    mock_run.return_value = mock_result

    exit_code = main([
        "run",
        "--cik", "123456",
        "--forms", "SC",
        "--depth", "1",
        "--limit", "5",
        "--out", "out.csv",
    ])

    assert exit_code == 0
    mock_run.assert_called_once()
    mock_write.assert_called_once()
