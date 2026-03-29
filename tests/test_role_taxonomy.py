import pytest
from secmap.role_taxonomy import classify_role, RoleClassification


def test_classify_role_basic_ceo():
    text = "John Doe, Chief Executive Officer of the Company"
    role = classify_role("John Doe", text)
    assert role.canonical_role == "CEO"
    assert role.confidence > 0.5
    assert role.is_executive is True


def test_classify_role_director():
    text = "Jane Smith has served as a Director of the company"
    role = classify_role("Jane Smith", text)
    assert role.canonical_role == "Director"
    assert role.is_board is True


def test_classify_role_unknown():
    text = "John Doe is involved in operations"
    role = classify_role("John Doe", text)
    assert role.canonical_role == "Unknown"


def test_classify_role_no_context():
    role = classify_role("John Doe", "")
    assert role.canonical_role == "Unknown"


def test_classify_role_name_not_found():
    text = "The Chief Financial Officer oversees financial operations"
    role = classify_role("Alice", text)
    assert role.canonical_role in ["CFO", "Unknown"]


def test_classify_role_handles_exceptions():
    role = classify_role(None, "CEO")
    assert role.canonical_role == "Unknown"


# --- Ownership chain roles ---

def test_beneficial_owner():
    text = "John Doe is the ultimate beneficial owner of 15% of common stock"
    role = classify_role("John Doe", text)
    assert role.canonical_role == "Beneficial Owner"
    assert role.is_ownership is True


def test_controlling_person():
    text = "ABC Holdings is the controlling shareholder of the issuer"
    role = classify_role("ABC Holdings", text)
    assert role.canonical_role == "Controlling Person"
    assert role.is_ownership is True


# --- Obscuring / layering roles ---

def test_nominee_role():
    text = "Shares held by Pacific Trust as nominee shareholder"
    role = classify_role("Pacific Trust", text)
    assert role.canonical_role == "Nominee"
    assert role.is_obscuring is True


def test_proxy_role():
    text = "Jane Doe holds power of attorney for the entity"
    role = classify_role("Jane Doe", text)
    assert role.canonical_role == "Proxy"
    assert role.is_obscuring is True


def test_intermediary_role():
    text = "Alpha Corp acts as intermediary between the parties"
    role = classify_role("Alpha Corp", text)
    assert role.canonical_role == "Intermediary"
    assert role.is_obscuring is True


def test_registered_agent():
    text = "CT Corporation serves as registered agent in Delaware"
    role = classify_role("CT Corporation", text)
    assert role.canonical_role == "Agent"
    assert role.is_obscuring is True
