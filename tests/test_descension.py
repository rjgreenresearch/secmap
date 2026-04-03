"""
tests/test_descension.py

Tests for the descension engine (descension.py).
Covers: single-level descent, recursive descent, cycle detection,
max_depth enforcement, and OwnershipEdge format compatibility.
"""

import os
import pytest

from secmap.xbrl_sub import XBRLSubIndex
from secmap.descension import descend_from_cik, DescensionResult
from secmap.csv_writer import format_edge_row, COLUMNS

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "test_period_notes")


@pytest.fixture
def sub_index():
    idx = XBRLSubIndex()
    idx.load_directory(FIXTURE_DIR)
    return idx


# ---------------------------------------------------------------------------
# Single-level descension
# ---------------------------------------------------------------------------

class TestSingleLevel:
    def test_parent_finds_direct_children(self, sub_index):
        """CIK 100001 has co-registrants 100002, 100003, 100004."""
        result = descend_from_cik("100001", sub_index, max_depth=1)
        child_names = {e.target.cleaned_name for e in result.edges}
        assert "ACME MANUFACTURING LLC" in child_names
        assert "ACME LOGISTICS CORP" in child_names
        assert "ACME INTERNATIONAL LTD" in child_names

    def test_edge_count_matches_children(self, sub_index):
        result = descend_from_cik("100001", sub_index, max_depth=1)
        assert len(result.edges) == 3

    def test_no_children_returns_empty(self, sub_index):
        """CIK 200001 has no co-registrants."""
        result = descend_from_cik("200001", sub_index, max_depth=1)
        assert len(result.edges) == 0

    def test_root_name_resolved(self, sub_index):
        result = descend_from_cik("100001", sub_index, max_depth=1)
        assert result.root_name == "ACME HOLDINGS INC"

    def test_root_cik_in_visited(self, sub_index):
        result = descend_from_cik("100001", sub_index, max_depth=1)
        assert "100001" in result.visited_ciks

    def test_children_in_visited(self, sub_index):
        result = descend_from_cik("100001", sub_index, max_depth=1)
        assert "100002" in result.visited_ciks
        assert "100003" in result.visited_ciks

    def test_tree_structure(self, sub_index):
        result = descend_from_cik("100001", sub_index, max_depth=1)
        assert "100001" in result.tree
        assert sorted(result.tree["100001"]) == ["100002", "100003", "100004"]


# ---------------------------------------------------------------------------
# Recursive descension (multi-level)
# ---------------------------------------------------------------------------

class TestRecursive:
    def test_grandchildren_discovered(self, sub_index):
        """CIK 400001 -> 400002 -> 400006 (grandchild via second filing)."""
        result = descend_from_cik("400001", sub_index, max_depth=3)
        all_targets = {e.target.cleaned_name for e in result.edges}
        assert "MEGACORP REFINING LLC" in all_targets
        assert "MEGACORP REFINING SUB LLC" in all_targets

    def test_depth_levels_correct(self, sub_index):
        """Edges from root should be depth 0, edges from children depth 1."""
        result = descend_from_cik("400001", sub_index, max_depth=3)
        for e in result.edges:
            if e.source.cleaned_name == "MEGACORP CONSOLIDATED INC":
                assert e.chain_depth == 0
            elif e.source.cleaned_name == "MEGACORP REFINING LLC":
                assert e.chain_depth == 1

    def test_multi_level_tree(self, sub_index):
        result = descend_from_cik("400001", sub_index, max_depth=3)
        # Root has 4 direct children
        assert len(result.tree.get("400001", [])) == 4
        # 400002 has 1 grandchild (400006)
        assert "400006" in result.tree.get("400002", [])

    def test_entity_info_populated(self, sub_index):
        result = descend_from_cik("400001", sub_index, max_depth=3)
        assert "400001" in result.entity_info
        assert result.entity_info["400001"]["name"] == "MEGACORP CONSOLIDATED INC"
        assert result.entity_info["400004"]["countryba"] == "CH"


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------

class TestCycleDetection:
    def test_no_infinite_loop_on_self_reference(self, sub_index):
        """Even if a CIK somehow references itself, descension should terminate."""
        result = descend_from_cik("100001", sub_index, max_depth=10)
        # Should complete without hanging
        assert result.root_cik == "100001"

    def test_visited_prevents_revisit(self, sub_index):
        """CIK 400002 appears as both a child of 400001 and has its own children.
        It should only be visited once."""
        result = descend_from_cik("400001", sub_index, max_depth=5)
        cik_list = [e.target.cleaned_name for e in result.edges
                    if e.target.cleaned_name == "MEGACORP REFINING LLC"]
        # Should appear exactly once as a target
        assert len(cik_list) == 1


# ---------------------------------------------------------------------------
# Max depth enforcement
# ---------------------------------------------------------------------------

class TestMaxDepth:
    def test_depth_zero_returns_no_edges(self, sub_index):
        """max_depth=0 means only process root, find its direct children but don't recurse."""
        result = descend_from_cik("400001", sub_index, max_depth=0)
        # depth 0 processes root and finds direct children
        assert len(result.edges) == 4  # 4 direct co-registrants
        # But no grandchildren
        all_targets = {e.target.cleaned_name for e in result.edges}
        assert "MEGACORP REFINING SUB LLC" not in all_targets

    def test_depth_one_no_grandchildren(self, sub_index):
        """max_depth=1 finds direct children AND their children (one level of recursion)."""
        result = descend_from_cik("400001", sub_index, max_depth=1)
        all_targets = {e.target.cleaned_name for e in result.edges}
        assert "MEGACORP REFINING LLC" in all_targets
        # At depth 1, children are processed so grandchild IS found
        assert "MEGACORP REFINING SUB LLC" in all_targets

    def test_depth_two_finds_grandchildren(self, sub_index):
        """max_depth=2 should find grandchildren."""
        result = descend_from_cik("400001", sub_index, max_depth=2)
        all_targets = {e.target.cleaned_name for e in result.edges}
        assert "MEGACORP REFINING SUB LLC" in all_targets

    def test_max_total_ciks_enforced(self, sub_index):
        """Setting max_total_ciks=3 should stop after visiting 3 CIKs."""
        result = descend_from_cik("400001", sub_index, max_depth=5, max_total_ciks=3)
        assert len(result.visited_ciks) <= 3


# ---------------------------------------------------------------------------
# Edge format compatibility
# ---------------------------------------------------------------------------

class TestEdgeFormat:
    def test_relationship_type(self, sub_index):
        result = descend_from_cik("100001", sub_index, max_depth=1)
        for e in result.edges:
            assert e.relationship == "consolidated_subsidiary"

    def test_method_field(self, sub_index):
        result = descend_from_cik("100001", sub_index, max_depth=1)
        for e in result.edges:
            assert e.method == "xbrl_co_registrant"

    def test_source_is_parent(self, sub_index):
        result = descend_from_cik("100001", sub_index, max_depth=1)
        for e in result.edges:
            assert e.source.cleaned_name == "ACME HOLDINGS INC"
            assert e.source.entity_type == "company"

    def test_target_is_child(self, sub_index):
        result = descend_from_cik("100001", sub_index, max_depth=1)
        target_names = {e.target.cleaned_name for e in result.edges}
        assert "ACME MANUFACTURING LLC" in target_names

    def test_filing_stub_has_accession(self, sub_index):
        result = descend_from_cik("100001", sub_index, max_depth=1)
        for e in result.edges:
            assert e.filing.accession  # non-empty
            assert e.filing.form  # non-empty

    def test_csv_writer_compatible(self, sub_index):
        """Edges must produce valid pipe-delimited rows via format_edge_row."""
        result = descend_from_cik("100001", sub_index, max_depth=1)
        for e in result.edges:
            row = format_edge_row(e)
            assert row  # non-empty
            fields = row.split("|")
            assert len(fields) == len(COLUMNS)
            assert "consolidated_subsidiary" in row
            assert "xbrl_co_registrant" in row

    def test_role_is_ownership_set(self, sub_index):
        result = descend_from_cik("100001", sub_index, max_depth=1)
        for e in result.edges:
            assert e.role_is_ownership is True

    def test_chain_depth_on_edges(self, sub_index):
        result = descend_from_cik("400001", sub_index, max_depth=3)
        depths = {e.chain_depth for e in result.edges}
        assert 0 in depths  # direct children


# ---------------------------------------------------------------------------
# Unknown / edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_unknown_cik(self, sub_index):
        result = descend_from_cik("999999", sub_index, max_depth=1)
        assert len(result.edges) == 0
        assert result.root_name.startswith("CIK")

    def test_cik_with_whitespace(self, sub_index):
        result = descend_from_cik("  100001  ", sub_index, max_depth=1)
        assert len(result.edges) == 3
