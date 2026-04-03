"""
role_taxonomy.py

Defines canonical role categories and deterministic classification logic
for people and institutions extracted from SEC filings.

Designed for beneficial ownership chain tracing: includes roles that
indicate layered or obscured ownership (nominee, agent, proxy, UBO),
as well as standard corporate governance roles.

Enhancements:
- Full logging
- Deterministic classification
- Robust regex matching
- Exception-safe fallbacks
- Clear canonical role mapping
- Ownership-chain-specific role categories
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclass representing a classified role
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RoleClassification:
    canonical_role: str
    raw_role_text: Optional[str] = None
    confidence: float = 0.0
    is_executive: bool = False
    is_board: bool = False
    is_supervisory: bool = False
    is_ownership: bool = False
    is_state_affiliated: bool = False
    is_obscuring: bool = False  # indicates layering / opacity in chain


# ---------------------------------------------------------------------------
# Canonical role categories
# ---------------------------------------------------------------------------

_CANONICAL_ROLES = {
    # ===================================================================
    # C-Suite
    # ===================================================================
    "CEO": ["chief executive officer", "ceo", "deputy chief executive officer", "deputy ceo"],
    "CFO": ["chief financial officer", "cfo", "deputy chief financial officer", "deputy cfo"],
    "COO": ["chief operating officer", "coo", "deputy chief operating officer"],
    "CTO": ["chief technology officer", "deputy chief technology officer"],
    "CIO": ["chief information officer", "deputy chief information officer"],
    "CISO": ["chief information security officer"],
    "CLO": ["chief legal officer", "deputy chief legal officer"],
    "CMO": ["chief marketing officer"],
    "CHRO": ["chief human resources officer"],
    "CAO": ["chief accounting officer", "chief administrative officer", "deputy chief accounting officer"],
    "CRO": ["chief risk officer", "chief revenue officer"],
    "CSO": ["chief strategy officer", "chief sustainability officer"],
    "CDO": ["chief data officer", "chief digital officer"],
    "CCO": ["chief compliance officer", "chief commercial officer"],

    # ===================================================================
    # Board-level
    # ===================================================================
    "Chairman": ["chairman", "chairwoman", "chairperson", "chair of the board"],
    "Vice Chairman": ["vice chairman", "vice chairwoman", "vice chairperson", "deputy chairman", "deputy chairperson"],
    "Director": ["director", "board member", "member of the board", "deputy director"],
    "Lead Independent Director": ["lead independent director", "lead director", "presiding director"],
    "Non-Executive Director": ["non-executive director", "independent non-executive director", "ined"],
    "Supervisory Board": ["supervisory board member", "supervisor", "supervisory director", "deputy supervisor"],

    # ===================================================================
    # Executive
    # ===================================================================
    "Vice President": [
        "deputy vice president",
        "vice president",
        "executive vice president", "evp",
        "senior vice president", "svp",
        "assistant vice president", "avp",
        "first vice president",
    ],
    "President": ["president", "deputy president"],
    "Managing Director": ["managing director", "deputy managing director"],
    "Executive Director": ["executive director", "deputy executive director"],
    "General Manager": ["general manager", "deputy general manager"],

    # ===================================================================
    # SEC-filing-specific
    # ===================================================================
    "Principal Financial Officer": ["principal financial officer", "pfo"],
    "Principal Accounting Officer": ["principal accounting officer", "pao"],
    "Principal Executive Officer": ["principal executive officer", "peo"],
    "Authorized Representative": [
        "authorized representative", "authorised representative",
        "authorized signatory", "authorised signatory",
        "authorized officer", "authorised officer",
    ],
    "Reporting Person": ["reporting person", "filer", "filing person"],

    # ===================================================================
    # Finance & accounting
    # ===================================================================
    "Treasurer": ["treasurer", "assistant treasurer"],
    "Controller": ["controller", "comptroller"],

    # ===================================================================
    # Legal & compliance
    # ===================================================================
    "Secretary": ["secretary", "corporate secretary", "assistant secretary", "company secretary", "deputy secretary"],
    "General Counsel": ["general counsel", "chief legal counsel", "deputy general counsel"],
    "Compliance Officer": ["compliance officer", "chief compliance officer", "deputy compliance officer"],

    # ===================================================================
    # Audit
    # ===================================================================
    "Audit Committee Chair": ["audit committee chair", "chair of the audit committee"],
    "Internal Auditor": ["internal auditor", "chief audit executive", "deputy auditor"],

    # ===================================================================
    # Deputy roles -- common in foreign (esp. PRC) SC-13 filings
    # Catch-all for deputy titles not covered above
    # ===================================================================
    "Deputy Director": [
        "deputy director of economics", "deputy director of finance",
        "deputy director of operations", "deputy director of research",
        "deputy director of technology", "deputy director of strategy",
        "deputy director of investment", "deputy director of compliance",
        "deputy director of risk", "deputy director of audit",
        "deputy director of human resources", "deputy director of marketing",
        "deputy director of legal", "deputy director of administration",
        "deputy director of planning", "deputy director of development",
        "deputy director of international", "deputy director of trade",
        "deputy director of procurement", "deputy director of production",
        "deputy director of engineering", "deputy director of security",
    ],
    "Deputy Minister": [
        "deputy minister", "vice minister",
        "deputy minister of finance", "deputy minister of commerce",
        "deputy minister of defense", "deputy minister of defence",
        "deputy minister of foreign affairs", "deputy minister of trade",
        "deputy minister of industry", "deputy minister of science",
        "deputy minister of technology", "deputy minister of education",
    ],
    "Deputy Governor": [
        "deputy governor", "vice governor",
        "deputy governor of the central bank",
        "deputy governor of the province",
    ],
    "Deputy Mayor": ["deputy mayor", "vice mayor"],
    "Deputy Commissioner": ["deputy commissioner", "deputy chief commissioner"],
    "Deputy Chief": [
        "deputy chief", "deputy chief of staff",
        "deputy chief economist", "deputy chief engineer",
        "deputy chief scientist", "deputy chief accountant",
        "deputy chief counsel",
    ],

    # ===================================================================
    # Investment & fund
    # ===================================================================
    "Partner": [
        "partner", "general partner", "limited partner",
        "managing partner", "senior partner", "junior partner",
    ],
    "Manager": [
        "manager", "fund manager", "portfolio manager",
        "investment manager", "asset manager",
    ],
    "Advisor": [
        "advisor", "adviser",
        "investment adviser", "financial advisor",
        "strategic advisor",
    ],
    "Trustee": ["trustee", "co-trustee"],
    "Custodian": ["custodian", "sub-custodian"],
    "Depositary": ["depositary", "depository"],

    # ===================================================================
    # Ownership -- critical for UBO chain tracing
    # ===================================================================
    "Beneficial Owner": ["beneficial owner", "ultimate beneficial owner", "ubo"],
    "Owner": ["owner"],
    "Controlling Person": [
        "controlling person", "control person",
        "controlling shareholder", "controlling interest",
        "controlling member",
    ],
    "Significant Shareholder": [
        "significant shareholder", "major shareholder",
        "principal shareholder", "substantial shareholder",
        "large shareholder", "block holder", "blockholder",
    ],
    "Majority Owner": ["majority owner", "majority shareholder", "majority interest"],
    "Minority Owner": ["minority owner", "minority shareholder", "minority interest"],

    # ===================================================================
    # Obscuring / layering roles -- red flags in ownership chains
    # ===================================================================
    "Nominee": [
        "nominee", "nominee shareholder", "nominee director",
        "nominee holder", "nominee owner",
        "nominal holder", "nominal shareholder",
    ],
    "Agent": [
        "registered agent", "resident agent",
        "corporate agent", "formation agent",
        "incorporation agent", "service agent",
    ],
    "Proxy": [
        "proxy holder", "proxy",
        "attorney-in-fact", "power of attorney",
        "poa holder",
    ],
    "Intermediary": [
        "intermediary", "intermediate holder",
        "intermediate entity", "conduit",
        "pass-through", "pass through",
    ],
    "Settlor": ["settlor", "grantor", "trustor"],
    "Protector": ["protector", "trust protector", "enforcer"],

    # ===================================================================
    # Founder
    # ===================================================================
    "Founder": ["founder", "co-founder", "cofounder"],
}

# ---------------------------------------------------------------------------
# Role metadata -- which roles belong to which categories
# ---------------------------------------------------------------------------

_EXECUTIVE_ROLES = {
    "CEO", "CFO", "COO", "CTO", "CIO", "CISO", "CLO", "CMO", "CHRO",
    "CAO", "CRO", "CSO", "CDO", "CCO", "President", "Vice President",
    "Managing Director", "Executive Director", "General Manager",
    "Principal Financial Officer", "Principal Accounting Officer",
    "Principal Executive Officer",
    "Deputy Chief",
}

_BOARD_ROLES = {
    "Chairman", "Vice Chairman", "Director", "Deputy Director",
    "Lead Independent Director", "Non-Executive Director",
}

_SUPERVISORY_ROLES = {
    "Supervisory Board",
}

_OWNERSHIP_ROLES = {
    "Owner", "Beneficial Owner", "Controlling Person",
    "Significant Shareholder", "Majority Owner", "Minority Owner",
    "Founder",
}

_OBSCURING_ROLES = {
    "Nominee", "Agent", "Proxy", "Intermediary",
    "Settlor", "Protector",
}

# Precompile regex patterns with word boundaries to prevent
# substring false positives (e.g. 'cto' matching inside 'Director').
# Terms are sorted longest-first so longer phrases match before
# shorter substrings in regex alternation.
_ROLE_PATTERNS = {
    canonical: re.compile(
        r"|".join(
            [r"\b" + re.escape(term) + r"\b"
             for term in sorted(terms, key=len, reverse=True)]
        ),
        re.IGNORECASE,
    )
    for canonical, terms in _CANONICAL_ROLES.items()
}


# ---------------------------------------------------------------------------
# Classification logic
# ---------------------------------------------------------------------------

def classify_role(name: str, context_text: str) -> RoleClassification:
    """
    Classify a person's or institution's role based on nearby text.

    Args:
        name: Extracted entity name
        context_text: Narrative or signature block text

    Returns:
        RoleClassification with semantic flags for chain analysis
    """
    if not name:
        logger.warning("classify_role() received empty name")
        return RoleClassification(canonical_role="Unknown", confidence=0.0)

    if not context_text:
        logger.debug("No context text provided for role classification")
        return RoleClassification(canonical_role="Unknown", confidence=0.0)

    try:
        window_size = 200
        idx = context_text.lower().find(name.lower())

        if idx != -1:
            start = max(0, idx - window_size)
            end = min(len(context_text), idx + window_size)
            window = context_text[start:end]
        else:
            window = context_text

        for canonical, pattern in _ROLE_PATTERNS.items():
            if pattern.search(window):
                logger.debug("Classified %s as %s", name, canonical)
                return RoleClassification(
                    canonical_role=canonical,
                    raw_role_text=window,
                    confidence=0.9,
                    is_executive=canonical in _EXECUTIVE_ROLES,
                    is_board=canonical in _BOARD_ROLES,
                    is_supervisory=canonical in _SUPERVISORY_ROLES,
                    is_ownership=canonical in _OWNERSHIP_ROLES,
                    is_obscuring=canonical in _OBSCURING_ROLES,
                )

        # Fallback: generic terms
        if "officer" in window.lower():
            return RoleClassification("Officer", raw_role_text=window, confidence=0.5, is_executive=True)
        if "director" in window.lower():
            return RoleClassification("Director", raw_role_text=window, confidence=0.5, is_board=True)

        return RoleClassification("Unknown", raw_role_text=None, confidence=0.0)

    except Exception as e:
        logger.error("Role classification failed for %s: %s", name, e)
        return RoleClassification("Unknown", raw_role_text=None, confidence=0.0)
