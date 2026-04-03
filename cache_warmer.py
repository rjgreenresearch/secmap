"""
cache_warmer.py

Pre-fetches SEC EDGAR filings into the disk cache using async HTTP.
Run this before a production/research run to eliminate network latency
during the analysis phase.

The cache is shared with sec_fetch.py -- once warmed, the synchronous
pipeline reads from cache with zero network requests.

Usage:
    # Warm cache for specific CIKs
    python cache_warmer.py --cik-list 91388 1123661 313927

    # Warm cache for CIKs from a file
    python cache_warmer.py --cik-file output/secmap_target_ciks.txt

    # Warm cache for all adversarial-nation CIKs (name-based)
    python cache_warmer.py --all-adversarial

    # Warm cache for XBRL-identified CIKs
    python cache_warmer.py --xbrl-search CN --xbrl-dir data/SEC/aqfsn

    # Control concurrency (default 8, SEC allows ~10/sec)
    python cache_warmer.py --cik-list 91388 --concurrent 6
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from secmap.sec_fetch_async import async_warm_cache
from secmap.sec_universe import SECUniverse

FORM_TYPES = ["10-K", "20-F", "SC 13D", "SC 13G", "SC 13D/A", "SC 13G/A"]
MAX_FILINGS = 50


def main():
    parser = argparse.ArgumentParser(
        description="SECMap Cache Warmer -- pre-fetch SEC filings for zero-latency analysis",
    )
    parser.add_argument("--cik-list", nargs="+", help="CIKs to warm")
    parser.add_argument("--cik-file", help="File with one CIK per line")
    parser.add_argument("--all-adversarial", action="store_true",
                        help="Warm all adversarial-nation CIKs (name-based search)")
    parser.add_argument("--xbrl-search", help="Warm CIKs matching XBRL country code")
    parser.add_argument("--xbrl-dir", default="", help="XBRL data directory")
    parser.add_argument("--concurrent", type=int, default=8,
                        help="Max concurrent requests (default 8, SEC limit ~10/sec)")
    parser.add_argument("--max-filings", type=int, default=MAX_FILINGS,
                        help=f"Max filings per CIK to cache (default {MAX_FILINGS})")
    parser.add_argument("--forms", nargs="+", default=FORM_TYPES,
                        help="Filing form types to cache")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logger = logging.getLogger("cache_warmer")

    # Determine target CIKs
    ciks = []

    if args.cik_list:
        ciks = [c.strip() for c in args.cik_list]
    elif args.cik_file:
        with open(args.cik_file, "r") as f:
            ciks = [line.strip() for line in f if line.strip()]
    elif args.all_adversarial:
        from secmap.adversarial_search import all_countries, expand_search
        universe = SECUniverse()
        universe.load()
        seen = set()
        for country in all_countries():
            for term in expand_search(country):
                for c in universe.search(term):
                    if c.cik not in seen:
                        seen.add(c.cik)
                        ciks.append(c.cik)

        # XBRL enrichment
        if args.xbrl_dir and os.path.isdir(args.xbrl_dir):
            from secmap.xbrl_sub import XBRLSubIndex
            from secmap.adversarial_xbrl import ADVERSARIAL_CODES
            idx = XBRLSubIndex()
            idx.load_all_months(args.xbrl_dir)
            for code in ADVERSARIAL_CODES:
                for r in idx.by_country(code):
                    if r.cik not in seen:
                        seen.add(r.cik)
                        ciks.append(r.cik)
                for r in idx.by_country_inc(code):
                    if r.cik not in seen:
                        seen.add(r.cik)
                        ciks.append(r.cik)
    elif args.xbrl_search:
        if not args.xbrl_dir or not os.path.isdir(args.xbrl_dir):
            print("ERROR: --xbrl-dir required for --xbrl-search")
            sys.exit(1)
        from secmap.xbrl_sub import XBRLSubIndex
        idx = XBRLSubIndex()
        idx.load_all_months(args.xbrl_dir)
        code = args.xbrl_search.upper()
        seen = set()
        for r in idx.by_country(code):
            if r.cik not in seen:
                seen.add(r.cik)
                ciks.append(r.cik)
        for r in idx.by_country_inc(code):
            if r.cik not in seen:
                seen.add(r.cik)
                ciks.append(r.cik)
    else:
        parser.print_help()
        sys.exit(1)

    logger.info("Cache warming %d CIKs, %d forms/CIK, concurrency=%d",
                len(ciks), args.max_filings, args.concurrent)

    start = time.time()
    stats = asyncio.run(async_warm_cache(
        ciks=ciks,
        form_types=args.forms,
        max_filings=args.max_filings,
        max_concurrent=args.concurrent,
    ))
    elapsed = time.time() - start

    total_filings = sum(stats.values())
    logger.info(
        "Done: %d CIKs, %d total filings, %.1f seconds (%.1f filings/sec)",
        len(ciks), total_filings, elapsed,
        total_filings / elapsed if elapsed > 0 else 0,
    )


if __name__ == "__main__":
    main()
