import pytest
from secmap.sc13_parser import parse_sc13_beneficial_ownership


def test_empty_input():
    assert parse_sc13_beneficial_ownership("") == []


def test_basic_sc13_parsing():
    text = """
    Name of Reporting Person:
    John Doe

    Percent of Class:
    5.2%

    Title of Class of Securities:
    Common Stock
    """

    entries = parse_sc13_beneficial_ownership(text)
    assert len(entries) == 1
    assert entries[0].reporting_person.cleaned_name == "John Doe"
    assert entries[0].percent_of_class == 5.2
    assert entries[0].class_title == "Common Stock"


def test_multiple_entries():
    text = """
    Name of Reporting Person:
    Alice Smith
    Name of Reporting Person:
    Bob Jones

    Percent of Class:
    3.1%
    Percent of Class:
    7.8%

    Title of Class of Securities:
    Class A
    Title of Class of Securities:
    Class B
    """

    entries = parse_sc13_beneficial_ownership(text)
    assert len(entries) == 2
    assert entries[0].reporting_person.cleaned_name == "Alice Smith"
    assert entries[1].reporting_person.cleaned_name == "Bob Jones"


def test_misaligned_lists():
    text = """
    Name of Reporting Person:
    Alice Smith

    Percent of Class:
    4.0%
    Percent of Class:
    6.0%

    Title of Class of Securities:
    Common Stock
    """

    entries = parse_sc13_beneficial_ownership(text)
    # Only 1 name present, so only 1 entry despite 2 percents
    assert len(entries) == 1
    assert entries[0].reporting_person.cleaned_name == "Alice Smith"
    assert entries[0].percent_of_class == 4.0


def test_malformed_percent():
    text = """
    Name of Reporting Person:
    John Doe

    Percent of Class:
    not_a_number%

    Title of Class of Securities:
    Common Stock
    """

    entries = parse_sc13_beneficial_ownership(text)
    assert len(entries) == 1
    assert entries[0].percent_of_class is None
