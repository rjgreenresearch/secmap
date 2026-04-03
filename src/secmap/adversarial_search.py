"""
adversarial_search.py

Expands a country-name search keyword into a comprehensive set of search
terms for the SEC filing universe. When a researcher runs:

    python run_research.py --search "russia"

the script currently finds 0 results because no SEC registrant has "russia"
in its company name. This module expands "russia" into 30+ search terms
including demonyms, legal entity suffixes, known SOEs, strategic companies,
and city names — catching GAZPROM NEFT PJSC, LUKOIL PJSC, MECHEL PAO, etc.

Design follows jurisdiction_inference.py: structured dictionaries, risk-tier
aware, deterministic, no external dependencies.

Usage:
    from adversarial_search import expand_search, is_country_keyword

    if is_country_keyword("russia"):
        terms = expand_search("russia")
        # Returns: ["russia", "russian", "PJSC", "PAO", "OAO", "gazprom", ...]

    # Or get the full expansion config:
    from adversarial_search import COUNTRY_SEARCH_EXPANSIONS

Author: Robert J. Green | robert@rjgreenresearch.org
ORCID: 0009-0002-9097-1021
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ===================================================================
# COUNTRY SEARCH EXPANSION TABLES
# ===================================================================
# Each adversarial/monitored nation has multiple search strategies:
#
#   country_names   — The country name + demonyms + abbreviations
#   legal_suffixes  — Entity type suffixes unique to that nation's
#                     corporate law (e.g., PJSC for Russia, AG for Swiss)
#   soe_names       — Known state-owned enterprises likely to file with SEC
#   strategic_names — Strategic/major companies (private or public)
#   city_names      — Major cities that appear in company names
#                     (e.g., "Beijing" in "Beijing Kunlun Tech Co")
#
# Legal suffixes that are shared across many nations (LLC, Ltd, Inc)
# are NOT included — they would match thousands of unrelated companies.
# Only suffixes with strong nation-specificity are listed.
# ===================================================================

COUNTRY_SEARCH_EXPANSIONS: Dict[str, dict] = {

    # ---------------------------------------------------------------
    # CHINA (PRC)
    # ---------------------------------------------------------------
    "china": {
        "country_names": [
            "china", "chinese", "prc",
        ],
        "legal_suffixes": [
            # Chinese legal entity types are rarely in SEC names
            # — most file under English names. Focus on name patterns.
        ],
        "soe_names": [
            "sinopec", "petrochina", "cnooc", "china national",
            "china state", "china petroleum", "china mobile",
            "china telecom", "china unicom", "china railway",
            "china construction", "china communications",
            "china merchants", "china resources", "china life",
            "china southern", "china eastern", "air china",
            "bank of china", "icbc", "china minsheng",
            "china citic", "china everbright",
            "chalco", "aluminum corp of china",
            "china shenhua", "china coal",
            "cosco", "china shipping",
            "sinochem", "chemchina",
            "china tower", "china molybdenum",
        ],
        "strategic_names": [
            "alibaba", "tencent", "baidu", "jd.com", "pinduoduo",
            "xpeng", "li auto", "zeekr",
            "xiaomi", "lenovo",
            "bilibili", "iqiyi", "netease",
            "yum china", "luckin", "hutchmed",
            "wuxi", "beigene", "zai lab",
            "futu", "up fintech", "kanzhun",
            "full truck", "tuya",
            "vnet", "chinadata", "gds holdings",
            "miniso", "lufax", "zhihu",
            "trip.com", "huazhu", "h world",
        ],
        "city_names": [
            "beijing", "shanghai", "shenzhen", "guangzhou",
            "hangzhou", "hong kong",
        ],
    },

    # ---------------------------------------------------------------
    # RUSSIA
    # ---------------------------------------------------------------
    "russia": {
        "country_names": [
            "russia", "russian",
        ],
        "legal_suffixes": [
            # Russian corporate suffixes — high specificity
            "pjsc",    # Public Joint-Stock Company (most common for SEC filers)
            "pao",     # Same in Russian abbreviation
            "oao",     # Open Joint-Stock Company (older form)
            "zao",     # Closed Joint-Stock Company
            "ooo",     # Limited Liability Company (Russian)
        ],
        "soe_names": [
            "gazprom", "rosneft", "lukoil",
            "sberbank", "vtb",
            "norilsk", "nornickel",
            "rostec", "rosatom",
            "transneft", "russhydro",
            "alrosa", "phosagro",
            "aeroflot", "russian railways",
            "inter rao", "sistema",
            "surgutneftegas",
            "tatneft", "bashneft",
            "novatek",
        ],
        "strategic_names": [
            "yandex", "veon", "vimpelcom",
            "mts", "mobile telesystems",
            "mechel", "severstal", "evraz",
            "polyus", "polymetal", "petropavlovsk",
            "lenta", "magnit", "x5",
            "mail.ru", "ozon", "headhunter",
            "cian", "qiwi", "tinkoff",
            "fix price", "globaltrans",
        ],
        "city_names": [
            "moscow", "st. petersburg", "saint petersburg",
        ],
    },

    # ---------------------------------------------------------------
    # IRAN
    # ---------------------------------------------------------------
    "iran": {
        "country_names": [
            "iran", "iranian", "persia", "persian",
        ],
        "legal_suffixes": [],
        "soe_names": [
            # Most are sanctions-delisted, but historical filings may exist
            "national iranian", "nioc",
            "iran khodro", "saipa",
            "bank melli", "bank mellat", "bank saderat",
            "bank tejarat", "bank sepah",
            "iran air",
        ],
        "strategic_names": [
            "tehran", "isfahan",
        ],
        "city_names": [
            "tehran",
        ],
    },

    # ---------------------------------------------------------------
    # NORTH KOREA (DPRK)
    # ---------------------------------------------------------------
    "north korea": {
        "country_names": [
            "north korea", "dprk", "democratic people's republic of korea",
            "d.p.r.k.",
        ],
        "legal_suffixes": [],
        "soe_names": [
            "korea mining", "komid",
            "korea national", "korea foreign",
            "mansudae",
        ],
        "strategic_names": [],
        "city_names": [
            "pyongyang",
        ],
    },

    # ---------------------------------------------------------------
    # CUBA
    # ---------------------------------------------------------------
    "cuba": {
        "country_names": [
            "cuba", "cuban",
        ],
        "legal_suffixes": [],
        "soe_names": [
            "cubana", "habanos",
        ],
        "strategic_names": [],
        "city_names": [
            "havana", "habana",
        ],
    },

    # ---------------------------------------------------------------
    # VENEZUELA
    # ---------------------------------------------------------------
    "venezuela": {
        "country_names": [
            "venezuela", "venezuelan",
        ],
        "legal_suffixes": [],
        "soe_names": [
            "pdvsa", "citgo",
            "petroleos de venezuela",
            "banco de venezuela",
        ],
        "strategic_names": [
            "carbozulia",
        ],
        "city_names": [
            "caracas",
        ],
    },

    # ---------------------------------------------------------------
    # BELARUS
    # ---------------------------------------------------------------
    "belarus": {
        "country_names": [
            "belarus", "belarusian", "byelorussia", "byelorussian",
        ],
        "legal_suffixes": [],
        "soe_names": [
            "belaruskali", "belneftekhim",
            "belarusbank", "belgazprombank",
        ],
        "strategic_names": [
            "epam",  # EPAM Systems — founded in Belarus, now US-listed
        ],
        "city_names": [
            "minsk",
        ],
    },

    # ---------------------------------------------------------------
    # MYANMAR
    # ---------------------------------------------------------------
    "myanmar": {
        "country_names": [
            "myanmar", "burma", "burmese",
        ],
        "legal_suffixes": [],
        "soe_names": [
            "myanma", "myanmar oil", "myanmar economic",
        ],
        "strategic_names": [],
        "city_names": [
            "yangon", "rangoon", "naypyidaw",
        ],
    },

    # ---------------------------------------------------------------
    # SYRIA
    # ---------------------------------------------------------------
    "syria": {
        "country_names": [
            "syria", "syrian",
        ],
        "legal_suffixes": [],
        "soe_names": [],
        "strategic_names": [],
        "city_names": [
            "damascus", "aleppo",
        ],
    },

    # ---------------------------------------------------------------
    # NICARAGUA
    # ---------------------------------------------------------------
    "nicaragua": {
        "country_names": [
            "nicaragua", "nicaraguan",
        ],
        "legal_suffixes": [],
        "soe_names": [],
        "strategic_names": [],
        "city_names": [
            "managua",
        ],
    },

    # ---------------------------------------------------------------
    # IRAQ (not PASS Act but included for completeness)
    # ---------------------------------------------------------------
    "iraq": {
        "country_names": [
            "iraq", "iraqi",
        ],
        "legal_suffixes": [],
        "soe_names": [
            "iraq petroleum", "south oil",
            "state oil marketing",
        ],
        "strategic_names": [],
        "city_names": [
            "baghdad", "basra", "erbil",
        ],
    },
}

# Alias handling: map common variants to canonical keys
_ALIASES = {
    "prc": "china",
    "chinese": "china",
    "russian": "russia",
    "russian federation": "russia",
    "iranian": "iran",
    "dprk": "north korea",
    "burmese": "myanmar",
    "burma": "myanmar",
    "cuban": "cuba",
    "venezuelan": "venezuela",
    "belarusian": "belarus",
    "byelorussia": "belarus",
    "syrian": "syria",
    "nicaraguan": "nicaragua",
    "iraqi": "iraq",
}


# ===================================================================
# PUBLIC API
# ===================================================================

def is_country_keyword(keyword: str) -> bool:
    """Check if a search keyword matches an adversarial nation."""
    k = keyword.strip().lower()
    return k in COUNTRY_SEARCH_EXPANSIONS or k in _ALIASES


def get_canonical_country(keyword: str) -> Optional[str]:
    """Resolve a keyword to its canonical country key."""
    k = keyword.strip().lower()
    if k in COUNTRY_SEARCH_EXPANSIONS:
        return k
    return _ALIASES.get(k)


def expand_search(keyword: str, min_length: int = 4) -> List[str]:
    """
    Expand a country keyword into all search terms for that nation.

    Returns a deduplicated list of search terms, ordered by specificity:
    country names first, then SOEs, then strategic names, then cities,
    then legal suffixes.

    Terms shorter than min_length are excluded to prevent false positives
    from substring matching (e.g., "nio" matching "domINIOn", "mts"
    matching "MACOM Technology Solutions", "oao" matching "Alpha One").

    If the keyword is not a recognised country, returns [keyword] unchanged.
    """
    canonical = get_canonical_country(keyword)
    if canonical is None:
        return [keyword]

    config = COUNTRY_SEARCH_EXPANSIONS[canonical]
    terms = []
    seen = set()
    skipped = []

    # Priority order: country names, SOEs, strategic, cities, legal suffixes
    for category in ["country_names", "soe_names", "strategic_names",
                     "city_names", "legal_suffixes"]:
        for term in config.get(category, []):
            lower = term.lower()
            if lower not in seen:
                seen.add(lower)
                if len(term) >= min_length:
                    terms.append(term)
                else:
                    skipped.append(term)

    if skipped:
        logger.info(
            "Skipped %d terms shorter than %d chars: %s",
            len(skipped), min_length, ", ".join(skipped),
        )

    logger.info(
        "Expanded '%s' → %s canonical country, %d search terms (%d skipped)",
        keyword, canonical, len(terms), len(skipped),
    )
    return terms


def expand_search_by_category(keyword: str) -> Dict[str, List[str]]:
    """
    Same as expand_search but returns terms organised by category.
    Useful for reporting which strategy found each hit.
    """
    canonical = get_canonical_country(keyword)
    if canonical is None:
        return {"raw_keyword": [keyword]}

    config = COUNTRY_SEARCH_EXPANSIONS[canonical]
    return {
        cat: list(config.get(cat, []))
        for cat in ["country_names", "soe_names", "strategic_names",
                     "city_names", "legal_suffixes"]
        if config.get(cat)
    }


def all_countries() -> List[str]:
    """Return all canonical country keys."""
    return sorted(COUNTRY_SEARCH_EXPANSIONS.keys())


def summary() -> str:
    """Print a summary of all country expansions for documentation."""
    lines = ["Adversarial Nation Search Expansion Summary", "=" * 50]
    for country in sorted(COUNTRY_SEARCH_EXPANSIONS.keys()):
        config = COUNTRY_SEARCH_EXPANSIONS[country]
        total = sum(len(config.get(cat, [])) for cat in
                    ["country_names", "soe_names", "strategic_names",
                     "city_names", "legal_suffixes"])
        lines.append(f"\n  {country.upper()}: {total} search terms")
        for cat in ["country_names", "legal_suffixes", "soe_names",
                     "strategic_names", "city_names"]:
            terms = config.get(cat, [])
            if terms:
                lines.append(f"    {cat}: {', '.join(terms[:8])}"
                             + (f" (+{len(terms)-8} more)" if len(terms) > 8 else ""))
    return "\n".join(lines)


# Quick self-test
if __name__ == "__main__":
    print(summary())
    print()
    for test in ["russia", "china", "iran", "cuba", "venezuela", "belarus",
                 "north korea", "myanmar", "prc", "russian", "dprk"]:
        terms = expand_search(test)
        print(f"  {test:20s} → {len(terms)} terms: {terms[:5]}...")
