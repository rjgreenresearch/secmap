import pytest

from secmap.entity_classification import (
    normalize_name,
    classify_entity_type,
    make_entity,
)


def test_normalize_name_basic():
    assert normalize_name("  John   Doe ") == "John Doe"


def test_normalize_name_empty():
    assert normalize_name("") == ""


def test_classify_entity_type_person():
    assert classify_entity_type("John Doe") == "person"
    assert classify_entity_type("Alice M. Smith") == "person"


def test_classify_entity_type_institution():
    assert classify_entity_type("Big Bank Corp.") == "institution"
    assert classify_entity_type("Alpha Capital Partners LP") == "institution"


def test_classify_entity_type_unknown():
    assert classify_entity_type("XJ-129 Special Vehicle") == "unknown"


def test_make_entity_with_explicit_type():
    e = make_entity("Custom Name", explicit_type="company")
    assert e.cleaned_name == "Custom Name"
    assert e.entity_type == "company"


def test_make_entity_heuristic():
    e = make_entity("John Doe")
    assert e.entity_type == "person"
