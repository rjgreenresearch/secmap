"""
run_research.py

Research-scale SECMap runner for systematic beneficial ownership mapping
across the entire SEC filing universe.

Supports:
  - Full exchange scans (NYSE, Nasdaq, OTC)
  - Filtered subsets (by name pattern, ticker list, CIK list)
  - Resumable runs (skips already-completed CIKs)
  - Progress tracking and ETA estimation
  - Per-CIK and combined output

Usage:
    # Scan all NYSE-listed companies
    python run_research.py --exchange NYSE

    # Scan all OTC companies (where opacity is highest)
    python run_research.py --exchange OTC

    # Scan specific CIKs from a file
    python run_research.py --cik-file target_ciks.txt

    # Scan companies matching a name pattern
    python run_research.py --search "china"

    # XBRL structured country code search (zero false positives)
    python run_research.py --xbrl-search CN --xbrl-dir data/SEC/aqfsn

    # All adversarial nations via XBRL country codes
    python run_research.py --all-adversarial-xbrl --xbrl-dir data/SEC/aqfsn

    # Combined: name search + XBRL enrichment
    python run_research.py --search "china" --xbrl-dir data/SEC/aqfsn

    # Resume a previous run
    python run_research.py --exchange NYSE --resume run_20260327_research_NYSE
"""

from __future__ import annotations

import argparse
import gc
import json
import logging
import os
import sys
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from secmap.sec_universe import SECUniverse
from secmap.ownership_mapper import run_secmap
from secmap.csv_writer import write_edges_to_csv
from secmap.metadata import generate_run_metadata
from report_generator import load_csv, analyze_rows, compute_risk_rating
from secmap.adversarial_search import is_country_keyword, expand_search, expand_search_by_category

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FORM_TYPES = ["10-K", "20-F", "SC 13D", "SC 13G", "SC 13D/A", "SC 13G/A"]
MAX_DEPTH = 10
MAX_FILINGS_PER_CIK = 50
LOG_LEVEL = "INFO"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "research")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def setup_logging(log_path: str):
    numeric = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(numeric)
    for h in list(root.handlers):
        root.removeHandler(h)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    console = logging.StreamHandler()
    console.setLevel(numeric)
    console.setFormatter(fmt)
    root.addHandler(console)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(numeric)
    fh.setFormatter(fmt)
    root.addHandler(fh)


def load_completed_ciks(run_dir: str) -> set:
    """Load CIKs that have already been processed (for resume)."""
    completed = set()
    per_cik_dir = os.path.join(run_dir, "per_cik")
    if os.path.exists(per_cik_dir):
        for f in os.listdir(per_cik_dir):
            if not f.endswith(".csv"):
                continue
            # Strip risk prefix if present (CRITICAL_cik_91388.csv -> 91388)
            name = f.replace(".csv", "")
            for prefix in ["CRITICAL_", "HIGH_", "ELEVATED_", "MODERATE_", "LOW_", "UNKNOWN_"]:
                name = name.replace(prefix, "")
            name = name.replace("cik_", "")
            if name:
                path = os.path.join(per_cik_dir, f)
                with open(path, "r", encoding="utf-8") as fh:
                    lines = [l for l in fh if not l.startswith("#") and "|" in l]
                    if len(lines) > 1:
                        completed.add(name)
    return completed


def process_cik(cik: str, name: str, run_dir: str) -> dict:
    """Process a single CIK and return result summary."""
    logger = logging.getLogger("research")
    out_csv = os.path.join(run_dir, "per_cik", f"cik_{cik}.csv")

    result = {
        "cik": cik,
        "name": name,
        "status": "failed",
        "edges": 0,
        "error": None,
    }

    try:
        secmap_result = run_secmap(
            root_cik=cik,
            form_types=FORM_TYPES,
            max_depth=MAX_DEPTH,
            max_filings_per_cik=MAX_FILINGS_PER_CIK,
        )

        metadata = generate_run_metadata(
            root_cik=cik,
            form_types=FORM_TYPES,
            max_depth=MAX_DEPTH,
            max_filings_per_cik=MAX_FILINGS_PER_CIK,
            visited_ciks=secmap_result.visited_ciks,
            filings_processed=secmap_result.filings_processed,
            run_id=str(uuid.uuid4())[:8],
            edges=secmap_result.edges,
        )

        with open(out_csv, "w", encoding="utf-8") as f:
            for line in metadata.to_header_lines():
                f.write(line + "\n")
            f.write("#\n")

        write_edges_to_csv(
            edges=secmap_result.edges,
            output_path=out_csv,
            root_cik=secmap_result.root_cik,
        )

        result.update({
            "status": "ok",
            "edges": len(secmap_result.edges),
            "filings": secmap_result.filings_processed,
            "visited_ciks": len(secmap_result.visited_ciks),
            "output_file": out_csv,
        })

        logger.info(
            "CIK %s (%s): %d edges from %d filings",
            cik, name, result["edges"], result.get("filings", 0),
        )

        # Explicitly free the large objects before returning
        del secmap_result
        del metadata

    except Exception as e:
        result["error"] = str(e)
        logger.error("CIK %s (%s) FAILED: %s", cik, name, e)

    return result

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="SECMap Research-Scale Runner -- systematic BOI mapping across SEC universe",
    )
    parser.add_argument("--exchange", help="Scan all CIKs on this exchange (NYSE, Nasdaq, OTC)")
    parser.add_argument("--search", help="Scan companies matching this name pattern")
    parser.add_argument("--cik-file", help="File with one CIK per line")
    parser.add_argument("--cik-list", nargs="+", help="Explicit list of CIKs")
    parser.add_argument("--limit", type=int, default=0, help="Max CIKs to process (0=all)")
    parser.add_argument("--resume", metavar="RUN_DIR",
                        help="Resume a previous run (pass the run directory name, e.g. 20260401_013958_all_adversarial)")
    parser.add_argument("--run-name", help="Custom run directory name")
    parser.add_argument("--all-adversarial", action="store_true",
                        help="Scan all PASS Act adversarial nations in sequence")
    # XBRL structured search options
    parser.add_argument("--xbrl-search",
                        help="Search by ISO 3166-1 country code in XBRL SUB data (e.g. CN, RU, IR)")
    parser.add_argument("--xbrl-dir", default="",
                        help="Directory containing XBRL quarterly/monthly data")
    parser.add_argument("--xbrl-field", default="any",
                        choices=["countryba", "countryinc", "countryma", "any"],
                        help="Which XBRL country field to search (default: any)")
    parser.add_argument("--all-adversarial-xbrl", action="store_true",
                        help="Search all adversarial nations via XBRL country codes")
    parser.add_argument("--workers", type=int, default=1,
                        help="Parallel worker processes for CIK processing (default 1)")
    parser.add_argument("--warm-cache", action="store_true",
                        help="Pre-fetch all filings into cache before processing (async)")
    parser.add_argument("--xbrl-prefilter", action="store_true",
                        help="Skip CIKs not present in XBRL SUB data (requires --xbrl-dir)")

    args = parser.parse_args()

    # Load SEC universe
    universe = SECUniverse()
    universe.load()

    # Determine target CIKs
    targets = []
    deferred_logs = []  # Messages generated before logger is initialized
    expansion_report = None

    if args.exchange:
        companies = universe.by_exchange(args.exchange)
        targets = [(c.cik, c.name) for c in companies]
        run_label = f"exchange_{args.exchange}"
    elif args.search:
        keyword = args.search.strip()

        if is_country_keyword(keyword):
            # Adversarial-nation expansion: auto-expand into all search strategies
            categories = expand_search_by_category(keyword)
            all_terms = expand_search(keyword)

            deferred_logs.append("=" * 60)
            deferred_logs.append("ADVERSARIAL-NATION SEARCH EXPANSION")
            deferred_logs.append(f"  Keyword: '{keyword}'")
            deferred_logs.append(f"  Expanded to {len(all_terms)} search terms across {len(categories)} categories:")
            for cat, terms in categories.items():
                suffix = f" (+{len(terms)-6} more)" if len(terms) > 6 else ""
                deferred_logs.append(f"    {cat}: {', '.join(terms[:6])}{suffix}")
            deferred_logs.append("=" * 60)

            # Run all search terms, deduplicate by CIK
            seen_ciks = set()
            targets = []
            match_sources = {}  # CIK -> list of (term, category) that matched

            for cat, terms in categories.items():
                for term in terms:
                    hits = universe.search(term)
                    for c in hits:
                        if c.cik not in seen_ciks:
                            seen_ciks.add(c.cik)
                            targets.append((c.cik, c.name))
                            match_sources[c.cik] = []
                        match_sources[c.cik].append((term, cat))

            # Log discovery summary
            deferred_logs.append(f"Discovery results: {len(targets)} unique CIKs from {len(all_terms)} search terms")
            for cat, terms in categories.items():
                cat_ciks = set()
                for term in terms:
                    for c in universe.search(term):
                        cat_ciks.add(c.cik)
                deferred_logs.append(f"  {cat}: {len(cat_ciks)} unique CIKs")

            # Save expansion manifest
            expansion_report = {
                "keyword": keyword,
                "total_terms": len(all_terms),
                "categories": {cat: terms for cat, terms in categories.items()},
                "unique_ciks_found": len(targets),
                "match_sources": {
                    cik: [{"term": t, "category": c} for t, c in sources]
                    for cik, sources in match_sources.items()
                },
                "targets": [
                    {"cik": cik, "name": name,
                     "matched_by": [t for t, c in match_sources.get(cik, [])]}
                    for cik, name in targets
                ],
            }

            run_label = f"search_{keyword.replace(' ', '_')}"

        else:
            # Standard single-keyword search (unchanged behavior)
            companies = universe.search(keyword)
            targets = [(c.cik, c.name) for c in companies]
            run_label = f"search_{keyword.replace(' ', '_')}"
    elif args.cik_file:
        with open(args.cik_file, "r") as f:
            ciks = [line.strip() for line in f if line.strip()]
        targets = [(cik, universe.by_cik(cik).name if universe.by_cik(cik) else f"CIK {cik}") for cik in ciks]
        run_label = f"file_{os.path.basename(args.cik_file)}"
    elif args.cik_list:
        targets = [(cik, universe.by_cik(cik).name if universe.by_cik(cik) else f"CIK {cik}") for cik in args.cik_list]
        run_label = "custom"
    elif args.all_adversarial:
        from secmap.adversarial_search import all_countries, expand_search, expand_search_by_category

        seen_ciks = set()
        targets = []
        match_sources = {}
        nation_counts = {}

        for country in all_countries():
            for cat, terms in expand_search_by_category(country).items():
                for term in terms:
                    hits = universe.search(term)
                    for c in hits:
                        if c.cik not in seen_ciks:
                            seen_ciks.add(c.cik)
                            targets.append((c.cik, c.name))
                            match_sources[c.cik] = []
                        match_sources[c.cik].append((term, cat, country))

            nation_ciks = sum(1 for cik, sources in match_sources.items()
                              if any(s[2] == country for s in sources))
            nation_counts[country] = nation_ciks

        deferred_logs.append(f"All-adversarial scan: {len(targets)} unique CIKs across {len(nation_counts)} nations")
        for country, count in sorted(nation_counts.items(), key=lambda x: -x[1]):
            deferred_logs.append(f"  {country.upper()}: {count} CIKs")

        # Tier 3: XBRL enrichment for --all-adversarial
        if args.xbrl_dir and os.path.isdir(args.xbrl_dir):
            from secmap.xbrl_sub import XBRLSubIndex
            from secmap.adversarial_xbrl import ADVERSARIAL_CODES

            deferred_logs.append("XBRL Tier 3 enrichment for all-adversarial scan...")
            sub_index = XBRLSubIndex()
            sub_index.load_all_months(args.xbrl_dir)

            existing_ciks = {cik for cik, _ in targets}
            xbrl_added = 0
            for code in ADVERSARIAL_CODES:
                xbrl_ciks = set()
                for r in sub_index.by_country(code):
                    xbrl_ciks.add(r.cik)
                for r in sub_index.by_country_inc(code):
                    xbrl_ciks.add(r.cik)
                for recs in sub_index._by_cik.values():
                    for r in recs:
                        if r.countryma == code:
                            xbrl_ciks.add(r.cik)
                new_ciks = xbrl_ciks - existing_ciks
                for cik in sorted(new_ciks):
                    best = max(sub_index.by_cik(cik), key=lambda r: r.filed or "")
                    targets.append((cik, best.name))
                    existing_ciks.add(cik)
                    xbrl_added += 1

            deferred_logs.append(f"  XBRL added {xbrl_added} CIKs not found by name search (total now {len(targets)})")

        run_label = "all_adversarial"

    elif args.xbrl_search or args.all_adversarial_xbrl:
        # ---------------------------------------------------------------
        # XBRL structured country code search
        # ---------------------------------------------------------------
        xbrl_dir = args.xbrl_dir
        if not xbrl_dir or not os.path.isdir(xbrl_dir):
            print(f"ERROR: --xbrl-dir is required and must exist for XBRL search")
            sys.exit(1)

        from secmap.xbrl_sub import XBRLSubIndex
        from secmap.adversarial_xbrl import (
            ADVERSARIAL_CODES, CONDUIT_CODES, adversarial_scan,
        )

        deferred_logs.append("=" * 60)
        deferred_logs.append("XBRL STRUCTURED COUNTRY CODE SEARCH")
        deferred_logs.append(f"  Data directory: {xbrl_dir}")

        sub_index = XBRLSubIndex()
        sub_index.load_all_months(xbrl_dir)
        xbrl_stats = sub_index.stats()
        deferred_logs.append(
            f"  Loaded {xbrl_stats['total_records']:,} records, "
            f"{xbrl_stats['unique_ciks']:,} CIKs, "
            f"{xbrl_stats['periods_loaded']} periods"
        )

        if args.all_adversarial_xbrl:
            # Scan all adversarial nations
            target_codes = list(ADVERSARIAL_CODES.keys())
            deferred_logs.append(f"  Mode: all adversarial nations ({len(target_codes)} codes)")
            run_label = "all_adversarial_xbrl"
        else:
            target_codes = [args.xbrl_search.upper()]
            deferred_logs.append(f"  Mode: single country code {target_codes[0]}")
            code_name = ADVERSARIAL_CODES.get(target_codes[0],
                        CONDUIT_CODES.get(target_codes[0], target_codes[0]))
            run_label = f"xbrl_{target_codes[0]}_{code_name.replace(' ', '_')}"

        field = args.xbrl_field
        deferred_logs.append(f"  Field: {field}")

        # Collect matching CIKs
        seen_ciks = set()
        targets = []
        xbrl_match_detail = {}  # cik -> {fields, codes, name, ...}

        for code in target_codes:
            if field == "any":
                recs_ba = sub_index.by_country(code)
                recs_inc = sub_index.by_country_inc(code)
                # countryma requires iterating
                recs_ma = [r for recs in sub_index._by_cik.values()
                           for r in recs if r.countryma == code]
                all_recs = {}
                for r in recs_ba:
                    all_recs.setdefault(r.cik, {"fields": set(), "rec": r})
                    all_recs[r.cik]["fields"].add("countryba")
                for r in recs_inc:
                    all_recs.setdefault(r.cik, {"fields": set(), "rec": r})
                    all_recs[r.cik]["fields"].add("countryinc")
                for r in recs_ma:
                    all_recs.setdefault(r.cik, {"fields": set(), "rec": r})
                    all_recs[r.cik]["fields"].add("countryma")
            elif field == "countryba":
                all_recs = {r.cik: {"fields": {"countryba"}, "rec": r}
                            for r in sub_index.by_country(code)}
            elif field == "countryinc":
                all_recs = {r.cik: {"fields": {"countryinc"}, "rec": r}
                            for r in sub_index.by_country_inc(code)}
            elif field == "countryma":
                all_recs = {r.cik: {"fields": {"countryma"}, "rec": r}
                            for r in [r for recs in sub_index._by_cik.values()
                                      for r in recs if r.countryma == code]}

            for cik, info in all_recs.items():
                rec = info["rec"]
                if cik not in seen_ciks:
                    seen_ciks.add(cik)
                    # Use most recent record for this CIK
                    best = max(sub_index.by_cik(cik), key=lambda r: r.filed or "")
                    targets.append((cik, best.name))
                    xbrl_match_detail[cik] = {
                        "name": best.name,
                        "matched_code": code,
                        "matched_fields": sorted(info["fields"]),
                        "countryba": best.countryba,
                        "countryinc": best.countryinc,
                        "countryma": best.countryma,
                        "sic": best.sic,
                        "method": "xbrl_country_code",
                    }
                else:
                    # Add additional matched fields/codes
                    existing = xbrl_match_detail.get(cik, {})
                    existing_fields = set(existing.get("matched_fields", []))
                    existing_fields.update(info["fields"])
                    existing["matched_fields"] = sorted(existing_fields)

        deferred_logs.append(f"  Found {len(targets)} unique CIKs")

        # Build per-code breakdown for the log
        code_counts = {}
        for cik, detail in xbrl_match_detail.items():
            c = detail["matched_code"]
            code_counts[c] = code_counts.get(c, 0) + 1
        for c in sorted(code_counts, key=lambda x: -code_counts[x]):
            name = ADVERSARIAL_CODES.get(c, CONDUIT_CODES.get(c, c))
            deferred_logs.append(f"    {c} ({name}): {code_counts[c]} CIKs")

        # Count intermediary patterns
        intermediary_count = sum(
            1 for d in xbrl_match_detail.values()
            if d["countryba"] != d["countryinc"] and d["countryba"] and d["countryinc"]
        )
        deferred_logs.append(f"  Intermediary patterns (ba != inc): {intermediary_count}")
        deferred_logs.append("=" * 60)

        # Build expansion report
        field_breakdown = {"countryba": 0, "countryinc": 0, "countryma": 0}
        for d in xbrl_match_detail.values():
            for f in d["matched_fields"]:
                field_breakdown[f] = field_breakdown.get(f, 0) + 1

        expansion_report = {
            "method": "xbrl_country_code",
            "xbrl_dir": xbrl_dir,
            "xbrl_field": field,
            "target_codes": target_codes,
            "xbrl_stats": xbrl_stats,
            "unique_ciks_found": len(targets),
            "by_country_code": code_counts,
            "by_field": field_breakdown,
            "intermediary_patterns": intermediary_count,
            "targets": [
                {"cik": cik, "name": name, **xbrl_match_detail.get(cik, {})}
                for cik, name in targets
            ],
        }

    else:
        print("Specify --exchange, --search, --cik-file, or --cik-list")
        print(f"\nAvailable exchanges: {universe.exchanges()}")
        sys.exit(1)

    if args.limit > 0:
        targets = targets[:args.limit]

    # Setup run directory
    if args.resume:
        run_dir = args.resume if os.path.isabs(args.resume) else os.path.join(OUTPUT_DIR, args.resume)
    else:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        name = args.run_name or f"{ts}_{run_label}"
        run_dir = os.path.join(OUTPUT_DIR, name)

    os.makedirs(os.path.join(run_dir, "per_cik"), exist_ok=True)
    os.makedirs(os.path.join(run_dir, "logs"), exist_ok=True)
    setup_logging(os.path.join(run_dir, "logs", "research.log"))

    logger = logging.getLogger("research")

    # Replay deferred log messages now that logger exists
    for msg in deferred_logs:
        logger.info(msg)

    # Resume support
    completed = load_completed_ciks(run_dir) if args.resume else set()
    remaining = [(cik, name) for cik, name in targets if cik not in completed]

    # XBRL pre-filter: skip CIKs not in XBRL SUB data
    if args.xbrl_prefilter and args.xbrl_dir and os.path.isdir(args.xbrl_dir):
        from secmap.xbrl_sub import XBRLSubIndex
        logger.info("XBRL pre-filter: loading SUB index...")
        pf_index = XBRLSubIndex()
        pf_index.load_all_months(args.xbrl_dir)
        xbrl_ciks = pf_index.unique_ciks()
        before = len(remaining)
        remaining = [(cik, name) for cik, name in remaining if cik in xbrl_ciks]
        logger.info("XBRL pre-filter: %d -> %d CIKs (%d skipped, not in XBRL)",
                    before, len(remaining), before - len(remaining))
        del pf_index  # free memory

    logger.info("SECMap Research Run")
    logger.info("  Target: %s", run_label)
    logger.info("  Total CIKs: %d", len(targets))
    logger.info("  Already completed: %d", len(completed))
    logger.info("  Remaining: %d", len(remaining))
    logger.info("  Run dir: %s", run_dir)
    logger.info("  Depth: %d, Filings/CIK: %d", MAX_DEPTH, MAX_FILINGS_PER_CIK)

    # Save run manifest
    manifest = {
        "run_label": run_label,
        "total_targets": len(targets),
        "form_types": FORM_TYPES,
        "max_depth": MAX_DEPTH,
        "max_filings_per_cik": MAX_FILINGS_PER_CIK,
        "started": datetime.utcnow().isoformat(),
        "targets": [{"cik": cik, "name": name} for cik, name in targets],
    }
    with open(os.path.join(run_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    if expansion_report is not None:
        expansion_path = os.path.join(run_dir, "expansion_report.json")
        with open(expansion_path, "w", encoding="utf-8") as f:
            json.dump(expansion_report, f, indent=2)
        logger.info("Expansion report saved: %s", expansion_path)

    # ===================================================================
    # Cache warming (optional): pre-fetch all filings asynchronously
    # ===================================================================
    if args.warm_cache and remaining:
        logger.info("=" * 60)
        logger.info("CACHE WARMING: pre-fetching filings for %d CIKs", len(remaining))
        logger.info("=" * 60)
        import asyncio
        from secmap.sec_fetch_async import async_warm_cache
        warm_ciks = [cik for cik, _ in remaining]
        warm_start = time.time()
        asyncio.run(async_warm_cache(
            ciks=warm_ciks,
            form_types=FORM_TYPES,
            max_filings=MAX_FILINGS_PER_CIK,
            max_concurrent=8,
        ))
        warm_elapsed = time.time() - warm_start
        logger.info("Cache warming complete: %.1f seconds for %d CIKs", warm_elapsed, len(warm_ciks))

    # ===================================================================
    # Process CIKs
    # ===================================================================
    results = []
    start_time = time.time()
    num_workers = max(1, args.workers)

    if num_workers > 1:
        # --- Multiprocessing mode ---
        logger.info("Processing with %d parallel workers", num_workers)
        executor = ProcessPoolExecutor(max_workers=num_workers)
        try:
            future_map = {}
            for cik, name in remaining:
                future = executor.submit(process_cik, cik, name, run_dir)
                future_map[future] = (cik, name)

            for future in as_completed(future_map):
                cik, name = future_map[future]
                try:
                    result = future.result()
                except Exception as e:
                    result = {"cik": cik, "name": name, "status": "failed",
                              "edges": 0, "error": str(e)}

                done = len(results) + 1
                elapsed = time.time() - start_time
                rate = (done / elapsed * 3600) if elapsed > 0 else 0
                eta_hours = ((len(remaining) - done) / rate) if rate > 0 else 0
                logger.info(
                    "[%d/%d] CIK %s (%s): %s (%d edges) -- %.0f/hr, ETA %.1fh",
                    done, len(remaining), cik, name[:30],
                    result.get("status", "?"), result.get("edges", 0),
                    rate, eta_hours,
                )

                # Flag immediately
                if result.get("status") == "ok" and os.path.exists(result.get("output_file", "")):
                    try:
                        rows = load_csv(result["output_file"])
                        if rows:
                            summary = analyze_rows(rows)
                            rating, score, _ = compute_risk_rating(summary)
                            result["risk_rating"] = rating
                            result["risk_score"] = score
                            old_path = result["output_file"]
                            new_name = f"{rating}_{os.path.basename(old_path)}"
                            new_path = os.path.join(os.path.dirname(old_path), new_name)
                            os.rename(old_path, new_path)
                            logger.info("  -> %s (score %d)", rating, score)
                        del rows, summary
                    except Exception as e:
                        logger.error("  Failed to flag: %s", e)

                results.append({
                    "cik": result["cik"], "name": result["name"],
                    "status": result["status"], "edges": result.get("edges", 0),
                    "risk_rating": result.get("risk_rating", ""),
                    "error": result.get("error"),
                })
                if done % 10 == 0:
                    gc.collect()
        except KeyboardInterrupt:
            logger.warning("KeyboardInterrupt -- shutting down workers...")
            executor.shutdown(wait=False, cancel_futures=True)
            logger.info("Workers shut down. %d CIKs completed before interrupt.", len(results))
        finally:
            executor.shutdown(wait=True)
    else:
        # --- Single-process mode ---
        for i, (cik, name) in enumerate(remaining):
            elapsed = time.time() - start_time
            rate = (i / elapsed * 3600) if elapsed > 0 and i > 0 else 0
            eta_hours = ((len(remaining) - i) / rate) if rate > 0 else 0

            logger.info(
                "[%d/%d] CIK %s (%s) -- %.0f CIKs/hr, ETA %.1f hrs",
                i + 1, len(remaining), cik, name[:40], rate, eta_hours,
            )

            result = process_cik(cik, name, run_dir)

            if result["status"] == "ok" and os.path.exists(result.get("output_file", "")):
                try:
                    rows = load_csv(result["output_file"])
                    if rows:
                        summary = analyze_rows(rows)
                        rating, score, _ = compute_risk_rating(summary)
                        result["risk_rating"] = rating
                        result["risk_score"] = score
                        old_path = result["output_file"]
                        new_name = f"{rating}_{os.path.basename(old_path)}"
                        new_path = os.path.join(os.path.dirname(old_path), new_name)
                        os.rename(old_path, new_path)
                        result["output_file"] = new_path
                        logger.info("  -> %s (score %d)", rating, score)
                    del rows, summary
                except Exception as e:
                    logger.error("  Failed to flag: %s", e)

            results.append({
                "cik": result["cik"], "name": result["name"],
                "status": result["status"], "edges": result.get("edges", 0),
                "risk_rating": result.get("risk_rating", ""),
                "risk_score": result.get("risk_score", 0),
                "error": result.get("error"),
            })

            if (i + 1) % 10 == 0:
                gc.collect()

            if (i + 1) % 50 == 0:
                progress = {
                    "processed": i + 1,
                    "total": len(remaining),
                    "elapsed_hours": elapsed / 3600,
                    "rate_per_hour": rate,
                    "results": results[-50:],
                }
                with open(os.path.join(run_dir, "progress.json"), "w", encoding="utf-8") as pf:
                    json.dump(progress, pf, indent=2)

    # Final summary
    total_edges = sum(r.get("edges", 0) for r in results)
    failed = [r for r in results if r["status"] != "ok"]

    logger.info("=" * 60)
    logger.info("Research run complete")
    logger.info("  Processed: %d CIKs", len(results))
    logger.info("  Total edges: %d", total_edges)
    logger.info("  Failed: %d", len(failed))
    logger.info("  Run dir: %s", run_dir)

    # Save final results
    with open(os.path.join(run_dir, "results.json"), "w", encoding="utf-8") as f:
        json.dump({
            "completed": datetime.utcnow().isoformat(),
            "total_processed": len(results),
            "total_edges": total_edges,
            "failed_count": len(failed),
            "failed_ciks": [r["cik"] for r in failed],
            "results": results,
        }, f, indent=2)


if __name__ == "__main__":
    main()
