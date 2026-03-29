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


# --- Adversarial nations ---

def test_china_city_inference():
    assert infer_jurisdiction("Shanghai Holdings Group") == "China"


def test_russia_inference():
    assert infer_jurisdiction("Moscow Industrial Trading") == "Russia"


def test_iran_inference():
    assert infer_jurisdiction("Tehran Petrochemical Corp") == "Iran"


def test_north_korea_inference():
    assert infer_jurisdiction("Pyongyang Trading Company") == "North Korea"


# --- Conduit jurisdictions ---

def test_hong_kong_inference():
    assert infer_jurisdiction("Hong Kong Ventures Ltd") == "Hong Kong"


def test_uae_inference():
    assert infer_jurisdiction("Dubai International Holdings") == "United Arab Emirates"


def test_cyprus_inference():
    assert infer_jurisdiction("Limassol Shipping Corp") == "Cyprus"


# --- Opacity jurisdictions ---

def test_cayman_inference():
    assert infer_jurisdiction("Grand Cayman SPV Holdings") == "Cayman Islands"


def test_bvi_inference():
    assert infer_jurisdiction("BVI Investment Holdings") == "British Virgin Islands"


def test_maldives_inference():
    assert infer_jurisdiction("Male Trading Corporation") == "Maldives"


def test_seychelles_inference():
    assert infer_jurisdiction("Seychelles Offshore Holdings") == "Seychelles"


# --- Risk tier API ---

def test_risk_tier_adversarial():
    assert get_risk_tier("China") == RISK_ADVERSARIAL
    assert get_risk_tier("Russia") == RISK_ADVERSARIAL
    assert get_risk_tier("Iran") == RISK_ADVERSARIAL
    assert get_risk_tier("North Korea") == RISK_ADVERSARIAL


def test_risk_tier_conduit():
    assert get_risk_tier("Hong Kong") == RISK_CONDUIT
    assert get_risk_tier("Cyprus") == RISK_CONDUIT


def test_risk_tier_opacity():
    assert get_risk_tier("Cayman Islands") == RISK_OPACITY
    assert get_risk_tier("British Virgin Islands") == RISK_OPACITY


def test_risk_tier_standard():
    assert get_risk_tier("United States") == RISK_STANDARD
    assert get_risk_tier("United Kingdom") == RISK_STANDARD


def test_infer_with_risk_returns_tier():
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


def test_adversarial_countries_list():
    countries = get_all_adversarial_countries()
    assert "China" in countries
    assert "Russia" in countries
    assert "Iran" in countries
    assert "North Korea" in countries


def test_opacity_jurisdictions_list():
    jurisdictions = get_all_opacity_jurisdictions()
    assert "Cayman Islands" in jurisdictions
    assert "British Virgin Islands" in jurisdictions
    assert "Seychelles" in jurisdictions
    assert "Maldives" in jurisdictions


def test_conduit_jurisdictions_list():
    jurisdictions = get_all_conduit_jurisdictions()
    assert "Hong Kong" in jurisdictions
    assert "Cyprus" in jurisdictions
    assert "United Arab Emirates" in jurisdictions
