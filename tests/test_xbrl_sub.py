"""
tests/test_xbrl_sub.py

Tests for the XBRL SUB table parser (xbrl_sub.py).
Covers: loading, CIK/country lookups, co-registrant parsing,
name search, deduplication across periods, and header skipping.
"""

import io
import os
import zipfile
import tempfile
import pytest

from secmap.xbrl_sub import XBRLSubIndex, SubRecord, SUB_COLUMNS, COL_IDX

# ---------------------------------------------------------------------------
# Fixture path
# ---------------------------------------------------------------------------

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "test_period_notes")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_fixture() -> XBRLSubIndex:
    idx = XBRLSubIndex()
    idx.load_directory(FIXTURE_DIR)
    return idx


# ---------------------------------------------------------------------------
# Loading tests
# ---------------------------------------------------------------------------

class TestLoading:
    def test_load_directory_reads_tsv(self):
        idx = _load_fixture()
        assert idx._total_rows > 0

    def test_header_row_skipped(self):
        """The 'adsh' header row must not be ingested as a data record."""
        idx = _load_fixture()
        assert len(idx.by_cik("cik")) == 0
        assert len(idx.by_cik("adsh")) == 0

    def test_correct_row_count(self):
        """Fixture has 15 data rows (1 header + 15 data)."""
        idx = _load_fixture()
        # 15 rows but some share the same accession -- dedup by adsh
        assert idx._total_rows == 15

    def test_unique_cik_count(self):
        """Fixture has 13 unique CIKs across 15 rows."""
        idx = _load_fixture()
        assert len(idx._by_cik) == 13

    def test_load_from_zip(self):
        """Loading from a ZIP archive should produce the same results as directory load."""
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, "2024q1_notes.zip")
            fixture_tsv = os.path.join(FIXTURE_DIR, "sub.tsv")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.write(fixture_tsv, "sub.tsv")
            idx = XBRLSubIndex()
            idx.load_zip(zip_path)
            assert idx._total_rows == 15

    def test_period_deduplication(self):
        """Loading the same period twice should not double-count rows."""
        idx = _load_fixture()
        initial_count = idx._total_rows
        idx.load_directory(FIXTURE_DIR)  # reload same period
        assert idx._total_rows == initial_count

    def test_accession_deduplication(self):
        """The same accession number appearing in two periods is loaded only once."""
        idx = XBRLSubIndex()
        with tempfile.TemporaryDirectory() as tmp:
            fixture_tsv = os.path.join(FIXTURE_DIR, "sub.tsv")
            for period in ("2024q1_notes", "2024q2_notes"):
                period_dir = os.path.join(tmp, period)
                os.makedirs(period_dir)
                import shutil
                shutil.copy(fixture_tsv, os.path.join(period_dir, "sub.tsv"))
            idx.load_all_months(tmp)
        assert idx._total_rows == 15

    def test_stats_returns_correct_keys(self):
        idx = _load_fixture()
        s = idx.stats()
        for key in ("total_records", "unique_ciks", "unique_accessions",
                    "periods_loaded", "unique_countries", "unique_sic_codes",
                    "unique_form_types"):
            assert key in s

    def test_countryma_field_populated(self):
        """countryma field must be extracted (not missing from SubRecord)."""
        idx = _load_fixture()
        recs = idx.by_cik("100001")
        assert recs
        assert recs[0].countryma == "US"


# ---------------------------------------------------------------------------
# SubRecord.from_row tests
# ---------------------------------------------------------------------------

class TestSubRecordFromRow:
    def _make_row(self, **overrides):
        """Build a minimal valid 40-column row."""
        row = [""] * 40
        row[COL_IDX["adsh"]] = "0000099999-24-000099"
        row[COL_IDX["cik"]] = "999999"
        row[COL_IDX["name"]] = "TEST CORP"
        row[COL_IDX["sic"]] = "3714"
        row[COL_IDX["countryba"]] = "US"
        row[COL_IDX["countryma"]] = "US"
        row[COL_IDX["countryinc"]] = "US"
        row[COL_IDX["form"]] = "10-K"
        row[COL_IDX["filed"]] = "20240101"
        row[COL_IDX["nciks"]] = "1"
        row[COL_IDX["aciks"]] = ""
        for k, v in overrides.items():
            row[COL_IDX[k]] = v
        return row

    def test_valid_row_parses(self):
        row = self._make_row()
        rec = SubRecord.from_row(row)
        assert rec is not None
        assert rec.cik == "999999"
        assert rec.name == "TEST CORP"

    def test_empty_cik_returns_none(self):
        row = self._make_row(cik="")
        assert SubRecord.from_row(row) is None

    def test_short_row_returns_none(self):
        assert SubRecord.from_row(["a", "b", "c"]) is None

    def test_nciks_invalid_defaults_to_zero(self):
        row = self._make_row(nciks="not_a_number")
        rec = SubRecord.from_row(row)
        assert rec is not None
        assert rec.nciks == 0

    def test_countryma_extracted(self):
        row = self._make_row(countryma="HK")
        rec = SubRecord.from_row(row)
        assert rec.countryma == "HK"

    def test_former_name_extracted(self):
        row = self._make_row(former="OLD CORP NAME")
        rec = SubRecord.from_row(row)
        assert rec.former == "OLD CORP NAME"


# ---------------------------------------------------------------------------
# Lookup tests
# ---------------------------------------------------------------------------

class TestLookups:
    @pytest.fixture(autouse=True)
    def idx(self):
        self.idx = _load_fixture()

    def test_by_cik_us_company(self):
        recs = self.idx.by_cik("100001")
        assert len(recs) == 1
        assert recs[0].name == "ACME HOLDINGS INC"
        assert recs[0].countryinc == "US"

    def test_by_cik_chinese_company(self):
        recs = self.idx.by_cik("200001")
        assert len(recs) == 2  # two filings for same CIK
        assert all(r.countryba == "CN" for r in recs)

    def test_by_cik_cayman_china_intermediary(self):
        recs = self.idx.by_cik("300001")
        assert len(recs) == 1
        assert recs[0].countryba == "CN"
        assert recs[0].countryinc == "KY"

    def test_by_cik_unknown_returns_empty(self):
        assert self.idx.by_cik("999999") == []

    def test_by_country_cn(self):
        recs = self.idx.by_country("CN")
        ciks = {r.cik for r in recs}
        assert "200001" in ciks
        assert "300001" in ciks

    def test_by_country_case_insensitive(self):
        recs_upper = self.idx.by_country("CN")
        recs_lower = self.idx.by_country("cn")
        assert len(recs_upper) == len(recs_lower)

    def test_by_country_inc_ky(self):
        recs = self.idx.by_country_inc("KY")
        assert any(r.cik == "300001" for r in recs)

    def test_by_country_inc_us(self):
        recs = self.idx.by_country_inc("US")
        ciks = {r.cik for r in recs}
        assert "100001" in ciks
        assert "100002" in ciks

    def test_by_country_inc_excludes_ba_only(self):
        """CIK 300001 has countryba=CN but countryinc=KY -- should NOT appear in by_country_inc('CN')."""
        recs = self.idx.by_country_inc("CN")
        ciks = {r.cik for r in recs}
        assert "300001" not in ciks
        assert "200001" in ciks

    def test_by_sic_exact(self):
        recs = self.idx.by_sic("3714")
        ciks = {r.cik for r in recs}
        assert "100001" in ciks
        assert "100002" in ciks

    def test_by_sic_prefix(self):
        recs = self.idx.by_sic("29", prefix=True)
        ciks = {r.cik for r in recs}
        assert "400001" in ciks

    def test_by_form(self):
        recs = self.idx.by_form("10-K")
        assert all(r.form == "10-K" for r in recs)
        assert any(r.cik == "100001" for r in recs)

    def test_unique_ciks(self):
        ciks = self.idx.unique_ciks()
        assert "100001" in ciks
        assert "200001" in ciks
        assert "300001" in ciks


# ---------------------------------------------------------------------------
# Co-registrant tests
# ---------------------------------------------------------------------------

class TestCoRegistrants:
    @pytest.fixture(autouse=True)
    def idx(self):
        self.idx = _load_fixture()

    def test_single_parent_three_children(self):
        """CIK 100001 lists 3 co-registrants: 100002, 100003, 100004."""
        co = self.idx.co_registrants("100001")
        assert sorted(co) == ["100002", "100003", "100004"]

    def test_multi_cik_consolidation(self):
        """CIK 400001 lists 4 co-registrants: 400002, 400003, 400004, 400005."""
        co = self.idx.co_registrants("400001")
        assert sorted(co) == ["400002", "400003", "400004", "400005"]

    def test_no_co_registrants(self):
        """CIK 200001 (Chinese company) has no co-registrants."""
        co = self.idx.co_registrants("200001")
        assert co == []

    def test_co_registrant_excludes_self(self):
        """The parent CIK should never appear in its own co-registrant list."""
        co = self.idx.co_registrants("100001")
        assert "100001" not in co

    def test_co_registrants_across_multiple_filings(self):
        """CIK 400002 appears in two filings -- second adds CIK 400006 as co-registrant."""
        co = self.idx.co_registrants("400002")
        assert "400006" in co

    def test_unknown_cik_returns_empty(self):
        assert self.idx.co_registrants("999999") == []


# ---------------------------------------------------------------------------
# Search tests
# ---------------------------------------------------------------------------

class TestSearch:
    @pytest.fixture(autouse=True)
    def idx(self):
        self.idx = _load_fixture()

    def test_search_by_name_substring(self):
        results = self.idx.search("acme")
        ciks = {r.cik for r in results}
        assert "100001" in ciks

    def test_search_case_insensitive(self):
        upper = self.idx.search("DRAGON")
        lower = self.idx.search("dragon")
        assert {r.cik for r in upper} == {r.cik for r in lower}

    def test_search_by_former_name(self):
        """CIK 300001 has former name 'PACIFIC OCEAN INVESTMENTS LTD'."""
        results = self.idx.search("pacific ocean")
        ciks = {r.cik for r in results}
        assert "300001" in ciks

    def test_search_deduplicates_by_cik(self):
        """CIK 200001 has two filings -- search should return it only once."""
        results = self.idx.search("dragon tech")
        ciks = [r.cik for r in results]
        assert ciks.count("200001") == 1

    def test_search_returns_most_recent_filing(self):
        """When a CIK has multiple filings, search returns the most recently filed."""
        results = self.idx.search("dragon tech")
        dragon = next((r for r in results if r.cik == "200001"), None)
        assert dragon is not None
        assert dragon.filed == "20240605"  # most recent of the two

    def test_search_no_match_returns_empty(self):
        assert self.idx.search("xyzzy_nonexistent_corp") == []

    def test_search_former_name_widget(self):
        """CIK 500001 has former name 'WIDGET INDUSTRIES INC'."""
        results = self.idx.search("widget industries")
        ciks = {r.cik for r in results}
        assert "500001" in ciks
