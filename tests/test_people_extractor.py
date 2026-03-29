import pytest
from secmap.people_extractor import (
    extract_people_from_signatures,
    extract_people_from_narrative,
)


def test_extract_standard_name():
    text = "/s/ John A. SmithChief Executive Officer"
    people = extract_people_from_signatures(text)
    assert any("John" in p.cleaned_name and "Smith" in p.cleaned_name for p in people)


def test_extract_slash_s_format():
    text = "/s/ Jane Doe\nTitle: Secretary"
    people = extract_people_from_signatures(text)
    assert any(p.cleaned_name == "Jane Doe" for p in people)


def test_extract_by_format():
    text = "By: Robert J. Green\nTitle: Director"
    people = extract_people_from_signatures(text)
    assert any("Robert" in p.cleaned_name and "Green" in p.cleaned_name for p in people)


def test_extract_concatenated_title():
    text = "/s/ Long WanChairmanMarch 24, 2026"
    people = extract_people_from_signatures(text)
    assert any(p.cleaned_name == "Long Wan" for p in people)


def test_extract_multiple_signatures():
    text = "/s/ John DoeDirector/s/ Jane SmithSecretary"
    people = extract_people_from_signatures(text)
    assert len(people) == 2


def test_extract_name_age_from_narrative():
    text = "Alice M. Johnson, age 52, has served as Director since 2020."
    people = extract_people_from_narrative(text)
    assert any("Alice" in p.cleaned_name for p in people)


def test_extract_name_title_from_narrative():
    text = "Bob Lee, director of the company"
    people = extract_people_from_narrative(text)
    assert any("Bob Lee" in p.cleaned_name for p in people)


def test_empty_input():
    assert extract_people_from_signatures("") == []
    assert extract_people_from_narrative("") == []


def test_exception_handling():
    assert extract_people_from_signatures(None) == []


def test_rejects_org_names():
    text = "/s/ BlackRock Fund Managers Ltd\nTitle: Agent"
    people = extract_people_from_signatures(text)
    assert people == []


def test_no_false_positives_from_boilerplate():
    text = "Securities Exchange Act of 1934. The People of the United States."
    people = extract_people_from_narrative(text)
    assert people == []
