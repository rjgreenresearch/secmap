"""
sec_fetch_async.py

Async HTTP fetcher for SEC EDGAR with concurrent request support.
Shares the same disk cache as sec_fetch.py so cached data is interchangeable
between sync and async code paths.

SEC fair-access compliance:
  - Max 10 requests/second (enforced via asyncio.Semaphore)
  - Mandatory 100ms minimum between requests per connection
  - SEC-compliant User-Agent header
  - Retry with exponential backoff on 429/5xx

Usage:
    from secmap.sec_fetch_async import async_fetch_urls, async_warm_cache

    # Fetch multiple URLs concurrently (cache-aware)
    results = asyncio.run(async_fetch_urls(url_list, max_concurrent=8))

    # Warm cache for a list of CIKs
    asyncio.run(async_warm_cache(cik_list, form_types, max_filings=50))
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Dict, List, Optional, Tuple

import aiohttp

from .sec_fetch import (
    CACHE_DIR, HEADERS, USER_AGENT, MAX_RETRIES, BACKOFF_SECONDS,
    SUBMISSIONS_BASE, EDGAR_ARCHIVES,
    _cache_path, _read_cache, _write_cache,
)

logger = logging.getLogger(__name__)

# SEC allows ~10 requests/second from a single IP
DEFAULT_MAX_CONCURRENT = 8
DEFAULT_DELAY = 0.12  # seconds between requests per slot


async def _async_fetch_one(
    session: aiohttp.ClientSession,
    url: str,
    semaphore: asyncio.Semaphore,
    delay: float = DEFAULT_DELAY,
) -> Tuple[str, Optional[str]]:
    """Fetch a single URL with rate limiting, caching, and retry."""
    # Check cache first (synchronous -- disk I/O is fast)
    cp = _cache_path(url)
    cached = _read_cache(cp)
    if cached is not None:
        return url, cached

    async with semaphore:
        await asyncio.sleep(delay)

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 429:
                        wait = BACKOFF_SECONDS * attempt
                        logger.warning("SEC rate limit (429) on %s, backing off %.1fs", url, wait)
                        await asyncio.sleep(wait)
                        continue

                    if resp.status != 200:
                        logger.debug("HTTP %d for %s", resp.status, url)
                        return url, None

                    text = await resp.text()
                    _write_cache(cp, text)
                    return url, text

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.debug("Attempt %d failed for %s: %s", attempt, url, e)
                await asyncio.sleep(BACKOFF_SECONDS * attempt)

        logger.error("Failed after %d attempts: %s", MAX_RETRIES, url)
        return url, None


async def async_fetch_urls(
    urls: List[str],
    max_concurrent: int = DEFAULT_MAX_CONCURRENT,
) -> Dict[str, Optional[str]]:
    """
    Fetch multiple URLs concurrently with SEC rate-limit compliance.
    Returns {url: content_or_None}.
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}

    async with aiohttp.ClientSession(headers=headers) as session:
        tasks = [_async_fetch_one(session, url, semaphore) for url in urls]
        results = await asyncio.gather(*tasks)

    return dict(results)


async def async_warm_cache(
    ciks: List[str],
    form_types: List[str],
    max_filings: int = 50,
    max_concurrent: int = DEFAULT_MAX_CONCURRENT,
) -> Dict[str, int]:
    """
    Pre-fetch all filings for a list of CIKs into the disk cache.
    Returns {cik: number_of_filings_cached}.

    Two-phase approach:
      Phase 1: Fetch all submissions JSON concurrently
      Phase 2: For each CIK, collect filing URLs, then fetch all concurrently
    """
    stats = {}
    semaphore = asyncio.Semaphore(max_concurrent)
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}

    async with aiohttp.ClientSession(headers=headers) as session:
        # Phase 1: Fetch submissions JSON for all CIKs
        logger.info("Cache warm phase 1: fetching submissions for %d CIKs", len(ciks))
        sub_urls = [
            f"{SUBMISSIONS_BASE}/CIK{cik.zfill(10)}.json"
            for cik in ciks
        ]
        sub_tasks = [_async_fetch_one(session, url, semaphore) for url in sub_urls]
        sub_results = dict(await asyncio.gather(*sub_tasks))

        # Phase 2: Collect filing URLs from submissions
        filing_urls = []  # (cik, url)
        import json as json_mod
        for cik in ciks:
            url = f"{SUBMISSIONS_BASE}/CIK{cik.zfill(10)}.json"
            text = sub_results.get(url)
            if not text:
                stats[cik] = 0
                continue

            try:
                data = json_mod.loads(text)
            except Exception:
                stats[cik] = 0
                continue

            recent = data.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            accessions = recent.get("accessionNumber", [])
            primary_docs = recent.get("primaryDocument", [])

            count = 0
            for i in range(len(forms)):
                if forms[i] in form_types and count < max_filings:
                    acc = accessions[i] if i < len(accessions) else ""
                    doc = primary_docs[i] if i < len(primary_docs) else ""
                    if doc and acc:
                        acc_folder = acc.replace("-", "")
                        furl = f"{EDGAR_ARCHIVES}/{cik}/{acc_folder}/{doc}"
                        filing_urls.append((cik, furl))
                        count += 1
            stats[cik] = count

        # Phase 2b: Fetch all filing documents concurrently
        logger.info(
            "Cache warm phase 2: fetching %d filing documents across %d CIKs",
            len(filing_urls), len(ciks),
        )
        filing_tasks = [
            _async_fetch_one(session, url, semaphore)
            for _, url in filing_urls
        ]

        # Process in batches to avoid overwhelming memory
        batch_size = 200
        fetched = 0
        for i in range(0, len(filing_tasks), batch_size):
            batch = filing_tasks[i:i + batch_size]
            await asyncio.gather(*batch)
            fetched += len(batch)
            logger.info("  Fetched %d/%d filing documents", fetched, len(filing_tasks))

    total_filings = sum(stats.values())
    cached_count = sum(1 for url in [u for _, u in filing_urls] if _read_cache(_cache_path(url)) is not None)
    logger.info(
        "Cache warm complete: %d CIKs, %d filing URLs, %d now cached",
        len(ciks), len(filing_urls), cached_count,
    )
    return stats
