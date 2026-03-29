import pytest
from secmap.parse_filings import (
    strip_html,
    normalize_text,
    extract_signature_block,
    extract_narrative_section,
    extract_country_mentions,
    parse_filing_to_sections,
)


def test_strip_html_basic():
    html = "<p>Hello<br>World</p>"
    result = strip_html(html)
    assert "Hello" in result
    assert "World" in result


def test_strip_html_handles_entities():
    html = "Tom &amp; Jerry"
    assert strip_html(html) == "Tom & Jerry"


def test_normalize_text_collapses_spaces():
    raw = "Hello   World\n\n\nTest"
    assert normalize_text(raw) == "Hello World\n\nTest"


def test_extract_signature_block_basic():
    text = "SIGNATURES\nJohn Doe\nCFO\nEXHIBIT"
    block = extract_signature_block(text)
    assert "John Doe" in block
    assert "CFO" in block


def test_extract_signature_block_missing():
    assert extract_signature_block("No signatures here") == ""


def test_extract_narrative_section_basic():
    text = "Some text\nDIRECTORS AND EXECUTIVE OFFICERS\nAlice is CEO"
    section = extract_narrative_section(text)
    assert "Alice" in section


def test_extract_country_mentions():
    text = "Operations in China and the United States"
    countries = extract_country_mentions(text)
    assert "China" in countries
    assert "United States" in countries


def test_parse_filing_to_sections_basic():
    raw = "<p>SIGNATURES</p>John Doe<br>EXHIBIT"
    sections = parse_filing_to_sections(raw)
    assert "John Doe" in sections["signatures"]
    assert sections["full_text"] != ""
