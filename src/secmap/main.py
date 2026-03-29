"""
main.py

CLI entrypoint for the SECMap application.

Responsibilities:
- Parse command-line arguments
- Initialize logging
- Run the SECMap orchestrator
- Generate run metadata
- Write CSV output
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import uuid
from typing import List

from .ownership_mapper import run_secmap
from .csv_writer import write_edges_to_csv
from .metadata import generate_run_metadata


def setup_logging(verbosity: int) -> None:
    level = logging.INFO
    if verbosity >= 2:
        level = logging.DEBUG
    elif verbosity <= 0:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SECMap: SEC ownership and governance mapper"
    )

    parser.add_argument(
        "root_cik",
        help="Root CIK to start mapping from (numeric, with or without leading zeros)",
    )
    parser.add_argument(
        "-f", "--forms", nargs="+",
        default=["10-K", "20-F", "SC 13D", "SC 13G"],
        help="Form types to include (default: 10-K 20-F SC 13D SC 13G)",
    )
    parser.add_argument(
        "-d", "--max-depth", type=int, default=2,
        help="Maximum recursion depth for CIK discovery (default: 2)",
    )
    parser.add_argument(
        "-n", "--max-filings-per-cik", type=int, default=10,
        help="Maximum number of filings per CIK to process (default: 10)",
    )
    parser.add_argument(
        "-o", "--output", required=True,
        help="Output CSV file path",
    )
    parser.add_argument("--issuer-name", default=None, help="Optional issuer name override")
    parser.add_argument("--issuer-country", default=None, help="Optional issuer country override")
    parser.add_argument(
        "-v", "--verbose", action="count", default=1,
        help="Increase verbosity (-v for INFO, -vv for DEBUG)",
    )

    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    args = parse_args(argv)
    setup_logging(args.verbose)

    logger = logging.getLogger(__name__)
    logger.info("Starting SECMap CLI")

    root_cik = args.root_cik
    form_types = args.forms
    max_depth = args.max_depth
    max_filings_per_cik = args.max_filings_per_cik
    output_path = args.output
    issuer_name = args.issuer_name
    issuer_country = args.issuer_country

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    run_id = str(uuid.uuid4())
    logger.info(
        "Run ID: %s | Root CIK: %s | Forms: %s | Depth: %d | Max filings/CIK: %d",
        run_id, root_cik, form_types, max_depth, max_filings_per_cik,
    )

    result = run_secmap(
        root_cik=root_cik,
        form_types=form_types,
        max_depth=max_depth,
        max_filings_per_cik=max_filings_per_cik,
        issuer_name_override=issuer_name,
        issuer_country_override=issuer_country,
    )

    metadata = generate_run_metadata(
        root_cik=root_cik,
        form_types=form_types,
        max_depth=max_depth,
        max_filings_per_cik=max_filings_per_cik,
        visited_ciks=result.visited_ciks,
        filings_processed=result.filings_processed,
        run_id=run_id,
        edges=result.edges,
    )

    logger.info("Writing CSV output to %s", output_path)

    with open(output_path, "w", encoding="utf-8") as f:
        for line in metadata.to_header_lines():
            f.write(line + "\n")
        f.write("#\n")

    write_edges_to_csv(
        edges=result.edges,
        output_path=output_path,
        root_cik=result.root_cik,
    )

    logger.info("SECMap run complete. Output: %s", output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
