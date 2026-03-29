import pytest
from secmap.institution_extractor import extract_institutions_from_narrative


def test_extract_basic_institution():
    text = "ABC Capital Partners LP executed the agreement."
    inst = extract_institutions_from_narrative(text)
    names = [e.cleaned_name for e, _ in inst]
    assert any("Capital" in n for n in names)


def test_extract_multiple_institutions():
    text = """
    Morgan Stanley & Co. LLC and
    Citigroup Global Markets Inc. are counterparties.
    """
    inst = extract_institutions_from_narrative(text)
    names = [e.cleaned_name for e, _ in inst]
    assert any("Morgan Stanley" in n for n in names)


def test_extract_institution_with_suffix_variants():
    text = "XYZ Asset Management executed the deal."
    inst = extract_institutions_from_narrative(text)
    assert any("XYZ Asset Management" in e.cleaned_name for e, _ in inst)


def test_no_false_positive_person_names():
    text = "John A. Smith signed the agreement."
    inst = extract_institutions_from_narrative(text)
    assert inst == []


def test_empty_input():
    assert extract_institutions_from_narrative("") == []


def test_exception_handling():
    assert extract_institutions_from_narrative(None) == []


def test_rejects_sentence_fragments():
    text = "Indicate by check mark whether the registrant is a large accelerated filer, an accelerated filer, a non-accelerated filer, or an emerging growth company"
    inst = extract_institutions_from_narrative(text)
    names = [e.cleaned_name for e, _ in inst]
    assert not any("Indicate" in n for n in names)
