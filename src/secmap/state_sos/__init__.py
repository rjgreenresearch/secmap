"""
state_sos/__init__.py

State Secretary of State (SOS) Integration Module

Bridges the critical gap between:
  - SEC EDGAR (federal, public companies)
  - USDA AFIDA (federal, agricultural foreign investment, self-reported)
  - State SOS records (state-level, ALL business entities including private)

The Problem:
  Federal agencies (SEC, CFIUS, USDA) have limited visibility into
  state-level business registrations. Adversarial-nation ownership
  chains frequently terminate in state-registered LLCs, LPs, and
  trusts that are invisible to federal beneficial ownership databases.

  Example: Brazos Highland Properties LP (Texas) -> Guangxin Sun
  (former PLA officer, largest Chinese landowner in US) was only
  discoverable through Texas SOS records, not through any federal
  filing.

State SOS Access Landscape (as of 2026):

  ACCESS_TIER_API — States with free, programmatic API access:
    California, Colorado, Connecticut, Delaware (ECORP),
    Massachusetts, Michigan, Oregon, Pennsylvania, Washington

  ACCESS_TIER_BULK — States with free bulk download / CSV export:
    Alaska, Florida, Georgia, Illinois, Indiana, Iowa, Kansas,
    Maryland, Minnesota, Missouri, Nebraska, New Hampshire,
    New Jersey, North Carolina, Ohio, Oklahoma, South Carolina,
    Tennessee, Utah, Virginia, Wisconsin

  ACCESS_TIER_WEB — States with free web search (scraping required):
    Alabama, Arizona, Arkansas, Hawaii, Idaho, Kentucky, Louisiana,
    Maine, Mississippi, Montana, Nevada, New Mexico, New York,
    North Dakota, Rhode Island, South Dakota, Vermont, West Virginia,
    Wyoming, District of Columbia

  ACCESS_TIER_PAYWALL — States requiring payment or delayed delivery:
    Texas ($1/page, cold storage, hours-to-days delivery)

  ACCESS_TIER_RESTRICTED — States with significant access barriers:
    (None currently identified as fully restricted, but some states
    limit online access to certain entity types or require in-person
    requests for officer/director information)

Priority States for Research (by foreign ownership risk):
  1. Delaware — incorporation haven, 1.5M+ entities, API available
  2. Texas — largest ag land holdings, paywall access
  3. Nevada — anonymous LLCs, web search only
  4. Wyoming — anonymous LLCs, web search only
  5. South Dakota — trust haven, web search only
  6. New York — financial entities, web search only
  7. California — tech + real estate, API available
  8. Florida — real estate, bulk download available
"""

from .gap_analyzer import GapAnalyzer, StateEntity, GapEntry
from .state_registry import StateRegistry, AccessTier, STATE_ACCESS_MAP
from .texas_sos import TexasSOSParser
