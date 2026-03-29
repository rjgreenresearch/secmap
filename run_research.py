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

    # Resume a previous run
    python run_research.py --exchange NYSE --resume run_20260327_research_NYSE
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from secmap.sec_universe import SECUniverse
from secmap.ownership_mapper import run_secmap
from secmap.csv_writer import write_edges_to_csv
from secmap.metadata import generate_run_metadata
from report_generator import load_csv, analyze_rows, compute_risk_rating

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
    logger = logging.getLogger(f"research.{cik}")
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
        })

        logger.info(
            "CIK %s (%s): %d edges from %d filings",
            cik, name, result["edges"], result.get("filings", 0),
        )

    except Exception as e:
        result["error"] = str(e)
        logger.error("CIK %s (%s) FAILED: %s", cik, name, e)

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="SECMap Research-Scale Runner — systematic BOI mapping across SEC universe",
    )
    parser.add_argument("--exchange", help="Scan all CIKs on this exchange (NYSE, Nasdaq, OTC)")
    parser.add_argument("--search", help="Scan companies matching this name pattern")
    parser.add_argument("--cik-file", help="File with one CIK per line")
    parser.add_argument("--cik-list", nargs="+", help="Explicit list of CIKs")
    parser.add_argument("--limit", type=int, default=0, help="Max CIKs to process (0=all)")
    parser.add_argument("--resume", help="Resume a previous run directory")
    parser.add_argument("--run-name", help="Custom run directory name")
    args = parser.parse_args()

    # Load SEC universe
    universe = SECUniverse()
    universe.load()

    # Determine target CIKs
    targets = []

    if args.exchange:
        companies = universe.by_exchange(args.exchange)
        targets = [(c.cik, c.name) for c in companies]
        run_label = f"exchange_{args.exchange}"
    elif args.search:
        companies = universe.search(args.search)
        targets = [(c.cik, c.name) for c in companies]
        run_label = f"search_{args.search.replace(' ', '_')}"
    elif args.cik_file:
        with open(args.cik_file, "r") as f:
            ciks = [line.strip() for line in f if line.strip()]
        targets = [(cik, universe.by_cik(cik).name if universe.by_cik(cik) else f"CIK {cik}") for cik in ciks]
        run_label = f"file_{os.path.basename(args.cik_file)}"
    elif args.cik_list:
        targets = [(cik, universe.by_cik(cik).name if universe.by_cik(cik) else f"CIK {cik}") for cik in args.cik_list]
        run_label = "custom"
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

    # Resume support
    completed = load_completed_ciks(run_dir) if args.resume else set()
    remaining = [(cik, name) for cik, name in targets if cik not in completed]

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

    # Process
    results = []
    start_time = time.time()

    for i, (cik, name) in enumerate(remaining):
        elapsed = time.time() - start_time
        rate = (i / elapsed * 3600) if elapsed > 0 and i > 0 else 0
        eta_hours = ((len(remaining) - i) / rate) if rate > 0 else 0

        logger.info(
            "[%d/%d] CIK %s (%s) — %.0f CIKs/hr, ETA %.1f hrs",
            i + 1, len(remaining), cik, name[:40], rate, eta_hours,
        )

        result = process_cik(cik, name, run_dir)

        # Flag immediately so partial runs still get risk prefixes
        if result["status"] == "ok" and os.path.exists(result.get("output_file", "")):
            try:
                rows = load_csv(result["output_file"])
                if rows:
                    summary = analyze_rows(rows)
                    rating, score, reasons = compute_risk_rating(summary)
                    result["risk_rating"] = rating
                    result["risk_score"] = score
                    result["company_name"] = sorted(summary["company_names"])[0] if summary["company_names"] else name
                    result["critical_sectors"] = summary.get("critical_sectors", [])
                    result["adversarial_jurisdictions"] = sorted(summary.get("adversarial_jurisdictions", set()))
                    old_path = result["output_file"]
                    new_name = f"{rating}_{os.path.basename(old_path)}"
                    new_path = os.path.join(os.path.dirname(old_path), new_name)
                    os.rename(old_path, new_path)
                    result["output_file"] = new_path
                    logger.info("  -> %s (score %d)", rating, score)
            except Exception as e:
                logger.error("  Failed to flag: %s", e)

        results.append(result)

        # Save progress periodically
        if (i + 1) % 50 == 0:
            progress = {
                "processed": i + 1,
                "total": len(remaining),
                "elapsed_hours": elapsed / 3600,
                "rate_per_hour": rate,
                "results": results[-50:],
            }
            with open(os.path.join(run_dir, "progress.json"), "w", encoding="utf-8") as f:
                json.dump(progress, f, indent=2)

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
