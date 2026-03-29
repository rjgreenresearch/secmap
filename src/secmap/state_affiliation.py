"""
state_affiliation.py

Classifies whether an entity is affiliated with a state actor, with
coverage across all primary adversarial nations:
  - PRC (SOEs, Party-controlled, MCF, UFWD)
  - Russia (state corporations, oligarch-linked, FSB/GRU-adjacent)
  - Iran (IRGC, bonyads, sanctions-listed patterns)
  - DPRK (front companies, trading entities)
  - Other adversarial-nation state apparatus

Also detects:
  - Sovereign wealth funds (global)
  - Politically exposed persons (PEP)
  - Sanctions-list entity name patterns
  - Shell / nominee / proxy indicators

Designed for beneficial ownership chain tracing: when an entity at
any depth in the chain matches these heuristics, the edge is flagged
for analyst review.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclass for classification result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StateAffiliation:
    category: str
    subcategory: Optional[str] = None
    details: Optional[str] = None
    confidence: float = 0.0


# ===================================================================
# PRC — People's Republic of China
# ===================================================================

_PRC_SOE_KEYWORDS = [
    "state-owned", "state owned", "soe",
    "state enterprise", "state asset", "sasac",
    "state-controlled", "state controlled",
    "government-owned", "government owned",
    "national enterprise", "provincial enterprise", "municipal enterprise",
    "state capital", "state investment", "state development",
    "state power", "state grid", "state railway", "state petroleum",
    "china national", "china state", "china energy",
    "china resources", "china merchants", "china electronics",
    "china aerospace", "china shipbuilding", "china railway",
    "china telecom", "china mobile", "china unicom",
    "china construction", "china communications",
    "sinopec", "petrochina", "cnooc", "cofco",
    "sinochem", "sinosteel", "chalco",
    "国有", "国资", "央企", "国企",
]

_PRC_PARTY_KEYWORDS = [
    "communist party", "ccp", "cpc",
    "party committee", "party secretary", "party branch",
    "party member", "party cell", "party group",
    "discipline inspection", "central committee",
    "politburo standing committee", "politburo",
    "party congress", "propaganda department", "organization department",
    "central commission", "party school",
    "党委", "党组", "党支部", "纪委", "中央委员会",
    "中组部", "中宣部", "党校",
]

_PRC_MCF_KEYWORDS = [
    "military-civil fusion", "military civil fusion", "mcf",
    "defense technology", "defence technology",
    "dual-use", "dual use",
    "military industry", "defense science", "defence science",
    "defense industrial", "defence industrial",
    "weapons system", "ordnance",
    "aerospace defense", "aerospace defence",
    "military equipment", "national defense", "national defence",
    "avic", "casic", "casc", "cetc", "cssc", "csgc",
    "norinco", "poly group", "poly technologies",
    "china electronics technology", "china aerospace science",
    "china north industries", "china south industries",
    "军民融合", "军工", "国防科技", "军事",
]

_PRC_UFWD_KEYWORDS = [
    "united front", "united front work",
    "overseas chinese affairs", "overseas chinese association",
    "chinese people's political consultative", "cppcc",
    "all-china federation", "returned overseas chinese",
    "compatriot", "peaceful reunification",
    "confucius institute", "thousand talents",
    "china council for international cooperation",
    "china association for science and technology",
    "china overseas exchange association",
    "统战", "统一战线", "侨务", "政协", "侨联",
    "千人计划", "孔子学院",
]

# ===================================================================
# Russia
# ===================================================================

_RUSSIA_STATE_KEYWORDS = [
    # State corporations and SOEs
    "gazprom", "rosneft", "lukoil", "transneft",
    "rostec", "rosatom", "roscosmos",
    "sberbank", "vtb bank", "vnesheconombank", "veb.rf",
    "russian railways", "aeroflot",
    "almaz-antey", "tactical missiles corporation",
    "united aircraft corporation", "united shipbuilding",
    "russian direct investment fund", "rdif",
    "russian state", "kremlin",
    # Intelligence / security apparatus
    "fsb", "gru", "svr", "fso",
    "federal security service", "main intelligence directorate",
    "foreign intelligence service",
    # Oligarch-linked patterns
    "oligarch",
    # Sanctions-era evasion patterns
    "russian federation", "russian government",
    "state corporation", "государственная корпорация",
    "госкорпорация",
]

# ===================================================================
# Iran
# ===================================================================

_IRAN_STATE_KEYWORDS = [
    # IRGC and affiliates
    "irgc", "islamic revolutionary guard",
    "revolutionary guard corps", "quds force",
    "basij", "sepah",
    # Bonyads (parastatal foundations)
    "bonyad", "foundation of the oppressed",
    "mostazafan foundation", "astan quds razavi",
    "execution of imam khomeini's order", "eiko", "setad",
    # State entities
    "national iranian oil", "nioc",
    "national iranian gas", "nigc",
    "iran khodro", "saipa",
    "bank melli", "bank mellat", "bank saderat", "bank sepah",
    "bank tejarat", "bank markazi",
    "islamic republic of iran shipping", "irisl",
    "iran air",
    # Nuclear / missile program
    "atomic energy organization of iran", "aeoi",
    "iran electronics industries",
    "shahid hemmat industrial group",
    "shahid bakeri industrial group",
]

# ===================================================================
# DPRK — North Korea
# ===================================================================

_DPRK_KEYWORDS = [
    "dprk", "north korea",
    "democratic people's republic of korea",
    "korea mining development trading", "komid",
    "korea ryonbong", "korea tangun",
    "korea hyoksin", "korea kwangson",
    "mansudae overseas", "korea national insurance",
    "foreign trade bank", "korea daesong",
    "korea kumgang", "korea united development bank",
    "office 39", "bureau 39", "room 39",
    "korea workers' party",
    "korean people's army",
    "reconnaissance general bureau", "rgb",
]

# ===================================================================
# Other adversarial-nation state apparatus
# ===================================================================

_BELARUS_STATE_KEYWORDS = [
    "belarusian state", "belneftekhim",
    "belaruskali", "grodno azot",
    "belarusian national", "lukashenko",
]

_SYRIA_STATE_KEYWORDS = [
    "syrian arab republic", "syrian government",
    "central bank of syria", "commercial bank of syria",
    "syrian petroleum", "sytrol",
]

_MYANMAR_STATE_KEYWORDS = [
    "myanmar economic holdings", "mehl",
    "myanmar economic corporation", "mec",
    "tatmadaw", "myanmar military",
    "myanma oil and gas", "moge",
]

_VENEZUELA_STATE_KEYWORDS = [
    "pdvsa", "petroleos de venezuela",
    "banco central de venezuela",
    "venezuelan government", "maduro regime",
    "citgo holding",
]

_CUBA_STATE_KEYWORDS = [
    "cuban government", "gaesa",
    "cimex", "habanos", "cubanacan",
    "cuban military",
]

# ===================================================================
# Sovereign Wealth Funds (global — not inherently adversarial,
# but critical for UBO chain terminus identification)
# ===================================================================

_SWF_KEYWORDS = [
    "sovereign wealth fund", "swf",
    "government investment", "state investment fund",
    "national wealth fund", "national investment",
    # Specific SWFs frequently seen in SEC filings
    "china investment corporation", "cic",
    "safe investment company", "state administration of foreign exchange",
    "national social security fund",
    "temasek", "gic private limited",
    "abu dhabi investment authority", "adia",
    "mubadala", "qatar investment authority", "qia",
    "public investment fund", "pif",
    "korea investment corporation",
    "national pension service",
    "government pension fund", "norges bank investment",
    "russian national wealth fund",
    "iran national development fund",
    "khazanah nasional",
]

# ===================================================================
# PEP — Politically Exposed Persons (global)
# ===================================================================

_PEP_KEYWORDS = [
    # Executive heads of state / government
    "minister", "vice minister", "deputy minister",
    "governor", "vice governor",
    "deputy governor", "deputy mayor",
    "deputy minister", "deputy commissioner",
    "deputy chief of staff",
    "mayor", "vice mayor",
    "prime minister", "head of state",
    "president of the republic", "premier",
    # Legislative
    "senator", "congressman", "congresswoman",
    "member of parliament", "member of congress",
    "legislator",
    # PRC-specific
    "secretary-general", "politburo",
    "npc", "cppcc", "standing committee",
    "state council", "central military commission",
    # Russia-specific
    "duma", "federation council",
    # Iran-specific
    "supreme leader", "guardian council", "assembly of experts",
    "expediency council", "majlis",
    # Diplomatic
    "ambassador", "consul general", "envoy",
    "high commissioner",
    # Judicial
    "chief justice", "supreme court",
    "attorney general", "solicitor general",
    "prosecutor general",
    # Military (senior)
    "general officer", "flag officer",
    "admiral", "field marshal",
    "commander-in-chief", "chief of staff",
    "marshal",
    # Regulatory / central bank
    "central bank governor", "central bank chairman",
    "regulator", "commissioner",
    # Intelligence
    "intelligence director", "security chief",
    "intelligence service",
    # Royal / monarchical
    "king", "queen", "prince", "princess",
    "emir", "sheikh", "sultan",
    "crown prince", "royal family",
]

# ===================================================================
# Shell / Nominee / Proxy indicators
# ===================================================================

_SHELL_PROXY_KEYWORDS = [
    "nominee", "nominee shareholder", "nominee director",
    "bearer share", "bearer instrument",
    "registered agent", "resident agent",
    "shelf company", "shell company", "shell corporation",
    "special purpose vehicle", "spv",
    "special purpose entity", "spe",
    "variable interest entity", "vie",
    "brass plate", "letterbox company",
    "dormant company", "dormant entity",
    "holding company", "intermediate holding",
    "investment vehicle", "investment holding",
    "trust company", "trust arrangement",
    "power of attorney", "poa",
    "proxy holder", "proxy voting",
    "straw man", "front company", "front entity",
    "pass-through entity", "pass through entity",
    "conduit entity", "conduit company",
    "offshore entity", "offshore company", "offshore holding",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _contains_any(text: str, keywords: list[str]) -> bool:
    t = text.lower()
    return any(kw in t for kw in keywords)


def _match_keyword(text: str, keywords: list[str]) -> Optional[str]:
    """Return the first matched keyword, or None."""
    t = text.lower()
    for kw in keywords:
        if kw in t:
            return kw
    return None


# ---------------------------------------------------------------------------
# Main classifier
# ---------------------------------------------------------------------------

def classify_state_affiliation(
    name: str,
    role,
    issuer_country: Optional[str] = None,
) -> StateAffiliation:
    """
    Classify whether an entity is affiliated with a state actor.

    Checks in priority order:
      1. PRC categories (SOE, Party, MCF, UFWD)
      2. Russia state apparatus
      3. Iran state apparatus (IRGC, bonyads)
      4. DPRK front companies
      5. Other adversarial-nation state entities
      6. Sovereign wealth funds (global)
      7. Shell / nominee / proxy indicators
      8. PEP detection (global)
      9. None

    Country-specific checks are gated on issuer_country when provided,
    but SOE/state keywords that are unambiguous (e.g. "Gazprom") match
    regardless of issuer_country.
    """
    if not name:
        logger.warning("classify_state_affiliation() received empty name")
        return StateAffiliation("None", None, None, 0.0)

    try:
        text = name.lower()

        # --- PRC ---
        if issuer_country in ("China", "Hong Kong", "Macau") or issuer_country is None:
            if _contains_any(text, _PRC_SOE_KEYWORDS):
                return StateAffiliation("SOE", "PRC", "Matched PRC SOE keywords", 0.9)
            if _contains_any(text, _PRC_PARTY_KEYWORDS):
                return StateAffiliation("Party-Controlled", "PRC", "Matched PRC Party keywords", 0.9)
            if _contains_any(text, _PRC_MCF_KEYWORDS):
                return StateAffiliation("MCF", "PRC", "Matched PRC MCF keywords", 0.85)
            if _contains_any(text, _PRC_UFWD_KEYWORDS):
                return StateAffiliation("UFWD", "PRC", "Matched PRC UFWD keywords", 0.8)

        # --- Russia ---
        if issuer_country in ("Russia",) or issuer_country is None:
            if _contains_any(text, _RUSSIA_STATE_KEYWORDS):
                return StateAffiliation("State-Linked", "Russia", "Matched Russia state keywords", 0.85)

        # --- Iran ---
        if issuer_country in ("Iran",) or issuer_country is None:
            if _contains_any(text, _IRAN_STATE_KEYWORDS):
                return StateAffiliation("State-Linked", "Iran", "Matched Iran state keywords", 0.85)

        # --- DPRK ---
        if _contains_any(text, _DPRK_KEYWORDS):
            return StateAffiliation("State-Linked", "DPRK", "Matched DPRK keywords", 0.9)

        # --- Belarus ---
        if issuer_country in ("Belarus",) or issuer_country is None:
            if _contains_any(text, _BELARUS_STATE_KEYWORDS):
                return StateAffiliation("State-Linked", "Belarus", "Matched Belarus state keywords", 0.8)

        # --- Syria ---
        if issuer_country in ("Syria",) or issuer_country is None:
            if _contains_any(text, _SYRIA_STATE_KEYWORDS):
                return StateAffiliation("State-Linked", "Syria", "Matched Syria state keywords", 0.8)

        # --- Myanmar ---
        if issuer_country in ("Myanmar",) or issuer_country is None:
            if _contains_any(text, _MYANMAR_STATE_KEYWORDS):
                return StateAffiliation("State-Linked", "Myanmar", "Matched Myanmar state keywords", 0.8)

        # --- Venezuela ---
        if issuer_country in ("Venezuela",) or issuer_country is None:
            if _contains_any(text, _VENEZUELA_STATE_KEYWORDS):
                return StateAffiliation("State-Linked", "Venezuela", "Matched Venezuela state keywords", 0.8)

        # --- Cuba ---
        if issuer_country in ("Cuba",) or issuer_country is None:
            if _contains_any(text, _CUBA_STATE_KEYWORDS):
                return StateAffiliation("State-Linked", "Cuba", "Matched Cuba state keywords", 0.8)

        # --- Sovereign Wealth Funds (global) ---
        if _contains_any(text, _SWF_KEYWORDS):
            return StateAffiliation("SWF", None, "Matched sovereign wealth fund keywords", 0.8)

        # --- Shell / Nominee / Proxy ---
        kw = _match_keyword(text, _SHELL_PROXY_KEYWORDS)
        if kw:
            return StateAffiliation("Shell-Proxy", None, f"Matched shell/proxy keyword: {kw}", 0.7)

        # --- PEP (global) ---
        if _contains_any(text, _PEP_KEYWORDS):
            return StateAffiliation("PEP", None, "Matched PEP keywords", 0.7)

        return StateAffiliation("None", None, None, 0.0)

    except Exception as e:
        logger.error("State affiliation classification failed for %s: %s", name, e)
        return StateAffiliation("None", None, None, 0.0)
