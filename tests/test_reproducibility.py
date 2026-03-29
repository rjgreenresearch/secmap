import os
import hashlib
import tempfile
from unittest.mock import patch, MagicMock
from datetime import datetime

from secmap.ownership_mapper import run_secmap
from secmap.csv_writer import write_edges_to_csv


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def test_reproducibility_same_input_same_hash():
    """
    Ensures SECMap produces byte-for-byte identical CSV output
    for identical synthetic SC-13 input.
    """

    filing = MagicMock()
    filing.accession = "SC13D1"
    filing.form = "SC 13D"
    filing.cik = "777777"
    filing.filing_date = "2024-01-01"
    filing.content = "BENEFICIAL OWNERSHIP\nJohn Doe 12.5%\nSIGNATURES\n/s/ John Doe"

    discovery = MagicMock()
    discovery.root_cik = "777777"
    discovery.visited_ciks = {"777777"}
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
    role_edge.target.cleaned_name = "777777"
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
    bo_edge.target.cleaned_name = "777777"
    bo_edge.target.entity_type = "company"
    bo_edge.relationship = "beneficial_owner"
    bo_edge.relationship_detail = "12.5%"
    bo_edge.filing.accession = "SC13D1"
    bo_edge.filing.form = "SC 13D"
    bo_edge.filing.filing_date = "2024-01-01"
    bo_edge.notes = "method: sc13_parser"

    with patch("secmap.ownership_mapper.walk_cik_universe", return_value=discovery), \
         patch("secmap.ownership_mapper.parse_filing_to_sections", return_value=sections), \
         patch("secmap.ownership_mapper.parse_sc13_beneficial_ownership", return_value=[bo_entry]), \
         patch("secmap.ownership_mapper.build_role_relationships_for_filing", return_value=[role_edge]), \
         patch("secmap.ownership_mapper.build_beneficial_owner_edges", return_value=[bo_edge]), \
         patch("secmap.ownership_mapper.merge_and_deduplicate_edges", return_value=[role_edge, bo_edge]), \
         patch("secmap.csv_writer.datetime") as mock_dt:

        frozen = datetime(2024, 1, 1, 12, 0, 0)
        mock_dt.utcnow.return_value = frozen
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        with tempfile.TemporaryDirectory() as tmp:
            out1 = os.path.join(tmp, "run1.csv")
            out2 = os.path.join(tmp, "run2.csv")

            result1 = run_secmap("777777", ["SC 13D"], 1, 5)
            write_edges_to_csv(result1.edges, out1, root_cik="777777")

            result2 = run_secmap("777777", ["SC 13D"], 1, 5)
            write_edges_to_csv(result2.edges, out2, root_cik="777777")

            assert sha256(out1) == sha256(out2)
