"""
tests/test_exhibit21_parser.py

Tests for the Exhibit 21 subsidiary listing parser (exhibit21_parser.py).
Covers: HTML table extraction, plain text fallback, jurisdiction parsing,
ownership percentage extraction, and name normalization.
"""

import pytest

from secmap.exhibit21_parser import (
    _parse_html_table,
    _parse_plain_text,
    _clean_subsidiary_name,
    _normalize_jurisdiction,
    _extract_ownership_pct,
    _is_header_row,
    parse_exhibit21_text,
)


# ---------------------------------------------------------------------------
# HTML table extraction
# ---------------------------------------------------------------------------

SAMPLE_HTML_TABLE = """
<html><body>
<table>
<tr><td><b>Name of Subsidiary</b></td><td><b>Jurisdiction of Organization</b></td></tr>
<tr><td>Alpha Manufacturing LLC</td><td>Delaware</td></tr>
<tr><td>Beta International Ltd.</td><td>United Kingdom</td></tr>
<tr><td>Gamma Holdings B.V.</td><td>Netherlands</td></tr>
<tr><td>Delta Logistics S.r.l.</td><td>Luxembourg</td></tr>
<tr><td>Epsilon Trading AG</td><td>Switzerland</td></tr>
</table>
</body></html>
"""

SAMPLE_HTML_WITH_PCT = """
<html><body>
<table>
<tr><td>Name of Subsidiary</td><td>Jurisdiction</td><td>Ownership</td></tr>
<tr><td>Sub One LLC</td><td>Delaware</td><td>100%</td></tr>
<tr><td>Sub Two Inc.</td><td>California</td><td>80.5%</td></tr>
<tr><td>Sub Three GmbH</td><td>Germany</td><td>wholly-owned</td></tr>
</table>
</body></html>
"""

SAMPLE_HTML_NESTED = """
<html><body>
<table>
<tr><td><font style="font-weight:700">Name of Subsidiary:</font></td>
    <td><font style="font-weight:700">Jurisdiction of Organization:</font></td></tr>
<tr><td><div><font>Ag Protein, Inc.</font></div></td>
    <td><div><font>North Carolina</font></div></td></tr>
<tr><td><div><font>Murphy-Brown LLC</font></div></td>
    <td><div><font>Delaware</font></div></td></tr>
</table>
</body></html>
"""


class TestHTMLTableExtraction:
    def test_basic_table(self):
        entries = _parse_html_table(SAMPLE_HTML_TABLE)
        assert len(entries) == 5
        names = {e.name for e in entries}
        assert "Alpha Manufacturing LLC" in names
        assert "Epsilon Trading AG" in names

    def test_jurisdictions_extracted(self):
        entries = _parse_html_table(SAMPLE_HTML_TABLE)
        jur_map = {e.name: e.jurisdiction for e in entries}
        assert jur_map["Alpha Manufacturing LLC"] == "Delaware"
        assert jur_map["Beta International Ltd."] == "United Kingdom"
        assert jur_map["Gamma Holdings B.V."] == "Netherlands"

    def test_header_row_skipped(self):
        entries = _parse_html_table(SAMPLE_HTML_TABLE)
        names = {e.name for e in entries}
        assert "Name of Subsidiary" not in names

    def test_ownership_percentage_from_third_column(self):
        entries = _parse_html_table(SAMPLE_HTML_WITH_PCT)
        pct_map = {e.name: e.ownership_pct for e in entries}
        assert pct_map["Sub One LLC"] == 100.0
        assert pct_map["Sub Two Inc."] == 80.5
        assert pct_map["Sub Three GmbH"] == 100.0  # wholly-owned

    def test_nested_font_tags(self):
        """Real-world Exhibit 21 uses deeply nested <div><font> inside <td>."""
        entries = _parse_html_table(SAMPLE_HTML_NESTED)
        assert len(entries) == 2
        names = {e.name for e in entries}
        assert "Ag Protein, Inc." in names
        assert "Murphy-Brown LLC" in names

    def test_empty_html_returns_empty(self):
        assert _parse_html_table("") == []
        assert _parse_html_table("<html><body></body></html>") == []

    def test_table_with_no_data_rows(self):
        html = "<table><tr><td>Name of Subsidiary</td><td>Jurisdiction</td></tr></table>"
        entries = _parse_html_table(html)
        assert len(entries) == 0


# ---------------------------------------------------------------------------
# Plain text extraction
# ---------------------------------------------------------------------------

SAMPLE_PLAIN_TEXT = """
EXHIBIT 21

SUBSIDIARIES OF THE REGISTRANT

Name of Subsidiary                          Jurisdiction of Incorporation
--------------------------                  ----------------------------
Alpha Manufacturing LLC                     Delaware
Beta International Ltd.                     United Kingdom
Gamma Holdings B.V.                         Netherlands
Delta Logistics S.r.l.                      Luxembourg
"""


class TestPlainTextExtraction:
    def test_basic_text(self):
        entries = _parse_plain_text(SAMPLE_PLAIN_TEXT)
        assert len(entries) >= 4
        names = {e.name for e in entries}
        assert "Alpha Manufacturing LLC" in names

    def test_header_skipped(self):
        entries = _parse_plain_text(SAMPLE_PLAIN_TEXT)
        names = {e.name for e in entries}
        assert "Name of Subsidiary" not in names

    def test_separator_lines_skipped(self):
        entries = _parse_plain_text(SAMPLE_PLAIN_TEXT)
        names = {e.name for e in entries}
        for name in names:
            assert "---" not in name

    def test_empty_text_returns_empty(self):
        assert _parse_plain_text("") == []


# ---------------------------------------------------------------------------
# parse_exhibit21_text (unified parser)
# ---------------------------------------------------------------------------

class TestUnifiedParser:
    def test_html_input(self):
        entries = parse_exhibit21_text(SAMPLE_HTML_TABLE)
        assert len(entries) == 5

    def test_plain_text_input(self):
        entries = parse_exhibit21_text(SAMPLE_PLAIN_TEXT)
        assert len(entries) >= 4

    def test_none_input(self):
        assert parse_exhibit21_text("") == []
        assert parse_exhibit21_text(None) == []


# ---------------------------------------------------------------------------
# Jurisdiction normalization
# ---------------------------------------------------------------------------

class TestJurisdictionNormalization:
    @pytest.mark.parametrize("input_val,expected", [
        ("DE", "Delaware"),
        ("CA", "California"),
        ("NY", "New York"),
        ("TX", "Texas"),
        ("OH", "Ohio"),
        ("NC", "North Carolina"),
    ])
    def test_state_abbreviations(self, input_val, expected):
        assert _normalize_jurisdiction(input_val) == expected

    def test_full_name_unchanged(self):
        assert _normalize_jurisdiction("Delaware") == "Delaware"
        assert _normalize_jurisdiction("United Kingdom") == "United Kingdom"

    def test_whitespace_stripped(self):
        assert _normalize_jurisdiction("  Delaware  ") == "Delaware"

    def test_trailing_punctuation_stripped(self):
        assert _normalize_jurisdiction("Delaware.") == "Delaware"
        assert _normalize_jurisdiction("Delaware,") == "Delaware"


# ---------------------------------------------------------------------------
# Ownership percentage extraction
# ---------------------------------------------------------------------------

class TestOwnershipPercentage:
    def test_numeric_percent(self):
        assert _extract_ownership_pct("100%") == 100.0
        assert _extract_ownership_pct("80.5%") == 80.5
        assert _extract_ownership_pct("51 %") == 51.0

    def test_wholly_owned(self):
        assert _extract_ownership_pct("wholly-owned") == 100.0
        assert _extract_ownership_pct("Wholly Owned") == 100.0

    def test_hundred_percent_owned(self):
        assert _extract_ownership_pct("100% owned") == 100.0

    def test_no_percentage(self):
        assert _extract_ownership_pct("Delaware") is None
        assert _extract_ownership_pct("") is None
        assert _extract_ownership_pct(None) is None

    def test_invalid_percentage_ignored(self):
        """Percentages > 100 should be ignored."""
        assert _extract_ownership_pct("150%") is None


# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------

class TestNameNormalization:
    def test_leading_bullets_removed(self):
        assert _clean_subsidiary_name("- Alpha Corp") == "Alpha Corp"
        assert _clean_subsidiary_name("* Beta LLC") == "Beta LLC"

    def test_leading_dashes_removed(self):
        assert _clean_subsidiary_name("-- Gamma Inc.") == "Gamma Inc."

    def test_trailing_footnotes_removed(self):
        assert _clean_subsidiary_name("Delta Corp (1)") == "Delta Corp"
        assert _clean_subsidiary_name("Epsilon LLC [a]") == "Epsilon LLC"

    def test_trailing_asterisks_removed(self):
        assert _clean_subsidiary_name("Zeta Holdings **") == "Zeta Holdings"

    def test_whitespace_collapsed(self):
        assert _clean_subsidiary_name("  Alpha   Beta   Corp  ") == "Alpha Beta Corp"

    def test_normal_name_unchanged(self):
        assert _clean_subsidiary_name("Normal Company LLC") == "Normal Company LLC"


# ---------------------------------------------------------------------------
# Header detection
# ---------------------------------------------------------------------------

class TestHeaderDetection:
    def test_name_of_subsidiary_header(self):
        assert _is_header_row(["Name of Subsidiary", "Jurisdiction"])

    def test_jurisdiction_header(self):
        assert _is_header_row(["Entity", "State or Other Jurisdiction of Incorporation"])

    def test_data_row_not_header(self):
        assert not _is_header_row(["Alpha Corp", "Delaware"])

    def test_empty_not_header(self):
        assert not _is_header_row([])
