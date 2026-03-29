"""
sec_fetch.py

Responsible for fetching SEC EDGAR filings in a rate-limit-compliant,
production-safe manner with disk-based caching.

Features:
- SEC-compliant User-Agent
- Mandatory inter-request delay (SEC fair access)
- Retry logic with backoff
- Disk cache for submissions JSON and filing content
- Fetch company submissions JSON from data.sec.gov
- Fetch filing content by accession + primaryDocument
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import logging
from typing import Optional, List, Dict

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SEC EDGAR configuration
# ---------------------------------------------------------------------------

EDGAR_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
SUBMISSIONS_BASE = "https://data.sec.gov/submissions"

USER_AGENT = (
    "SECMap/1.0 (Contact: research@rjgreenresearch.org; "
    "Developer: Robert Green; Purpose: academic research)"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
}

MAX_RETRIES = 5
BACKOFF_SECONDS = 1.5
REQUEST_DELAY = 0.15

# ---------------------------------------------------------------------------
# Disk cache
# ---------------------------------------------------------------------------

CACHE_DIR = os.environ.get("SECMAP_CACHE_DIR", os.path.join(".", "cache"))


def _cache_path(url: str) -> str:
    """Deterministic cache file path from URL."""
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    # Use URL structure for human-readable subdirs
    safe_name = url.replace("https://", "").replace("http://", "")
    safe_name = safe_name.replace("/", os.sep).replace("?", "_").replace("&", "_")
    # Truncate long paths, append hash for uniqueness
    if len(safe_name) > 120:
        safe_name = safe_name[:120]
    return os.path.join(CACHE_DIR, safe_name + "." + url_hash)


def _read_cache(path: str) -> Optional[str]:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            logger.debug("Cache HIT: %s", path)
            return content
    except Exception as e:
        logger.warning("Cache read failed for %s: %s", path, e)
    return None


def _write_cache(path: str, content: str):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.debug("Cache WRITE: %s", path)
    except Exception as e:
        logger.warning("Cache write failed for %s: %s", path, e)


# ---------------------------------------------------------------------------
# Core HTTP fetcher with retry + SEC compliance + caching
# ---------------------------------------------------------------------------

def _http_get(url: str, use_cache: bool = True) -> Optional[requests.Response]:
    """
    Perform a GET request with retry logic, SEC-compliant headers,
    and optional disk caching. Returns Response object or None.
    """
    # Check cache first
    if use_cache:
        cp = _cache_path(url)
        cached = _read_cache(cp)
        if cached is not None:
            # Build a fake response-like object isn't clean;
            # instead we return None here and let callers use
            # _http_get_text() for cached text access.
            pass  # fall through — cache is handled at higher level

    time.sleep(REQUEST_DELAY)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.debug("Fetching URL (attempt %d): %s", attempt, url)
            resp = requests.get(url, headers=HEADERS, timeout=30)

            if resp.status_code == 429:
                logger.warning("SEC rate limit hit (429). Backing off.")
                time.sleep(BACKOFF_SECONDS * attempt)
                continue

            if resp.status_code != 200:
                logger.error("HTTP %d for URL: %s", resp.status_code, url)
                return None

            # Write to cache
            if use_cache:
                _write_cache(_cache_path(url), resp.text)

            return resp

        except requests.RequestException as e:
            logger.error("Request error for URL %s: %s", url, e)
            time.sleep(BACKOFF_SECONDS * attempt)

    logger.critical("Failed to fetch URL after %d attempts: %s", MAX_RETRIES, url)
    return None


def _fetch_text(url: str) -> Optional[str]:
    """Fetch URL text with disk caching. Returns cached content if available."""
    cp = _cache_path(url)
    cached = _read_cache(cp)
    if cached is not None:
        return cached

    resp = _http_get(url, use_cache=True)
    return resp.text if resp else None


def _fetch_json(url: str) -> Optional[Dict]:
    """Fetch URL and parse as JSON with disk caching."""
    cp = _cache_path(url)
    cached = _read_cache(cp)
    if cached is not None:
        try:
            return json.loads(cached)
        except Exception:
            logger.warning("Cached JSON invalid, re-fetching: %s", url)

    resp = _http_get(url, use_cache=True)
    if not resp:
        return None
    try:
        return resp.json()
    except Exception as e:
        logger.error("Failed to parse JSON from %s: %s", url, e)
        return None


# ---------------------------------------------------------------------------
# Fetch company submissions JSON
# ---------------------------------------------------------------------------

def fetch_company_submissions(cik: str) -> Optional[Dict]:
    cik_padded = cik.zfill(10)
    url = f"{SUBMISSIONS_BASE}/CIK{cik_padded}.json"
    logger.debug("Fetching submissions for CIK %s", cik)
    return _fetch_json(url)


# ---------------------------------------------------------------------------
# Fetch latest filings of specific form types
# ---------------------------------------------------------------------------

def fetch_latest_filings(
    cik: str,
    form_types: List[str],
    limit: int = 20,
) -> List[Dict]:
    submissions = fetch_company_submissions(cik)
    if not submissions:
        return []

    company_name = submissions.get("name", f"CIK {cik}")

    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    dates = recent.get("filingDate", [])
    primary_docs = recent.get("primaryDocument", [])

    results = []
    for i in range(len(forms)):
        if forms[i] in form_types:
            results.append({
                "form": forms[i],
                "accession": accessions[i] if i < len(accessions) else "",
                "filing_date": dates[i] if i < len(dates) else "",
                "primary_doc": primary_docs[i] if i < len(primary_docs) else "",
                "company": company_name,
                "cik": cik,
            })
            if len(results) >= limit:
                break

    logger.debug(
        "Found %d filings for CIK %s (%s) matching forms %s",
        len(results), cik, company_name, form_types,
    )
    return results


# ---------------------------------------------------------------------------
# Fetch filing content by accession + primary document
# ---------------------------------------------------------------------------

def fetch_filing_content(cik: str, accession: str, primary_doc: str) -> Optional[str]:
    accession_folder = accession.replace("-", "")
    url = f"{EDGAR_ARCHIVES}/{cik}/{accession_folder}/{primary_doc}"
    logger.debug("Fetching filing content: %s/%s", accession, primary_doc)
    return _fetch_text(url)


def fetch_filing_by_accession(cik: str, accession: str) -> Optional[str]:
    accession_folder = accession.replace("-", "")
    url = f"{EDGAR_ARCHIVES}/{cik}/{accession_folder}/{accession}.txt"
    logger.debug("Fetching filing by accession: %s", accession)
    return _fetch_text(url)


# ---------------------------------------------------------------------------
# Fetch full filing text for a list of filings
# ---------------------------------------------------------------------------

def fetch_filings_for_cik(
    cik: str,
    form_types: List[str],
    limit: int = 20,
) -> List[Dict]:
    filings = fetch_latest_filings(cik, form_types, limit)
    results = []

    for f in filings:
        primary_doc = f.get("primary_doc", "")
        if primary_doc:
            content = fetch_filing_content(cik, f["accession"], primary_doc)
        else:
            content = fetch_filing_by_accession(cik, f["accession"])

        if not content:
            logger.error(
                "Failed to fetch content for accession %s (CIK %s)",
                f["accession"], cik,
            )
            continue

        results.append({
            "accession": f["accession"],
            "form": f["form"],
            "filing_date": f["filing_date"],
            "content": content,
            "company": f.get("company", ""),
            "primary_doc": primary_doc,
        })

    return results
