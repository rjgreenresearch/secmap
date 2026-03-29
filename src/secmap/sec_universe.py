"""
sec_universe.py

Pulls the complete SEC filing universe from official SEC mapping endpoints:
  - company_tickers.json         (all tickers + CIKs + names)
  - company_tickers_exchange.json (tickers + CIKs + exchange)
  - company_tickers_mf.json      (mutual funds + ETFs)

Provides filterable access to the full SEC universe for systematic
research-scale beneficial ownership mapping.

Usage:
    from secmap.sec_universe import SECUniverse

    universe = SECUniverse()
    universe.load()

    # All NYSE-listed companies
    nyse = universe.by_exchange("NYSE")

    # All companies
    all_ciks = universe.all_companies()

    # Mutual funds
    funds = universe.mutual_funds()
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set

import requests

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "SECMap/1.0 (Contact: research@rjgreenresearch.org; "
                  "Developer: Robert Green; Purpose: academic research)",
}

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
EXCHANGE_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
MF_URL = "https://www.sec.gov/files/company_tickers_mf.json"

CACHE_DIR = os.environ.get("SECMAP_CACHE_DIR", os.path.join(".", "cache"))


@dataclass
class Company:
    cik: str
    name: str
    ticker: str = ""
    exchange: str = ""


@dataclass
class MutualFund:
    cik: str
    series_id: str = ""
    class_id: str = ""
    symbol: str = ""


@dataclass
class SECUniverse:
    companies: List[Company] = field(default_factory=list)
    funds: List[MutualFund] = field(default_factory=list)
    _by_exchange: Dict[str, List[Company]] = field(default_factory=dict)
    _by_cik: Dict[str, Company] = field(default_factory=dict)
    _loaded: bool = False

    def load(self, use_cache: bool = True):
        """Load all SEC universe data from endpoints (or cache)."""
        self._load_exchange_tickers(use_cache)
        self._load_mutual_funds(use_cache)
        self._loaded = True
        logger.info(
            "SEC Universe loaded: %d companies, %d mutual funds, %d exchanges",
            len(self.companies), len(self.funds), len(self._by_exchange),
        )

    def _fetch_json(self, url: str, use_cache: bool) -> Optional[dict]:
        cache_path = os.path.join(CACHE_DIR, "universe", url.split("/")[-1])
        if use_cache and os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                logger.debug("Universe cache HIT: %s", cache_path)
                return json.load(f)

        time.sleep(0.15)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code != 200:
                logger.error("Failed to fetch %s: HTTP %d", url, resp.status_code)
                return None
            data = resp.json()
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            logger.info("Fetched and cached: %s", url)
            return data
        except Exception as e:
            logger.error("Failed to fetch %s: %s", url, e)
            return None

    def _load_exchange_tickers(self, use_cache: bool):
        data = self._fetch_json(EXCHANGE_URL, use_cache)
        if not data:
            return

        fields = data.get("fields", [])
        rows = data.get("data", [])

        for row in rows:
            cik = str(row[0]).strip()
            name = str(row[1]).strip() if row[1] else ""
            ticker = str(row[2]).strip() if row[2] else ""
            exchange = str(row[3]).strip() if len(row) > 3 and row[3] else ""

            company = Company(cik=cik, name=name, ticker=ticker, exchange=exchange)
            self.companies.append(company)
            self._by_cik[cik] = company

            if exchange not in self._by_exchange:
                self._by_exchange[exchange] = []
            self._by_exchange[exchange].append(company)

    def _load_mutual_funds(self, use_cache: bool):
        data = self._fetch_json(MF_URL, use_cache)
        if not data:
            return

        rows = data.get("data", [])
        for row in rows:
            self.funds.append(MutualFund(
                cik=str(row[0]).strip(),
                series_id=str(row[1]).strip() if len(row) > 1 and row[1] else "",
                class_id=str(row[2]).strip() if len(row) > 2 and row[2] else "",
                symbol=str(row[3]).strip() if len(row) > 3 and row[3] else "",
            ))

    # -----------------------------------------------------------------
    # Query methods
    # -----------------------------------------------------------------

    def all_companies(self) -> List[Company]:
        return self.companies

    def all_ciks(self) -> List[str]:
        return [c.cik for c in self.companies]

    def by_exchange(self, exchange: str) -> List[Company]:
        return self._by_exchange.get(exchange, [])

    def exchanges(self) -> Dict[str, int]:
        return {ex: len(companies) for ex, companies in self._by_exchange.items()}

    def by_cik(self, cik: str) -> Optional[Company]:
        return self._by_cik.get(cik)

    def mutual_funds(self) -> List[MutualFund]:
        return self.funds

    def search(self, query: str) -> List[Company]:
        q = query.lower()
        return [c for c in self.companies
                if q in c.name.lower() or q in c.ticker.lower()]

    def unique_fund_ciks(self) -> Set[str]:
        return {f.cik for f in self.funds}
