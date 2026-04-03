import pytest
from secmap.jurisdiction_inference import (
    infer_jurisdiction,
    infer_jurisdiction_with_risk,
    get_risk_tier,
    get_all_adversarial_countries,
    get_all_opacity_jurisdictions,
    get_all_conduit_jurisdictions,
    RISK_ADVERSARIAL,
    RISK_CONDUIT,
    RISK_OPACITY,
    RISK_STANDARD,
)


# ---------------------------------------------------------------------------
# Core inference
# ---------------------------------------------------------------------------

def test_issuer_country_override():
    assert infer_jurisdiction("TestCorp", issuer_country="China") == "China"


def test_name_based_inference():
    assert infer_jurisdiction("China National Petroleum Corp") == "China"
    assert infer_jurisdiction("Japan Electric Co.") == "Japan"


def test_context_based_inference():
    text = "The company operates primarily in the United States."
    assert infer_jurisdiction("Generic Name", context_text=text) == "United States"


def test_no_inference():
    assert infer_jurisdiction("XJ-129 Special Vehicle") is None


def test_empty_name():
    assert infer_jurisdiction("") is None


def test_exception_handling():
    assert infer_jurisdiction(None) is None


# ---------------------------------------------------------------------------
# Country inference -- parametrized across all tiers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("entity_name,expected_country", [
    # Adversarial
    ("Shanghai Holdings Group", "China"),
    ("Moscow Industrial Trading", "Russia"),
    ("Tehran Petrochemical Corp", "Iran"),
    ("Pyongyang Trading Company", "North Korea"),
    # Conduit
    ("Hong Kong Ventures Ltd", "Hong Kong"),
    ("Dubai International Holdings", "United Arab Emirates"),
    ("Limassol Shipping Corp", "Cyprus"),
    # Opacity
    ("Grand Cayman SPV Holdings", "Cayman Islands"),
    ("BVI Investment Holdings", "British Virgin Islands"),
    ("Male Trading Corporation", "Maldives"),
    ("Seychelles Offshore Holdings", "Seychelles"),
])
def test_country_inference(entity_name, expected_country):
    assert infer_jurisdiction(entity_name) == expected_country


# ---------------------------------------------------------------------------
# Risk tier API -- parametrized
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("country,expected_tier", [
    ("China", RISK_ADVERSARIAL),
    ("Russia", RISK_ADVERSARIAL),
    ("Iran", RISK_ADVERSARIAL),
    ("North Korea", RISK_ADVERSARIAL),
    ("Hong Kong", RISK_CONDUIT),
    ("Cyprus", RISK_CONDUIT),
    ("Cayman Islands", RISK_OPACITY),
    ("British Virgin Islands", RISK_OPACITY),
    ("United States", RISK_STANDARD),
    ("United Kingdom", RISK_STANDARD),
])
def test_risk_tier(country, expected_tier):
    assert get_risk_tier(country) == expected_tier


# ---------------------------------------------------------------------------
# infer_jurisdiction_with_risk
# ---------------------------------------------------------------------------

def test_infer_with_risk_adversarial():
    result = infer_jurisdiction_with_risk("Beijing Capital Holdings")
    assert result is not None
    assert result.country == "China"
    assert result.risk_tier == RISK_ADVERSARIAL


def test_infer_with_risk_conduit():
    result = infer_jurisdiction_with_risk("Dubai Free Zone Entity")
    assert result is not None
    assert result.risk_tier == RISK_CONDUIT


def test_infer_with_risk_none():
    result = infer_jurisdiction_with_risk("XJ-129 Special Vehicle")
    assert result is None


# ---------------------------------------------------------------------------
# List API
# ---------------------------------------------------------------------------

def test_adversarial_countries_list():
    countries = get_all_adversarial_countries()
    assert {"China", "Russia", "Iran", "North Korea"} <= set(countries)


def test_opacity_jurisdictions_list():
    jurisdictions = get_all_opacity_jurisdictions()
    assert {"Cayman Islands", "British Virgin Islands", "Seychelles"} <= set(jurisdictions)


def test_conduit_jurisdictions_list():
    jurisdictions = get_all_conduit_jurisdictions()
    assert {"Hong Kong", "Cyprus", "United Arab Emirates"} <= set(jurisdictions)
