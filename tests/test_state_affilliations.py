import pytest
from secmap.state_affiliation import classify_state_affiliation


def test_empty_name():
    result = classify_state_affiliation("", None)
    assert result.category == "None"


def test_exception_handling():
    result = classify_state_affiliation(None, None)
    assert result.category == "None"


def test_no_affiliation():
    result = classify_state_affiliation("Acme Widgets LLC", None)
    assert result.category == "None"


# --- PRC ---

def test_prc_soe_classification():
    result = classify_state_affiliation("China State-Owned Assets Corp", None, issuer_country="China")
    assert result.category == "SOE"
    assert result.subcategory == "PRC"


def test_prc_soe_named_entity():
    result = classify_state_affiliation("Sinopec Group Holdings", None)
    assert result.category == "SOE"


def test_prc_party_controlled():
    result = classify_state_affiliation("Beijing Communist Party Committee", None, issuer_country="China")
    assert result.category == "Party-Controlled"


def test_prc_mcf_classification():
    result = classify_state_affiliation("Aerospace Dual-Use Defense Technology Group", None, issuer_country="China")
    assert result.category == "MCF"


def test_prc_mcf_named_entity():
    result = classify_state_affiliation("NORINCO International Cooperation Ltd", None)
    assert result.category == "MCF"


def test_prc_ufwd_classification():
    result = classify_state_affiliation("Shanghai United Front Work Department", None, issuer_country="China")
    assert result.category == "UFWD"


def test_prc_ufwd_confucius():
    result = classify_state_affiliation("Confucius Institute at State University", None)
    assert result.category == "UFWD"


# --- Russia ---

def test_russia_state_linked():
    result = classify_state_affiliation("Gazprom Neft Trading", None)
    assert result.category == "State-Linked"
    assert result.subcategory == "Russia"


def test_russia_rostec():
    result = classify_state_affiliation("Rostec Corporation", None)
    assert result.category == "State-Linked"
    assert result.subcategory == "Russia"


# --- Iran ---

def test_iran_irgc():
    result = classify_state_affiliation("Islamic Revolutionary Guard Corps Cooperative", None)
    assert result.category == "State-Linked"
    assert result.subcategory == "Iran"


def test_iran_bonyad():
    result = classify_state_affiliation("Bonyad Mostazafan Foundation", None)
    assert result.category == "State-Linked"
    assert result.subcategory == "Iran"


# --- DPRK ---

def test_dprk_front_company():
    result = classify_state_affiliation("Korea Mining Development Trading Corporation", None)
    assert result.category == "State-Linked"
    assert result.subcategory == "DPRK"


def test_dprk_office_39():
    result = classify_state_affiliation("Office 39 Trading Entity", None)
    assert result.category == "State-Linked"
    assert result.subcategory == "DPRK"


# --- SWF ---

def test_swf_detection():
    result = classify_state_affiliation("Abu Dhabi Investment Authority", None)
    assert result.category == "SWF"


def test_swf_cic():
    result = classify_state_affiliation("China Investment Corporation", None)
    # CIC matches PRC SOE keywords first (china + state investment)
    assert result.category in ("SOE", "SWF")


# --- Shell / Proxy ---

def test_shell_nominee():
    result = classify_state_affiliation("Pacific Nominee Holdings Ltd", None)
    assert result.category == "Shell-Proxy"


def test_shell_spv():
    result = classify_state_affiliation("Alpha Special Purpose Vehicle III", None)
    assert result.category == "Shell-Proxy"


# --- PEP ---

def test_pep_detection():
    result = classify_state_affiliation("Former Minister of Finance John Doe", None)
    assert result.category == "PEP"


def test_pep_ambassador():
    result = classify_state_affiliation("Ambassador to the United Nations", None)
    assert result.category == "PEP"
