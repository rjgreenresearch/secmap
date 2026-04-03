"""
jurisdiction_inference.py

Infers the jurisdiction (country) associated with an entity based on:
- Name patterns
- Filing context
- Known geographic tokens
- Issuer country overrides

Designed for beneficial ownership chain tracing: jurisdictions are
organized by risk tier to flag when ownership chains transit through
adversarial nations, opacity havens, or known conduit jurisdictions.

Enhancements:
- Full logging
- Deterministic heuristics
- Exception-safe inference
- Conservative defaults
- Risk-tier classification for chain analysis
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional, List

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Risk tier definitions
# ---------------------------------------------------------------------------
# ADVERSARIAL  -- Nations with known state-directed economic warfare,
#                espionage, or sanctions programs targeting the US.
# CONDUIT      -- Jurisdictions frequently used as intermediate layering
#                nodes in adversarial ownership chains.
# OPACITY      -- Secrecy jurisdictions with weak beneficial-ownership
#                disclosure; common shell-company domiciles.
# MONITORED    -- Jurisdictions with partial transparency or FATF
#                grey-list history.
# STANDARD     -- Allied or transparent jurisdictions.
# ---------------------------------------------------------------------------

RISK_ADVERSARIAL = "ADVERSARIAL"
RISK_CONDUIT = "CONDUIT"
RISK_OPACITY = "OPACITY"
RISK_MONITORED = "MONITORED"
RISK_STANDARD = "STANDARD"


@dataclass(frozen=True)
class JurisdictionResult:
    country: str
    risk_tier: str
    matched_token: Optional[str] = None


# ---------------------------------------------------------------------------
# Known geographic tokens, organized by risk tier
# ---------------------------------------------------------------------------

_JURISDICTIONS = {
    # =======================================================================
    # ADVERSARIAL -- primary targets for UBO chain terminus detection
    # =======================================================================
    RISK_ADVERSARIAL: {
        "China": [
            "China", "PRC", "People's Republic of China", "Chinese",
            "Beijing", "Shanghai", "Shenzhen", "Guangzhou", "Hangzhou",
            "Chengdu", "Nanjing", "Wuhan", "Tianjin", "Chongqing",
            "Dalian", "Qingdao", "Xiamen", "Suzhou", "Hefei",
            "Zhengzhou", "Changsha", "Kunming", "Fuzhou", "Dongguan",
            "Foshan", "Harbin", "Shenyang", "Jinan", "Urumqi",
            "Lhasa", "Hainan", "Zhuhai", "Ningbo",
        ],
        "Russia": [
            "Russia", "Russian Federation", "Russian",
            "Moscow", "St. Petersburg", "Saint Petersburg",
            "Novosibirsk", "Yekaterinburg", "Kazan", "Vladivostok",
            "Rostov", "Sochi", "Kaliningrad", "Crimea", "Sevastopol",
        ],
        "Iran": [
            "Iran", "Islamic Republic of Iran", "Iranian",
            "Tehran", "Isfahan", "Shiraz", "Tabriz", "Mashhad",
            "Kish Island", "Qeshm",
        ],
        "North Korea": [
            "North Korea", "DPRK",
            "Democratic People's Republic of Korea",
            "Pyongyang",
        ],
        "Belarus": [
            "Belarus", "Belarusian", "Minsk",
        ],
        "Myanmar": [
            "Myanmar", "Burma", "Yangon", "Naypyidaw",
        ],
        "Syria": [
            "Syria", "Syrian", "Damascus", "Aleppo",
        ],
        "Cuba": [
            "Cuba", "Cuban", "Havana",
        ],
        "Venezuela": [
            "Venezuela", "Venezuelan", "Caracas",
        ],
        "Nicaragua": [
            "Nicaragua", "Managua",
        ],
    },

    # =======================================================================
    # CONDUIT -- frequently used as intermediate layering nodes
    # in adversarial ownership chains (PRC/Russia → conduit → US)
    # =======================================================================
    RISK_CONDUIT: {
        "Hong Kong": ["Hong Kong", "H.K.", "HK", "HKSAR"],
        "Macau": ["Macau", "Macao", "MSAR"],
        "Singapore": ["Singapore", "SG"],
        "United Arab Emirates": [
            "United Arab Emirates", "UAE", "U.A.E.",
            "Dubai", "Abu Dhabi", "DIFC", "ADGM",
            "Sharjah", "Ras Al Khaimah", "RAK", "Ajman", "Fujairah",
        ],
        "Turkey": ["Turkey", "Turkiye", "Istanbul", "Ankara", "Izmir"],
        "Malaysia": ["Malaysia", "Kuala Lumpur", "Labuan"],
        "Thailand": ["Thailand", "Bangkok"],
        "Kazakhstan": ["Kazakhstan", "Almaty", "Astana", "Nur-Sultan"],
        "Uzbekistan": ["Uzbekistan", "Tashkent"],
        "Kyrgyzstan": ["Kyrgyzstan", "Bishkek"],
        "Tajikistan": ["Tajikistan", "Dushanbe"],
        "Turkmenistan": ["Turkmenistan", "Ashgabat"],
        "Armenia": ["Armenia", "Yerevan"],
        "Georgia": ["Georgia, Tbilisi", "Tbilisi"],
        "Azerbaijan": ["Azerbaijan", "Baku"],
        "Serbia": ["Serbia", "Belgrade"],
        "Hungary": ["Hungary", "Budapest"],
        "Cyprus": ["Cyprus", "Nicosia", "Limassol", "Larnaca", "Paphos"],
        "Malta": ["Malta", "Valletta", "Sliema"],
        "Montenegro": ["Montenegro", "Podgorica"],
        "North Macedonia": ["North Macedonia", "Skopje"],
        "Moldova": ["Moldova", "Chisinau"],
        "Latvia": ["Latvia", "Riga"],
        "Estonia": ["Estonia", "Tallinn"],
        "Lithuania": ["Lithuania", "Vilnius"],
    },

    # =======================================================================
    # OPACITY -- secrecy jurisdictions / shell-company domiciles
    # =======================================================================
    RISK_OPACITY: {
        # Caribbean
        "Cayman Islands": ["Cayman Islands", "Cayman", "Grand Cayman", "George Town, Cayman"],
        "British Virgin Islands": ["British Virgin Islands", "BVI", "Tortola", "Road Town"],
        "Bermuda": ["Bermuda", "Hamilton, Bermuda"],
        "Bahamas": ["Bahamas", "Nassau, Bahamas", "Freeport, Bahamas"],
        "Barbados": ["Barbados", "Bridgetown"],
        "Belize": ["Belize", "Belize City"],
        "Curacao": ["Curacao", "Curaçao", "Willemstad"],
        "Antigua and Barbuda": ["Antigua and Barbuda", "Antigua", "St. John's, Antigua"],
        "St. Kitts and Nevis": ["St. Kitts and Nevis", "Saint Kitts", "Nevis"],
        "St. Vincent and the Grenadines": ["St. Vincent and the Grenadines", "Saint Vincent", "Kingstown"],
        "Turks and Caicos": ["Turks and Caicos", "Providenciales"],
        "Dominica": ["Commonwealth of Dominica", "Dominica"],
        "Grenada": ["Grenada", "St. George's, Grenada"],
        "St. Lucia": ["St. Lucia", "Saint Lucia", "Castries"],
        "Anguilla": ["Anguilla", "The Valley, Anguilla"],
        "Aruba": ["Aruba", "Oranjestad"],
        "US Virgin Islands": ["US Virgin Islands", "USVI", "St. Thomas", "St. Croix"],
        # Pacific
        "Samoa": ["Samoa", "Apia"],
        "Vanuatu": ["Vanuatu", "Port Vila"],
        "Cook Islands": ["Cook Islands", "Rarotonga"],
        "Marshall Islands": ["Marshall Islands", "Majuro"],
        "Nauru": ["Nauru"],
        "Niue": ["Niue"],
        "Tonga": ["Tonga", "Nuku'alofa"],
        "Palau": ["Palau"],
        # Indian Ocean
        "Seychelles": ["Seychelles", "Mahe", "Victoria, Seychelles"],
        "Mauritius": ["Mauritius", "Port Louis"],
        "Maldives": ["Maldives", "Male"],
        "Comoros": ["Comoros", "Moroni"],
        # Europe
        "Liechtenstein": ["Liechtenstein", "Vaduz"],
        "Monaco": ["Monaco", "Monte Carlo"],
        "Andorra": ["Andorra", "Andorra la Vella"],
        "San Marino": ["San Marino"],
        "Gibraltar": ["Gibraltar"],
        "Jersey": ["Jersey", "St. Helier"],
        "Guernsey": ["Guernsey", "St. Peter Port"],
        "Isle of Man": ["Isle of Man", "Douglas, Isle of Man"],
        # Americas
        "Panama": ["Panama", "Panama City"],
        "Uruguay": ["Uruguay", "Montevideo"],
        "Costa Rica": ["Costa Rica", "San Jose, Costa Rica"],
        # Middle East
        "Bahrain": ["Bahrain", "Manama"],
        # Asia
        "Brunei": ["Brunei", "Bandar Seri Begawan"],
    },

    # =======================================================================
    # MONITORED -- partial transparency, FATF grey-list history,
    # or known to facilitate layered structures
    # =======================================================================
    RISK_MONITORED: {
        "Taiwan": ["Taiwan", "ROC", "Taipei", "Kaohsiung", "Taichung"],
        "Pakistan": ["Pakistan", "Islamabad", "Karachi", "Lahore"],
        "Saudi Arabia": ["Saudi Arabia", "Riyadh", "Jeddah", "NEOM"],
        "Qatar": ["Qatar", "Doha"],
        "Oman": ["Oman", "Muscat"],
        "Kuwait": ["Kuwait", "Kuwait City"],
        "Jordan": ["Jordan", "Amman"],
        "Lebanon": ["Lebanon", "Beirut"],
        "Iraq": ["Iraq", "Baghdad", "Erbil"],
        "Libya": ["Libya", "Tripoli"],
        "South Africa": ["South Africa", "Johannesburg", "Cape Town"],
        "Nigeria": ["Nigeria", "Lagos", "Abuja"],
        "Kenya": ["Kenya", "Nairobi"],
        "Tanzania": ["Tanzania", "Dar es Salaam"],
        "Ethiopia": ["Ethiopia", "Addis Ababa"],
        "Egypt": ["Egypt", "Cairo"],
        "Morocco": ["Morocco", "Casablanca", "Rabat"],
        "Tunisia": ["Tunisia", "Tunis"],
        "Algeria": ["Algeria", "Algiers"],
        "Ukraine": ["Ukraine", "Kyiv", "Kiev", "Odessa", "Kharkiv"],
        "Cambodia": ["Cambodia", "Phnom Penh"],
        "Laos": ["Laos", "Vientiane"],
        "Sri Lanka": ["Sri Lanka", "Colombo"],
        "Bangladesh": ["Bangladesh", "Dhaka"],
        "Nepal": ["Nepal", "Kathmandu"],
        "Mongolia": ["Mongolia", "Ulaanbaatar"],
    },

    # =======================================================================
    # STANDARD -- allied / transparent jurisdictions
    # =======================================================================
    RISK_STANDARD: {
        "United States": [
            "United States", "USA", "U.S.", "U.S.A.",
            "Delaware", "New York", "California", "Nevada",
            "Wyoming", "South Dakota", "Texas", "Florida",
            "Illinois", "Massachusetts", "New Jersey",
            "Washington", "Colorado", "Oregon", "Connecticut",
        ],
        "Canada": ["Canada", "Toronto", "Vancouver", "Ontario", "Montreal", "Calgary", "Ottawa"],
        "United Kingdom": ["United Kingdom", "UK", "U.K.", "England", "London", "Scotland", "Wales", "Edinburgh"],
        "Germany": ["Germany", "Frankfurt", "Munich", "Berlin", "Hamburg", "Dusseldorf", "GmbH", "(DE)"],
        "France": ["France", "Paris", "Lyon", "Marseille"],
        "Switzerland": ["Switzerland", "Zurich", "Geneva", "Swiss", "Basel", "Bern", "Zug", "(CH)"],
        "Netherlands": ["Netherlands", "Amsterdam", "Dutch", "Rotterdam", "The Hague", "(NL)", "B.V.", "B.V", "Eindhoven"],
        "Ireland": ["Ireland", "Dublin", "(IE)"],
        "Luxembourg": ["Luxembourg", "(LUX)", "S.r.l", "S. r.l", "Sarl"],
        "Sweden": ["Sweden", "Stockholm"],
        "Norway": ["Norway", "Oslo"],
        "Denmark": ["Denmark", "Copenhagen"],
        "Finland": ["Finland", "Helsinki"],
        "Italy": ["Italy", "Milan", "Rome"],
        "Spain": ["Spain", "Madrid", "Barcelona"],
        "Belgium": ["Belgium", "Brussels"],
        "Austria": ["Austria", "Vienna"],
        "Portugal": ["Portugal", "Lisbon"],
        "Greece": ["Greece", "Athens"],
        "Poland": ["Poland", "Warsaw"],
        "Czech Republic": ["Czech Republic", "Czechia", "Prague"],
        "Romania": ["Romania", "Bucharest"],
        "Bulgaria": ["Bulgaria", "Sofia"],
        "Croatia": ["Croatia", "Zagreb"],
        "Slovakia": ["Slovakia", "Bratislava"],
        "Slovenia": ["Slovenia", "Ljubljana"],
        "Israel": ["Israel", "Tel Aviv", "Jerusalem"],
        "Japan": ["Japan", "Tokyo", "Osaka", "Yokohama", "Nagoya"],
        "South Korea": ["South Korea", "Korea", "Republic of Korea", "Seoul", "Busan"],
        "India": ["India", "Mumbai", "New Delhi", "Bangalore", "Hyderabad", "Chennai", "Pune"],
        "Australia": ["Australia", "Sydney", "Melbourne", "Brisbane", "Perth"],
        "New Zealand": ["New Zealand", "Auckland", "Wellington"],
        "Indonesia": ["Indonesia", "Jakarta"],
        "Philippines": ["Philippines", "Manila"],
        "Vietnam": ["Vietnam", "Hanoi", "Ho Chi Minh"],
        "Mexico": ["Mexico", "Mexico City", "Monterrey"],
        "Brazil": ["Brazil", "Sao Paulo", "Rio de Janeiro"],
        "Argentina": ["Argentina", "Buenos Aires"],
        "Chile": ["Chile", "Santiago"],
        "Colombia": ["Colombia", "Bogota"],
        "Peru": ["Peru", "Lima"],
    },
}

# ---------------------------------------------------------------------------
# Flatten into lookup structures
# ---------------------------------------------------------------------------

# country -> (risk_tier, compiled_pattern)
_COUNTRY_LOOKUP: dict[str, tuple[str, re.Pattern]] = {}

# Build in risk-tier priority order so adversarial matches win ties
for _tier in [RISK_ADVERSARIAL, RISK_CONDUIT, RISK_OPACITY, RISK_MONITORED, RISK_STANDARD]:
    for _country, _tokens in _JURISDICTIONS[_tier].items():
        _COUNTRY_LOOKUP[_country] = (
            _tier,
            re.compile("|".join([re.escape(t) for t in _tokens]), re.IGNORECASE),
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def infer_jurisdiction(
    name: str,
    issuer_country: Optional[str] = None,
    context_text: Optional[str] = None,
) -> Optional[str]:
    """
    Infer the jurisdiction associated with an entity.

    Priority:
      1. Explicit issuer_country override
      2. Name-based inference
      3. Context-based inference
      4. Unknown (None)

    Returns:
        Country name or None
    """
    if issuer_country:
        logger.debug("Using issuer_country override: %s", issuer_country)
        return issuer_country

    if not name:
        logger.warning("infer_jurisdiction() received empty name")
        return None

    try:
        for country, (tier, pattern) in _COUNTRY_LOOKUP.items():
            if pattern.search(name):
                logger.debug("Inferred jurisdiction from name '%s': %s (%s)", name, country, tier)
                return country

        if context_text:
            for country, (tier, pattern) in _COUNTRY_LOOKUP.items():
                if pattern.search(context_text):
                    logger.debug("Inferred jurisdiction from context: %s (%s)", country, tier)
                    return country

        logger.debug("No jurisdiction inferred for '%s'", name)
        return None

    except Exception as e:
        logger.error("infer_jurisdiction() failed for %s: %s", name, e)
        return None


def infer_jurisdiction_with_risk(
    name: str,
    issuer_country: Optional[str] = None,
    context_text: Optional[str] = None,
) -> Optional[JurisdictionResult]:
    """
    Like infer_jurisdiction(), but returns a JurisdictionResult with
    the risk tier attached. Used for ownership-chain risk scoring.
    """
    if issuer_country:
        tier = get_risk_tier(issuer_country)
        return JurisdictionResult(country=issuer_country, risk_tier=tier)

    if not name:
        return None

    try:
        for country, (tier, pattern) in _COUNTRY_LOOKUP.items():
            m = pattern.search(name)
            if m:
                return JurisdictionResult(country=country, risk_tier=tier, matched_token=m.group())

        if context_text:
            for country, (tier, pattern) in _COUNTRY_LOOKUP.items():
                m = pattern.search(context_text)
                if m:
                    return JurisdictionResult(country=country, risk_tier=tier, matched_token=m.group())

        return None

    except Exception as e:
        logger.error("infer_jurisdiction_with_risk() failed for %s: %s", name, e)
        return None


def get_risk_tier(country: str) -> str:
    """Return the risk tier for a known country, or MONITORED as default."""
    if country in _COUNTRY_LOOKUP:
        return _COUNTRY_LOOKUP[country][0]
    return RISK_MONITORED


def get_all_adversarial_countries() -> List[str]:
    """Return the list of adversarial-nation names."""
    return list(_JURISDICTIONS[RISK_ADVERSARIAL].keys())


def get_all_opacity_jurisdictions() -> List[str]:
    """Return the list of opacity/secrecy jurisdictions."""
    return list(_JURISDICTIONS[RISK_OPACITY].keys())


def get_all_conduit_jurisdictions() -> List[str]:
    """Return the list of known conduit jurisdictions."""
    return list(_JURISDICTIONS[RISK_CONDUIT].keys())
