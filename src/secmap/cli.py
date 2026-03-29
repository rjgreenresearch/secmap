"""
cli.py

Hardened command-line interface for SECMap.

Enhancements:
- Deterministic argument parsing
- Structured logging
- Clear error codes
- Full exception safety
"""

from __future__ import annotations

import argparse
import logging
import sys

from .ownership_mapper import run_secmap
from .csv_writer import write_edges_to_csv


def configure_logging(level: str):
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="secmap",
        description="SECMap — Ownership & Governance Mapping Tool",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    run_cmd = sub.add_parser("run", help="Run SECMap pipeline")

    run_cmd.add_argument("--cik", required=True, help="Root CIK to analyze")
    run_cmd.add_argument("--forms", nargs="+", required=True, help="Form types (e.g., 10-K 10-Q SC13D)")
    run_cmd.add_argument("--depth", type=int, required=True, help="Max recursion depth")
    run_cmd.add_argument("--limit", type=int, required=True, help="Max filings per CIK")
    run_cmd.add_argument("--out", required=True, help="Output CSV path")

    run_cmd.add_argument("--issuer-name", help="Override issuer name")
    run_cmd.add_argument("--issuer-country", help="Override issuer country")
    run_cmd.add_argument("--log-level", default="INFO", help="Logging level")
    run_cmd.add_argument("--log-file", help="Optional log file path")

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    configure_logging(args.log_level)


    if args.command == "run":
        try:
            result = run_secmap(
                root_cik=args.cik,
                form_types=args.forms,
                max_depth=args.depth,
                max_filings_per_cik=args.limit,
                issuer_name_override=args.issuer_name,
                issuer_country_override=args.issuer_country,
            )
        except Exception as e:
            logging.critical("SECMap failed during discovery: %s", e)
            return 2

        try:
            write_edges_to_csv(
                edges=result.edges,
                output_path=args.out,
                root_cik=result.root_cik,
            )
        except Exception as e:
            logging.critical("Failed to write CSV output: %s", e)
            return 3

        logging.info(
            "SECMap completed successfully: %d edges written",
            len(result.edges),
        )
        return 0

    return 1
