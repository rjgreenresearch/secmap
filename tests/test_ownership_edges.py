import pytest
from unittest.mock import MagicMock

from secmap.ownership_edges import (
    build_person_role_edges,
    build_institution_role_edges,
    build_beneficial_owner_edges,
    build_country_association_edges,
    merge_and_deduplicate_edges,
    OwnershipEdge,
)


@pytest.fixture
def mock_filing():
    f = MagicMock()
    f.accession = "A1"
    f.form = "10-K"
    f.filing_date = "2023-01-01"
    f.cik = "123456"
    return f


@pytest.fixture
def mock_issuer():
    e = MagicMock()
    e.cleaned_name = "TestCorp"
    e.entity_type = "company"
    return e


def test_person_role_edges_basic(mock_filing, mock_issuer):
    person = MagicMock()
    person.cleaned_name = "John Doe"
    role = MagicMock()
    role.canonical_role = "Director"

    edges = build_person_role_edges(mock_filing, mock_issuer, [(person, role)])
    assert len(edges) == 1
    assert edges[0].relationship == "person_role"


def test_institution_role_edges_basic(mock_filing, mock_issuer):
    inst = MagicMock()
    inst.cleaned_name = "BigBank"
    role = MagicMock()
    role.canonical_role = "Custodian"

    edges = build_institution_role_edges(mock_filing, mock_issuer, [(inst, role)])
    assert len(edges) == 1
    assert edges[0].relationship == "institution_role"


def test_beneficial_owner_edges_basic(mock_filing, mock_issuer):
    entry = MagicMock()
    entry.reporting_person = MagicMock()
    entry.reporting_person.cleaned_name = "Jane Doe"
    entry.percent_of_class = 5.0
    entry.class_title = "Common Stock"
    entry.notes = "Test note"

    edges = build_beneficial_owner_edges(mock_filing, mock_issuer, [entry])
    assert len(edges) == 1
    assert edges[0].relationship == "beneficial_owner"


def test_country_association_edges(mock_filing, mock_issuer):
    edges = build_country_association_edges(mock_issuer, mock_filing, ["China", "USA"])
    assert len(edges) == 2
    assert edges[0].relationship == "country_association"


def test_deduplication_merges_notes(mock_filing):
    e1 = MagicMock()
    e1.source.cleaned_name = "A"
    e1.source.entity_type = "person"
    e1.target.cleaned_name = "B"
    e1.target.entity_type = "company"
    e1.relationship = "person_role"
    e1.relationship_detail = "CEO"
    e1.filing.accession = "A1"
    e1.notes = "note1"
    e1.chain_depth = 0

    e2 = MagicMock()
    e2.source.cleaned_name = "A"
    e2.source.entity_type = "person"
    e2.target.cleaned_name = "B"
    e2.target.entity_type = "company"
    e2.relationship = "person_role"
    e2.relationship_detail = "CEO"
    e2.filing.accession = "A1"
    e2.notes = "note2"
    e2.chain_depth = 0

    merged = merge_and_deduplicate_edges([e1, e2])
    assert len(merged) == 1
    assert "note1" in merged[0].notes
    assert "note2" in merged[0].notes
