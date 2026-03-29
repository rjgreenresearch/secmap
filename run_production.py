"""
run_production.py

Production batch runner for SECMap.

Runs the full SECMap pipeline against a list of target CIKs, producing:
  - Per-CIK CSV output files
  - A combined merged CSV
  - A run summary report (text)
  - Per-CIK log files

Usage:
    python run_production.py

Configuration is set in the PRODUCTION_CONFIG block below.
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from datetime import datetime
from report_generator import load_csv, analyze_rows, compute_risk_rating

# ---------------------------------------------------------------------------
# Production configuration
# ---------------------------------------------------------------------------

TARGET_CIKS = [
    "1123658",
    "1123661",
    "1350487",
    "1620087",
    "1650575",
    "313927",
    "91388",
    "898745",
    "1059213",
    "1502557",
    "1534254",
    "1593899",
    "854775",
    "940942"
]

FORM_TYPES = ["10-K", "20-F", "SC 13D", "SC 13G", "SC 13D/A", "SC 13G/A"]

MAX_DEPTH = 10         # 10 layers deep to trace full BOI lineage (exceeds USDA AFIDA limits)
MAX_FILINGS_PER_CIK = 50  # enough to capture SC-13 filings in complex multi-layered structures
MAX_TOTAL_CIKS = 100      # hard cap per root CIK to prevent exponential explosion
LOG_LEVEL = "INFO"

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
RUN_ID = datetime.utcnow().strftime("%Y%m%d_%H%M%S") + "_" + str(uuid.uuid4())[:8]
RUN_DIR = os.path.join(OUTPUT_DIR, f"run_{RUN_ID}")

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def setup_run_dir():
    os.makedirs(RUN_DIR, exist_ok=True)
    os.makedirs(os.path.join(RUN_DIR, "per_cik"), exist_ok=True)
    os.makedirs(os.path.join(RUN_DIR, "logs"), exist_ok=True)


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


# ---------------------------------------------------------------------------
# Per-CIK run
# ---------------------------------------------------------------------------

def run_cik(cik: str) -> dict:
    from secmap.ownership_mapper import run_secmap
    from secmap.csv_writer import write_edges_to_csv
    from secmap.metadata import generate_run_metadata

    logger = logging.getLogger(f"production.{cik}")
    logger.info("=" * 60)
    logger.info("Starting run for CIK %s", cik)

    out_csv = os.path.join(RUN_DIR, "per_cik", f"cik_{cik}.csv")
    cik_run_id = str(uuid.uuid4())

    result = {
        "cik": cik,
        "status": "failed",
        "edges": 0,
        "adversarial_edges": 0,
        "state_affiliated_edges": 0,
        "obscuring_role_edges": 0,
        "adversarial_jurisdictions": [],
        "output_file": out_csv,
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
            run_id=cik_run_id,
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

        cs = metadata.chain_summary
        result.update({
            "status": "ok",
            "edges": len(secmap_result.edges),
            "filings_processed": secmap_result.filings_processed,
            "visited_ciks": len(secmap_result.visited_ciks),
            "adversarial_edges": cs.adversarial_edges if cs else 0,
            "conduit_edges": cs.conduit_edges if cs else 0,
            "opacity_edges": cs.opacity_edges if cs else 0,
            "state_affiliated_edges": cs.state_affiliated_edges if cs else 0,
            "obscuring_role_edges": cs.obscuring_role_edges if cs else 0,
            "adversarial_jurisdictions": cs.adversarial_jurisdictions if cs else [],
            "unique_jurisdictions": cs.unique_jurisdictions if cs else [],
            "max_chain_depth": cs.max_chain_depth if cs else 0,
        })

        logger.info(
            "CIK %s complete: %d edges | %d adversarial | %d state-affiliated | adversarial jurisdictions: %s",
            cik,
            result["edges"],
            result["adversarial_edges"],
            result["state_affiliated_edges"],
            result["adversarial_jurisdictions"] or "none",
        )

    except Exception as e:
        result["error"] = str(e)
        logger.error("CIK %s FAILED: %s", cik, e, exc_info=True)

    return result


# ---------------------------------------------------------------------------
# Risk-flag CSV files
# ---------------------------------------------------------------------------

def flag_single_result(r: dict):
    """Flag a single CIK result immediately after processing."""
    logger = logging.getLogger("production.flag")

    if r["status"] != "ok" or not os.path.exists(r["output_file"]):
        return

    try:
        rows = load_csv(r["output_file"])
        if not rows:
            r["risk_rating"] = "LOW"
            r["risk_score"] = 0
            return

        summary = analyze_rows(rows)
        rating, score, reasons = compute_risk_rating(summary)

        r["risk_rating"] = rating
        r["risk_score"] = score
        r["risk_reasons"] = reasons
        r["company_name"] = sorted(summary["company_names"])[0] if summary["company_names"] else f"CIK {r['cik']}"
        r["critical_sectors"] = summary.get("critical_sectors", [])

        # Rename file with risk prefix
        old_path = r["output_file"]
        dirname = os.path.dirname(old_path)
        old_name = os.path.basename(old_path)
        new_name = f"{rating}_{old_name}"
        new_path = os.path.join(dirname, new_name)

        os.rename(old_path, new_path)
        r["output_file"] = new_path

        logger.info("CIK %s -> %s (score %d): %s", r["cik"], rating, score, new_name)

    except Exception as e:
        logger.error("Failed to flag CIK %s: %s", r["cik"], e)
        r["risk_rating"] = "UNKNOWN"
        r["risk_score"] = 0


# ---------------------------------------------------------------------------
# Triage manifest
# ---------------------------------------------------------------------------

def write_triage_manifest(results: list[dict]):
    """Write a prioritized triage manifest sorted by risk score."""
    logger = logging.getLogger("production.triage")
    manifest_path = os.path.join(RUN_DIR, "TRIAGE_MANIFEST.md")

    # Sort by risk score descending
    scored = [r for r in results if r["status"] == "ok"]
    scored.sort(key=lambda r: r.get("risk_score", 0), reverse=True)

    emoji = {"CRITICAL": "\U0001f534", "HIGH": "\U0001f7e0", "ELEVATED": "\U0001f7e1",
             "MODERATE": "\U0001f535", "LOW": "\U0001f7e2", "UNKNOWN": "\u26aa"}

    lines = [
        "# SECMap Triage Manifest",
        "",
        "> **Author:** Robert J. Green",
        "> **Web:** [www.rjgreenresearch.org](https://www.rjgreenresearch.org)",
        "> **Email:** [robert@rjgreenresearch.org](mailto:robert@rjgreenresearch.org)",
        "> **ORCID:** [0009-0002-9097-1021](https://orcid.org/0009-0002-9097-1021)",
        "> **SSRN:** [https://ssrn.com/author=10825096](https://ssrn.com/author=10825096)",
        "",
        f"Run ID: {RUN_ID}",
        f"Generated: {datetime.utcnow().isoformat()} UTC",
        f"CIKs processed: {len(scored)}",
        "",
        "---",
        "",
        "## Priority Queue",
        "",
        "| Priority | Rating | Score | CIK | Company | Sectors | Adversarial Jurisdictions | File |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for i, r in enumerate(scored, 1):
        rating = r.get("risk_rating", "UNKNOWN")
        e = emoji.get(rating, "")
        score = r.get("risk_score", 0)
        name = r.get("company_name", f"CIK {r['cik']}")
        sectors = ", ".join(r.get("critical_sectors", [])) or ""
        adv = ", ".join(r.get("adversarial_jurisdictions", [])) or ""
        fname = os.path.basename(r.get("output_file", ""))
        lines.append(f"| {i} | {e} **{rating}** | {score} | {r['cik']} | {name} | {sectors} | {adv} | `{fname}` |")

    # Summary counts
    counts = {}
    for r in scored:
        rating = r.get("risk_rating", "UNKNOWN")
        counts[rating] = counts.get(rating, 0) + 1

    lines += [
        "",
        "---",
        "",
        "## Summary",
        "",
        "| Rating | Count |",
        "|---|---|",
    ]
    for rating in ["CRITICAL", "HIGH", "ELEVATED", "MODERATE", "LOW"]:
        if rating in counts:
            e = emoji.get(rating, "")
            lines.append(f"| {e} **{rating}** | {counts[rating]} |")

    failed = [r for r in results if r["status"] != "ok"]
    if failed:
        lines += [
            "",
            "---",
            "",
            "## Failed CIKs",
            "",
        ]
        for r in failed:
            lines.append(f"- CIK {r['cik']}: {r.get('error', 'unknown error')}")

    lines += [
        "",
        "---",
        "",
        "*Triage manifest generated by SECMap Production Runner*",
    ]

    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    logger.info("Triage manifest written: %s", manifest_path)
    return manifest_path


# ---------------------------------------------------------------------------
# Combined CSV
# ---------------------------------------------------------------------------

def merge_outputs(results: list[dict]):
    """Concatenate all per-CIK CSVs into a single combined output."""
    combined_path = os.path.join(RUN_DIR, "combined.csv")
    logger = logging.getLogger("production.merge")

    with open(combined_path, "w", encoding="utf-8") as out:
        out.write(f"# SECMap Combined Production Run\n")
        out.write(f"# Run ID: {RUN_ID}\n")
        out.write(f"# Generated: {datetime.utcnow().isoformat()} UTC\n")
        out.write(f"# CIKs: {', '.join(TARGET_CIKS)}\n")
        out.write("#\n")

        header_written = False
        for r in results:
            if r["status"] != "ok" or not os.path.exists(r["output_file"]):
                continue
            with open(r["output_file"], "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("#"):
                        continue
                    if not header_written:
                        out.write(line)  # column header
                        header_written = True
                    elif "|" in line:
                        out.write(line)

    logger.info("Combined output written: %s", combined_path)
    return combined_path


# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------

def write_summary(results: list[dict], combined_path: str):
    summary_path = os.path.join(RUN_DIR, "summary.txt")
    logger = logging.getLogger("production.summary")

    total_edges = sum(r.get("edges", 0) for r in results)
    total_adversarial = sum(r.get("adversarial_edges", 0) for r in results)
    total_state = sum(r.get("state_affiliated_edges", 0) for r in results)
    total_obscuring = sum(r.get("obscuring_role_edges", 0) for r in results)
    all_adv_jurs = sorted(set(
        j for r in results for j in r.get("adversarial_jurisdictions", [])
    ))
    failed = [r["cik"] for r in results if r["status"] != "ok"]

    lines = [
        "=" * 70,
        "SECMap Production Run Summary",
        "=" * 70,
        f"Run ID          : {RUN_ID}",
        f"Timestamp (UTC) : {datetime.utcnow().isoformat()}",
        f"Target CIKs     : {', '.join(TARGET_CIKS)}",
        f"Form Types      : {', '.join(FORM_TYPES)}",
        f"Max Depth       : {MAX_DEPTH}",
        f"Max Filings/CIK : {MAX_FILINGS_PER_CIK}",
        "",
        "-" * 70,
        "Per-CIK Results",
        "-" * 70,
    ]

    for r in results:
        status_str = "OK" if r["status"] == "ok" else f"FAILED: {r.get('error', '')}"
        lines.append(f"\nCIK {r['cik']}  [{status_str}]")
        if r["status"] == "ok":
            lines.append(f"  Filings processed   : {r.get('filings_processed', 0)}")
            lines.append(f"  CIKs visited        : {r.get('visited_ciks', 0)}")
            lines.append(f"  Total edges         : {r.get('edges', 0)}")
            lines.append(f"  Adversarial edges   : {r.get('adversarial_edges', 0)}")
            lines.append(f"  Conduit edges       : {r.get('conduit_edges', 0)}")
            lines.append(f"  Opacity edges       : {r.get('opacity_edges', 0)}")
            lines.append(f"  State-affiliated    : {r.get('state_affiliated_edges', 0)}")
            lines.append(f"  Obscuring roles     : {r.get('obscuring_role_edges', 0)}")
            lines.append(f"  Max chain depth     : {r.get('max_chain_depth', 0)}")
            lines.append(f"  Adversarial jurs    : {', '.join(r.get('adversarial_jurisdictions', [])) or 'none'}")
            lines.append(f"  All jurisdictions   : {', '.join(r.get('unique_jurisdictions', [])) or 'none'}")
            lines.append(f"  Output              : {r['output_file']}")

    lines += [
        "",
        "=" * 70,
        "Aggregate Totals",
        "=" * 70,
        f"Total edges             : {total_edges}",
        f"Total adversarial edges : {total_adversarial}",
        f"Total state-affiliated  : {total_state}",
        f"Total obscuring roles   : {total_obscuring}",
        f"Adversarial jurisdictions found: {', '.join(all_adv_jurs) or 'none'}",
        f"Failed CIKs             : {', '.join(failed) or 'none'}",
        "",
        f"Combined output         : {combined_path}",
        f"Run directory           : {RUN_DIR}",
        "=" * 70,
    ]

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    for line in lines:
        logger.info(line)

    return summary_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    setup_run_dir()
    setup_logging(os.path.join(RUN_DIR, "logs", "production.log"))

    logger = logging.getLogger("production")
    logger.info("SECMap Production Run starting")
    logger.info("Run ID  : %s", RUN_ID)
    logger.info("Run dir : %s", RUN_DIR)
    logger.info("CIKs    : %s", ", ".join(TARGET_CIKS))

    results = []
    for cik in TARGET_CIKS:
        result = run_cik(cik)
        # Flag immediately so partial runs still get risk prefixes
        flag_single_result(result)
        results.append(result)

    # Write triage manifest
    triage_path = write_triage_manifest(results)

    combined_path = merge_outputs(results)
    summary_path = write_summary(results, combined_path)

    failed = [r["cik"] for r in results if r["status"] != "ok"]
    if failed:
        logger.warning("Production run completed with failures: %s", ", ".join(failed))
        sys.exit(1)
    else:
        logger.info("Production run completed successfully.")
        sys.exit(0)


if __name__ == "__main__":
    main()
