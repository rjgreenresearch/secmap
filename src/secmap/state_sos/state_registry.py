"""
state_registry.py

Catalogs the access method, endpoint, cost, and expected latency
for each state's Secretary of State business entity database.

This is the operational backbone for systematic state-level entity
discovery. Each state has a different access model — some are free
APIs, some are bulk downloads, some require scraping, and some
(like Texas) are behind paywalls with multi-hour delivery times.

The registry enables the gap analyzer to:
  1. Know which states CAN be queried programmatically
  2. Estimate cost and time for a given research scope
  3. Prioritize states by access feasibility and risk value
  4. Track which states have been ingested vs. pending
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class AccessTier(Enum):
    API = "api"              # Free programmatic API
    BULK = "bulk"            # Free bulk download / CSV export
    WEB = "web"              # Free web search (scraping required)
    PAYWALL = "paywall"      # Requires payment per record/page
    RESTRICTED = "restricted" # Significant access barriers


@dataclass(frozen=True)
class StateAccess:
    state: str
    state_name: str
    tier: AccessTier
    endpoint: str = ""
    search_url: str = ""
    bulk_url: str = ""
    cost_per_record: float = 0.0  # USD, 0 = free
    cost_notes: str = ""
    expected_latency: str = ""    # "instant", "seconds", "minutes", "hours", "days"
    supports_officer_search: bool = False
    supports_name_search: bool = True
    supports_agent_search: bool = False
    notes: str = ""


# ===================================================================
# Complete state access catalog
# ===================================================================

STATE_ACCESS_MAP: Dict[str, StateAccess] = {
    # --- API TIER ---
    "CA": StateAccess(
        state="CA", state_name="California", tier=AccessTier.API,
        endpoint="https://bizfileonline.sos.ca.gov/api/",
        search_url="https://bizfileonline.sos.ca.gov/search/business",
        expected_latency="seconds",
        supports_officer_search=True,
        supports_agent_search=True,
        notes="Free API, comprehensive data, includes officers",
    ),
    "CO": StateAccess(
        state="CO", state_name="Colorado", tier=AccessTier.API,
        endpoint="https://www.sos.state.co.us/biz/",
        search_url="https://www.sos.state.co.us/biz/BusinessEntityCriteriaExt.do",
        expected_latency="seconds",
        supports_officer_search=True,
    ),
    "CT": StateAccess(
        state="CT", state_name="Connecticut", tier=AccessTier.API,
        search_url="https://service.ct.gov/business/s/onlinebusinesssearch",
        expected_latency="seconds",
    ),
    "DE": StateAccess(
        state="DE", state_name="Delaware", tier=AccessTier.API,
        endpoint="https://icis.corp.delaware.gov/ecorp/entitysearch/",
        search_url="https://icis.corp.delaware.gov/ecorp/entitysearch/namesearch.aspx",
        expected_latency="seconds",
        notes="ECORP system. Delaware is #1 incorporation state. Limited officer data online.",
    ),
    "MA": StateAccess(
        state="MA", state_name="Massachusetts", tier=AccessTier.API,
        search_url="https://corp.sec.state.ma.us/corpweb/CorpSearch/CorpSearch.aspx",
        expected_latency="seconds",
        supports_officer_search=True,
    ),
    "MI": StateAccess(
        state="MI", state_name="Michigan", tier=AccessTier.API,
        search_url="https://cofs.lara.state.mi.us/SearchApi/Search/Search",
        expected_latency="seconds",
    ),
    "OR": StateAccess(
        state="OR", state_name="Oregon", tier=AccessTier.API,
        search_url="http://egov.sos.state.or.us/br/pkg_web_name_srch_inq.login",
        expected_latency="seconds",
    ),
    "PA": StateAccess(
        state="PA", state_name="Pennsylvania", tier=AccessTier.API,
        search_url="https://www.corporations.pa.gov/search/corpsearch",
        expected_latency="seconds",
    ),
    "WA": StateAccess(
        state="WA", state_name="Washington", tier=AccessTier.API,
        search_url="https://ccfs.sos.wa.gov/",
        expected_latency="seconds",
        supports_officer_search=True,
    ),

    # --- BULK DOWNLOAD TIER ---
    "AK": StateAccess(state="AK", state_name="Alaska", tier=AccessTier.BULK,
        search_url="https://www.commerce.alaska.gov/cbp/main/search/entities",
        expected_latency="seconds"),
    "FL": StateAccess(state="FL", state_name="Florida", tier=AccessTier.BULK,
        search_url="https://search.sunbiz.org/Inquiry/CorporationSearch/ByName",
        bulk_url="https://dos.fl.gov/sunbiz/bulk-data/",
        expected_latency="instant",
        supports_officer_search=True,
        notes="Sunbiz bulk data available. High foreign real estate ownership."),
    "GA": StateAccess(state="GA", state_name="Georgia", tier=AccessTier.BULK,
        search_url="https://ecorp.sos.ga.gov/BusinessSearch",
        expected_latency="seconds"),
    "IL": StateAccess(state="IL", state_name="Illinois", tier=AccessTier.BULK,
        search_url="https://www.ilsos.gov/corporatellc/",
        expected_latency="seconds"),
    "IN": StateAccess(state="IN", state_name="Indiana", tier=AccessTier.BULK,
        search_url="https://bsd.sos.in.gov/publicbusinesssearch",
        expected_latency="seconds"),
    "IA": StateAccess(state="IA", state_name="Iowa", tier=AccessTier.BULK,
        search_url="https://sos.iowa.gov/search/business/(S(...))/search.aspx",
        expected_latency="seconds"),
    "KS": StateAccess(state="KS", state_name="Kansas", tier=AccessTier.BULK,
        search_url="https://www.kansas.gov/bess/flow/main",
        expected_latency="seconds"),
    "MD": StateAccess(state="MD", state_name="Maryland", tier=AccessTier.BULK,
        search_url="https://egov.maryland.gov/BusinessExpress/EntitySearch",
        expected_latency="seconds"),
    "MN": StateAccess(state="MN", state_name="Minnesota", tier=AccessTier.BULK,
        search_url="https://mblsportal.sos.state.mn.us/Business/Search",
        expected_latency="seconds"),
    "MO": StateAccess(state="MO", state_name="Missouri", tier=AccessTier.BULK,
        search_url="https://bsd.sos.mo.gov/BusinessEntity/BESearch.aspx",
        expected_latency="seconds"),
    "NE": StateAccess(state="NE", state_name="Nebraska", tier=AccessTier.BULK,
        search_url="https://www.nebraska.gov/sos/corp/corpsearch.cgi",
        expected_latency="seconds"),
    "NH": StateAccess(state="NH", state_name="New Hampshire", tier=AccessTier.BULK,
        search_url="https://quickstart.sos.nh.gov/online/BusinessInquire",
        expected_latency="seconds"),
    "NJ": StateAccess(state="NJ", state_name="New Jersey", tier=AccessTier.BULK,
        search_url="https://www.njportal.com/DOR/BusinessNameSearch/",
        expected_latency="seconds"),
    "NC": StateAccess(state="NC", state_name="North Carolina", tier=AccessTier.BULK,
        search_url="https://www.sosnc.gov/online_services/search/by_title/_Business_Registration",
        expected_latency="seconds"),
    "OH": StateAccess(state="OH", state_name="Ohio", tier=AccessTier.BULK,
        search_url="https://businesssearch.ohiosos.gov/",
        expected_latency="seconds"),
    "OK": StateAccess(state="OK", state_name="Oklahoma", tier=AccessTier.BULK,
        search_url="https://www.sos.ok.gov/corp/corpInquiryFind.aspx",
        expected_latency="seconds"),
    "SC": StateAccess(state="SC", state_name="South Carolina", tier=AccessTier.BULK,
        search_url="https://businessfilings.sc.gov/BusinessFiling/Entity/Search",
        expected_latency="seconds"),
    "TN": StateAccess(state="TN", state_name="Tennessee", tier=AccessTier.BULK,
        search_url="https://tnbear.tn.gov/Ecommerce/FilingSearch.aspx",
        expected_latency="seconds"),
    "UT": StateAccess(state="UT", state_name="Utah", tier=AccessTier.BULK,
        search_url="https://secure.utah.gov/bes/",
        expected_latency="seconds"),
    "VA": StateAccess(state="VA", state_name="Virginia", tier=AccessTier.BULK,
        search_url="https://cis.scc.virginia.gov/EntitySearch/Index",
        expected_latency="seconds",
        notes="Smithfield Foods incorporated here."),
    "WI": StateAccess(state="WI", state_name="Wisconsin", tier=AccessTier.BULK,
        search_url="https://www.wdfi.org/apps/CorpSearch/Search.aspx",
        expected_latency="seconds"),

    # --- WEB SEARCH TIER (scraping required) ---
    "AL": StateAccess(state="AL", state_name="Alabama", tier=AccessTier.WEB,
        search_url="https://arc-sos.state.al.us/cgi/corpname.mbr/output",
        expected_latency="seconds"),
    "AZ": StateAccess(state="AZ", state_name="Arizona", tier=AccessTier.WEB,
        search_url="https://ecorp.azcc.gov/EntitySearch/Index",
        expected_latency="seconds"),
    "AR": StateAccess(state="AR", state_name="Arkansas", tier=AccessTier.WEB,
        search_url="https://www.sos.arkansas.gov/corps/search_all.php",
        expected_latency="seconds"),
    "HI": StateAccess(state="HI", state_name="Hawaii", tier=AccessTier.WEB,
        search_url="https://hbe.ehawaii.gov/documents/search.html",
        expected_latency="seconds"),
    "ID": StateAccess(state="ID", state_name="Idaho", tier=AccessTier.WEB,
        search_url="https://sosbiz.idaho.gov/search/business",
        expected_latency="seconds"),
    "KY": StateAccess(state="KY", state_name="Kentucky", tier=AccessTier.WEB,
        search_url="https://web.sos.ky.gov/bussearchnprofile/(S(...))/search",
        expected_latency="seconds"),
    "LA": StateAccess(state="LA", state_name="Louisiana", tier=AccessTier.WEB,
        search_url="https://coraweb.sos.la.gov/CommercialSearch/CommercialSearch.aspx",
        expected_latency="seconds"),
    "ME": StateAccess(state="ME", state_name="Maine", tier=AccessTier.WEB,
        search_url="https://icrs.informe.org/nei-sos-icrs/ICRS",
        expected_latency="seconds"),
    "MS": StateAccess(state="MS", state_name="Mississippi", tier=AccessTier.WEB,
        search_url="https://corp.sos.ms.gov/corp/portal/c/page/corpBusinessIdSearch/portal.aspx",
        expected_latency="seconds"),
    "MT": StateAccess(state="MT", state_name="Montana", tier=AccessTier.WEB,
        search_url="https://biz.sosmt.gov/search",
        expected_latency="seconds"),
    "NV": StateAccess(state="NV", state_name="Nevada", tier=AccessTier.WEB,
        search_url="https://esos.nv.gov/EntitySearch/OnlineEntitySearch",
        expected_latency="seconds",
        notes="Privacy-friendly LLC laws. High shell company risk."),
    "NM": StateAccess(state="NM", state_name="New Mexico", tier=AccessTier.WEB,
        search_url="https://portal.sos.state.nm.us/BFS/online/CorporationBusinessSearch",
        expected_latency="seconds"),
    "NY": StateAccess(state="NY", state_name="New York", tier=AccessTier.WEB,
        search_url="https://appext20.dos.ny.gov/corp_public/CORPSEARCH.ENTITY_SEARCH_ENTRY",
        expected_latency="seconds",
        notes="Major financial center. Limited online officer data."),
    "ND": StateAccess(state="ND", state_name="North Dakota", tier=AccessTier.WEB,
        search_url="https://firststop.sos.nd.gov/search/business",
        expected_latency="seconds"),
    "RI": StateAccess(state="RI", state_name="Rhode Island", tier=AccessTier.WEB,
        search_url="http://business.sos.ri.gov/CorpWeb/CorpSearch/CorpSearch.aspx",
        expected_latency="seconds"),
    "SD": StateAccess(state="SD", state_name="South Dakota", tier=AccessTier.WEB,
        search_url="https://sosenterprise.sd.gov/BusinessServices/Business/FilingSearch.aspx",
        expected_latency="seconds",
        notes="Trust haven. Significant foreign trust activity."),
    "VT": StateAccess(state="VT", state_name="Vermont", tier=AccessTier.WEB,
        search_url="https://bizfilings.vermont.gov/online/BusinessInquire",
        expected_latency="seconds"),
    "WV": StateAccess(state="WV", state_name="West Virginia", tier=AccessTier.WEB,
        search_url="https://apps.wv.gov/SOS/BusinessEntitySearch/",
        expected_latency="seconds"),
    "WY": StateAccess(state="WY", state_name="Wyoming", tier=AccessTier.WEB,
        search_url="https://wyobiz.wyo.gov/Business/FilingSearch.aspx",
        expected_latency="seconds",
        notes="Anonymous LLCs. No public officer/member disclosure."),
    "DC": StateAccess(state="DC", state_name="District of Columbia", tier=AccessTier.WEB,
        search_url="https://corponline.dcra.dc.gov/Home.aspx",
        expected_latency="seconds"),

    # --- PAYWALL TIER ---
    "TX": StateAccess(
        state="TX", state_name="Texas", tier=AccessTier.PAYWALL,
        search_url="https://mycpa.cpa.state.tx.us/coa/",
        cost_per_record=1.00,
        cost_notes="$1/page for certified copies. Documents pulled from cold storage or scanned from paper. Delivery can take hours to days.",
        expected_latency="hours",
        supports_officer_search=False,
        notes="Largest agricultural land holdings. Brazos Highland Properties LP case. SOS returns PDFs via email after payment.",
    ),
}


class StateRegistry:
    """
    Query interface for the state SOS access catalog.

    Usage:
        registry = StateRegistry()
        api_states = registry.by_tier(AccessTier.API)
        tx = registry.get("TX")
        cost = registry.estimate_cost("TX", num_records=50)
    """

    def __init__(self):
        self._map = STATE_ACCESS_MAP

    def get(self, state_code: str) -> Optional[StateAccess]:
        return self._map.get(state_code.upper())

    def by_tier(self, tier: AccessTier) -> List[StateAccess]:
        return [s for s in self._map.values() if s.tier == tier]

    def all_states(self) -> List[StateAccess]:
        return list(self._map.values())

    def api_states(self) -> List[StateAccess]:
        return self.by_tier(AccessTier.API)

    def bulk_states(self) -> List[StateAccess]:
        return self.by_tier(AccessTier.BULK)

    def free_states(self) -> List[StateAccess]:
        """States with free programmatic or bulk access."""
        return self.by_tier(AccessTier.API) + self.by_tier(AccessTier.BULK)

    def scrapeable_states(self) -> List[StateAccess]:
        return self.by_tier(AccessTier.WEB)

    def paywall_states(self) -> List[StateAccess]:
        return self.by_tier(AccessTier.PAYWALL)

    def estimate_cost(self, state_code: str, num_records: int) -> float:
        access = self.get(state_code)
        if not access:
            return 0.0
        return access.cost_per_record * num_records

    def coverage_summary(self) -> Dict[str, int]:
        summary = {}
        for tier in AccessTier:
            summary[tier.value] = len(self.by_tier(tier))
        return summary

    def search_url(self, state_code: str) -> str:
        access = self.get(state_code)
        return access.search_url if access else ""
