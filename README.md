# SECMap

**Deterministic Beneficial Ownership Chain Tracing Through SEC EDGAR Filings**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/downloads/)
[![Tests: 258](https://img.shields.io/badge/tests-258-brightgreen.svg)]()
[![Deterministic](https://img.shields.io/badge/output-deterministic-orange.svg)]()

SECMap traces beneficial ownership chains through SEC regulatory filings to their ultimate terminus -- including chains that route through adversarial nations, conduit jurisdictions, and opacity havens. Given the same filings, it produces identical output, every time.

**Author:** Robert J. Green · [robert@rjgreenresearch.org](mailto:robert@rjgreenresearch.org) · [ORCID: 0009-0002-9097-1021](https://orcid.org/0009-0002-9097-1021) · [www.rjgreenresearch.org](https://www.rjgreenresearch.org)

---

## Why SECMap Exists

The USDA's Agricultural Foreign Investment Disclosure Act (AFIDA) traces foreign ownership of U.S. agricultural land to 2-3 layers. Real-world adversarial ownership structures use 7+ layers. The ChemChina → Syngenta acquisition chain runs through **seven corporate tiers** across **six jurisdictions** (China, Hong Kong, Luxembourg, Netherlands, Switzerland, United States) -- using single-purpose vehicles that the SEC filing itself describes as having "not conducted any other activities or business."

AFIDA sees "Syngenta Seeds, LLC." The Chinese state-owned enterprise seven tiers above it is invisible.

SECMap was built to see through these structures. It is the primary research instrument for a PhD-track research programme on foreign agricultural ownership, spatial econometrics, and national security economics.

---

## How This Tool Supports the Research

SECMap operationalises the "three-system visibility gap" -- the central finding of the companion paper (Green, 2026b). The paper argues that AFIDA sees entity names but not beneficial owners, the SEC sees parent companies but not AFIDA-registered subsidiaries, and state SOS records see everything but are siloed across 50 jurisdictions. SECMap is the system that traces ownership chains through the SEC layer, cross-references AFIDA entities against SEC registrants, catalogs state SOS access methods for the state layer, and quantifies the gap between all three.

Every empirical claim in the paper -- the 92.7% visibility gap, the seven-tier ChemChina chain, the 507,957 ownership edges, the zero SEC registrants for five PASS Act nations -- was produced by this tool running against federal primary-source data. The results are fully reproducible (see [Reproducing the Paper's Results](#reproducing-the-papers-results) below).

**Companion papers:**
- Green, R.J. (2026a). "Spatial Clustering of Foreign Agricultural Acquisitions Near U.S. Military Installations." [SSRN](https://ssrn.com/author=10825096).
- Green, R.J. (2026b). "Through the Looking Glass: The Three-System Visibility Gap in U.S. Foreign Agricultural Land Disclosure." In preparation.

---

## What It Does

| Capability | Description |
|-----------|-------------|
| **Recursive CIK Discovery** | Breadth-first traversal to 10 layers of ownership depth |
| **Filing Parsing** | 10-K, 20-F, SC 13D, SC 13G, SC 13D/A, SC 13G/A, DEF 14A |
| **Person Extraction** | Positional extraction from signature blocks, age patterns, title adjacency -- zero false positives from boilerplate |
| **SC 13D/G Parsing** | Cover page beneficial ownership entries with percentage stakes |
| **Jurisdiction Risk** | 5-tier classification across 135+ countries: adversarial, conduit, opacity, monitored, standard |
| **State-Actor Affiliation** | SOE, Party-controlled, military-civil fusion, sovereign wealth fund, shell/proxy, PEP -- across PRC, Russia, Iran, DPRK, and others |
| **Obscuring Role Detection** | Nominee, proxy, intermediary, settlor, protector -- flags layered ownership indicators |
| **AFIDA Cross-Reference** | Parses USDA AFIDA data, matches entities against SEC registrants, measures the federal visibility gap |
| **Adversarial-Nation Search** | Auto-expands country keywords into SOE names, legal suffixes, strategic companies, and city names for comprehensive SEC universe discovery |
| **XBRL Structured Search** | Zero-false-positive adversarial-nation identification using ISO 3166-1 country codes from SEC XBRL Financial Statement and Notes Data Sets (558K+ records, 2020–2026) |
| **Descension Engine** | Downward ownership traversal via XBRL co-registrant CIKs -- traces what a parent entity OWNS, complementing the ascension pipeline that traces who owns it |
| **Exhibit 21 Parsing** | Extracts subsidiary listings from 10-K Exhibit 21 documents using BeautifulSoup HTML table extraction with plain-text fallback; cross-references against XBRL SUB for CIK resolution |
| **Ownership Chain Tree** | Full hierarchical tree rendering in reports showing owners above and subsidiaries below the investigated entity, with jurisdiction and risk tier tags at each node |
| **State SOS Integration** | 51-jurisdiction access catalog, gap analyser comparing federal vs. state visibility |
| **Deterministic Output** | 25-column CSV with chain analysis metadata. Same input → same output, verified by test suite |

---

## Quick Start

### Installation

```bash
git clone https://github.com/rjgreenresearch/secmap.git
cd secmap
pip install -e .

# Or with dev dependencies (tests, reporting)
pip install -e ".[dev]"
```

Requires Python 3.10+.

### Single Entity Trace

```bash
# Trace Smithfield Foods (WH Group subsidiary, largest Chinese-linked pork producer)
secmap run --cik 91388 --forms 10-K 20-F SC\ 13D SC\ 13G --depth 10 --limit 50 --out smithfield.csv

# Generate risk-rated ownership report
python report_generator.py smithfield.csv

# Generate ownership chain diagram
python network_visualizer.py smithfield.csv --cik 91388 --root "SMITHFIELD FOODS INC" --fmt pdf
```

### AFIDA Cross-Reference

```bash
# Download required data (not included -- see Data Sources below)
# 1. AFIDA 2024 holdings: AFIDACurrentHoldingsYR2024.xlsx from USDA FSA
# 2. SEC tickers: company_tickers.json from sec.gov/files/company_tickers.json

# Cross-reference Chinese-linked AFIDA entities against SEC registrants
python afida_parser.py \
    --afida AFIDACurrentHoldingsYR2024.xlsx \
    --tickers company_tickers.json \
    --out output/

# Include Hong Kong/Macau in China filter
python afida_parser.py --afida AFIDA_2024.xlsx --tickers company_tickers.json --include-hk --out output/

# All adversarial nations (China, Russia, Iran, DPRK, Cuba, Venezuela, etc.)
python afida_parser.py --afida AFIDA_2024.xlsx --tickers company_tickers.json --all-adversarial --out output/
```

Output:
```
output/
├── afida_sec_matched.csv       # Entities with SEC CIK matches → feed to run_production.py
├── afida_unmatched.csv         # Entities with NO SEC presence → state SOS targets
├── secmap_target_ciks.txt      # CIK list -- paste directly into run_production.py
└── afida_parse_summary.txt     # Coverage statistics and top entity tables
```

The `secmap_target_ciks.txt` output drops directly into `run_production.py`'s TARGET_CIKS list. The `afida_unmatched.csv` identifies entities invisible to federal analysis -- candidates for state SOS investigation via the gap analyser.

### Production Batch

```bash
# Process all target CIKs defined in run_production.py
python run_production.py
```

Output structure:
```
output/run_YYYYMMDD_HHMMSS_HASH/
├── combined.csv              # All edges, all CIKs
├── summary.txt               # Aggregate statistics
├── TRIAGE_MANIFEST.md        # Risk-sorted priority queue
├── per_cik/
│   ├── CRITICAL_cik_91388.csv
│   ├── CRITICAL_cik_1123661.csv
│   └── ...
└── per_cik/reports/
    ├── CRITICAL_cik_91388_report.md
    ├── CRITICAL_cik_91388_summary.md
    └── ...
```

### Research-Scale Adversarial-Nation Scan

```bash
# Scan all Chinese-named SEC filers (auto-expands to SOEs, strategic companies, city names)
python run_research.py --search "china"

# Scan all PASS Act adversarial nations (name-based)
python run_research.py --all-adversarial

# Combined: name search + XBRL structured country code enrichment
python run_research.py --all-adversarial --xbrl-dir data/SEC/aqfsn

# XBRL-only: zero-false-positive search by ISO country code
python run_research.py --xbrl-search CN --xbrl-dir data/SEC/aqfsn

# All adversarial nations via XBRL country codes
python run_research.py --all-adversarial-xbrl --xbrl-dir data/SEC/aqfsn

# Filter by specific XBRL field (incorporation vs business address)
python run_research.py --xbrl-search CN --xbrl-dir data/SEC/aqfsn --xbrl-field countryinc

# Scan specific exchange (highest opacity risk)
python run_research.py --exchange OTC
```

### High-Performance Production Workflow

For large-scale runs (500+ CIKs), use the three-step workflow:

```bash
# Step 1: Warm the disk cache (async HTTP, ~50-80 filings/sec)
python cache_warmer.py --all-adversarial --xbrl-dir data/SEC/aqfsn

# Step 2: Run analysis from cache with parallel workers
python run_research.py --all-adversarial --xbrl-dir data/SEC/aqfsn \
    --workers 4 --xbrl-prefilter

# Step 3: Generate reports from output
python report_generator.py output/research/<run_dir>/per_cik/
```

| Option | Effect |
|---|---|
| `--warm-cache` | Pre-fetch all filings into disk cache using async HTTP before processing |
| `--workers N` | Process N CIKs in parallel using multiprocessing (default 1) |
| `--xbrl-prefilter` | Skip CIKs not present in XBRL SUB data (requires `--xbrl-dir`) |

SECMap uses a three-tier adversarial-nation discovery strategy:

| Tier | Method | Source | False Positive Rate |
|------|--------|--------|--------------------|
| **Tier 1** | Country name + demonym expansion | SEC company tickers | Low |
| **Tier 2** | SOE names, legal suffixes, strategic companies, city names | SEC company tickers | Low |
| **Tier 3** | ISO 3166-1 country code matching | XBRL SUB table | **Zero** |

Tier 3 uses the SEC's XBRL Financial Statement and Notes Data Sets, which contain structured country codes for business address (`countryba`), incorporation (`countryinc`), and mailing address (`countryma`). This catches entities like GAZPROM NEFT PJSC (countryba=RU) that name-based search misses entirely.

When `--xbrl-dir` is provided alongside `--all-adversarial` or `--search`, all three tiers run and results are merged by CIK. The expansion_report.json records which method discovered each CIK.

---

## The AFIDA Visibility Gap Finding

The AFIDA parser cross-references USDA AFIDA entity names against the SEC's complete company tickers database (10,447 registrants). For Chinese-linked agricultural holdings:

| Metric | Value |
|--------|-------|
| Unique Chinese-linked AFIDA entities | 82 |
| Entities with SEC filing presence | 6 (7.3%) -- all false positives on manual review |
| **Entities invisible to federal analysis** | **76-82 (92.7-100%)** |
| Invisible acreage | 246,019 acres (98.9%) |

The structural cause: **AFIDA records subsidiaries. SEC records parents.** "Murphy Brown LLC" appears in AFIDA. "Smithfield Foods Inc" appears in SEC. They are the same ownership chain. No federal system connects them.

The parser handles AFIDA's varying Excel formats (auto-detects header rows, maps all column name variants) and captures the 2024 Secondary Interest flags for China, Iran, Russia, and North Korea -- identifying entities attributed to allied countries but with adversarial-nation secondary interests.

---

## Output Schema

SECMap produces pipe-delimited CSV with 25 fields per edge:

| Field | Description |
|-------|-------------|
| `source_name` | Entity name (cleaned, normalised) |
| `source_type` | person, company, institution, government |
| `source_jurisdiction` | Inferred jurisdiction |
| `source_jurisdiction_risk` | ADVERSARIAL, CONDUIT, OPACITY, MONITORED, STANDARD |
| `target_name` | Target entity name |
| `target_type` | Entity type classification |
| `target_jurisdiction` | Inferred jurisdiction |
| `target_jurisdiction_risk` | Risk tier |
| `relationship` | person_role, institution_role, beneficial_owner, incorporated_in, country_association, consolidated_subsidiary |
| `role` | Specific role (CEO, Director, beneficial owner, etc.) |
| `role_category` | executive, board, ownership, filing, obscuring |
| `state_affiliation_category` | SOE, SWF, MCF, Party, UFWD, Shell-Proxy, PEP, or blank |
| `state_affiliation_detail` | Specific match detail |
| `ownership_pct` | Percentage ownership (from SC 13D/G, where available) |
| `chain_depth` | Depth in the recursive CIK traversal |
| `company_cik` | Root CIK for this edge |
| `filing_accession` | SEC EDGAR accession number (provenance) |
| `filing_form` | 10-K, 20-F, SC 13D, etc. |
| `filing_date` | Filing date |
| `extraction_method` | How the edge was extracted |

Plus metadata fields for deduplication, timestamps, and notes.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        SECMap Pipeline                          │
│                                                                 │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌────────────┐  │
│  │   SEC    │   │  Filing  │   │ Entity   │   │ Ownership  │  │
│  │  Fetch   │──▶│  Parse   │──▶│ Extract  │──▶│   Edges    │  │
│  │ + Cache  │   │ + Strip  │   │ + Class  │   │  + Dedup   │  │
│  └──────────┘   └──────────┘   └──────────┘   └─────┬──────┘  │
│       │                                              │         │
│       ▼                                              ▼         │
│  ┌──────────┐                                 ┌────────────┐   │
│  │   CIK    │                                 │    CSV     │   │
│  │Discovery │◀─── recursive ──────────────────│   Writer   │   │
│  │  (BFS)   │     up to depth 10              │  + Meta    │   │
│  └──────────┘                                 └─────┬──────┘   │
│                                                      │         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Classification & Risk Scoring               │  │
│  │  ┌────────────┐  ┌──────────────┐  ┌─────────────────┐  │  │
│  │  │Jurisdiction│  │    State     │  │      Role       │  │  │
│  │  │ Inference  │  │ Affiliation  │  │    Taxonomy     │  │  │
│  │  │ 5 tiers    │  │ PRC/RU/IR/KP │  │ 50+ roles      │  │  │
│  │  └────────────┘  └──────────────┘  └─────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                      │         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │               Visualization & Reporting                  │  │
│  │  ┌─────────────────┐         ┌───────────────────────┐  │  │
│  │  │    Network       │         │   Report Generator    │  │  │
│  │  │   Visualizer     │         │  Risk-rated Markdown  │  │  │
│  │  │ Graphviz + PyVis │         │  + ownership tree     │  │  │
│  │  └─────────────────┘         └───────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  XBRL Integration                         │  │
│  │  ┌────────────┐  ┌──────────────┐  ┌─────────────────┐  │  │
│  │  │  XBRL SUB  │  │  Descension  │  │   Exhibit 21    │  │  │
│  │  │   Parser   │  │   Engine     │  │    Parser       │  │  │
│  │  │ 558K recs  │  │ co-registrant│  │  BeautifulSoup  │  │  │
│  │  └────────────┘  └──────────────┘  └─────────────────┘  │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  Adversarial XBRL Scan -- ISO country code search   │  │  │
│  │  │  Zero false positives across 3 country fields      │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  AFIDA Integration                        │  │
│  │  ┌────────────┐  ┌──────────────┐  ┌─────────────────┐  │  │
│  │  │   AFIDA    │  │ Adversarial  │  │   Visibility    │  │  │
│  │  │   Parser   │  │   Search     │  │ Gap Measurement │  │  │
│  │  │ Excel/CSV  │  │  Expansion   │  │  92.7-100%      │  │  │
│  │  └────────────┘  └──────────────┘  └─────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  State SOS Integration                    │  │
│  │  ┌────────────┐  ┌──────────────┐  ┌─────────────────┐  │  │
│  │  │   State    │  │     Gap      │  │   Texas SOS     │  │  │
│  │  │  Registry  │  │   Analyzer   │  │   PDF Parser    │  │  │
│  │  │ 51 states  │  │ Fed vs State │  │                 │  │  │
│  │  └────────────┘  └──────────────┘  └─────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Module Reference

| Module | Lines | Purpose |
|--------|-------|---------|
| **Core Pipeline** | | |
| `sec_fetch.py` | 277 | SEC EDGAR HTTP client with rate limiting, retry, and disk cache |
| `sec_fetch_async.py` | 150+ | Async HTTP fetcher (aiohttp) for concurrent SEC requests with shared disk cache |
| `cik_discovery.py` | 220 | Breadth-first recursive CIK traversal to depth 10 |
| `parse_filings.py` | 271 | HTML/XBRL stripping, text normalisation, section extraction |
| `ownership_mapper.py` | 246 | Top-level pipeline orchestrator |
| `people_extractor.py` | 236 | Positional person extraction from structural filing locations |
| `institution_extractor.py` | 132 | Corporate entity extraction using suffix patterns |
| `sc13_parser.py` | 217 | SC 13D/G cover page parsing for beneficial ownership |
| `csv_writer.py` | 200 | 25-column deterministic CSV with metadata headers |
| `metadata.py` | 176 | Run metadata and chain analysis summary |
| `config.py` | 130 | Three-layer config: defaults → environment → CLI |
| **Classification & Risk** | | |
| `jurisdiction_inference.py` | 411 | 5-tier jurisdiction risk classification (135+ countries) |
| `state_affiliation.py` | 438 | Multi-nation state-actor affiliation detection |
| `role_taxonomy.py` | 344 | 50+ role categories with semantic flags |
| `entity_classification.py` | 123 | Person/company/institution/government classification |
| `relationship_builder.py` | 164 | Edge construction and deduplication |
| **Visualization & Reporting** | | |
| `report_generator.py` | 400+ | Risk-rated ownership chain summary reports (Markdown) |
| `network_visualizer.py` | 350+ | Hierarchical ownership chain diagrams (Graphviz/PyVis) |
| **AFIDA & Research** | | |
| `afida_parser.py` | 500+ | AFIDA-to-SEC cross-reference and visibility gap measurement |
| `adversarial_search.py` | 440+ | Country keyword expansion for adversarial-nation SEC universe search |
| `sec_universe.py` | 174 | SEC filing universe (10,447 companies, 28,183 mutual funds) |
| **XBRL Integration** | | |
| `xbrl_sub.py` | 280+ | XBRL SUB table parser -- 558K records, 11.4K CIKs, 34 periods (2020q1–2026) |
| `descension.py` | 250+ | Downward ownership traversal via co-registrant CIKs |
| `exhibit21_parser.py` | 350+ | Exhibit 21 subsidiary listing parser (BeautifulSoup + regex fallback) |
| `adversarial_xbrl.py` | 300+ | Zero-false-positive adversarial scan using ISO 3166-1 country codes |
| **State SOS Integration** | | |
| `state_sos/state_registry.py` | 317 | 51-jurisdiction access catalog |
| `state_sos/gap_analyzer.py` | 286 | Federal/state visibility gap analysis |
| `state_sos/texas_sos.py` | 171 | Texas SOS PDF parser |

### Visualization & Reporting

| Tool | Purpose |
|------|---------|
| `report_generator.py` | Generates per-CIK dual reports: executive summary (`_summary.md`) and detailed analysis (`_report.md`). Includes risk rating (CRITICAL / HIGH / ELEVATED / MODERATE / LOW), ownership chain tree showing full hierarchy with investigated entity positioned in context, supply chain vulnerability assessment with SIC-to-critical-sector mapping, AFIDA depth comparison, all beneficial owners and institutional relationships, state-actor affiliation findings, key personnel by role, obscuring-role flags, jurisdiction risk distribution, and temporal filing coverage. |
| `network_visualizer.py` | Produces hierarchical ownership chain diagrams from per-CIK CSVs. Supports Graphviz (PDF/SVG/PNG) with pagination and typed node colouring (company/person/country), plus PyVis interactive HTML graphs at configurable depth levels. |

```bash
# Report generator
python report_generator.py output/run_XXXX/per_cik/cik_91388.csv           # Single entity
python report_generator.py output/run_XXXX/per_cik/                         # Batch all CIKs
python report_generator.py output/run_XXXX/per_cik/ --out reports/          # Custom output dir

# Network visualizer
python network_visualizer.py output/run_XXXX/per_cik/cik_1123661.csv \
    --cik 1123661 --root "Syngenta AG" --depth1 1 --depth2 2 --fmt pdf
```

---

## Jurisdiction Risk Tiers

| Tier | Countries (examples) | Policy Relevance |
|------|---------------------|-----------------|
| **ADVERSARIAL** | China, Russia, Iran, DPRK, Belarus, Myanmar, Cuba, Venezuela, Syria, Nicaragua | PASS Act designated nations; CFIUS mandatory review |
| **CONDUIT** | Hong Kong, Singapore, UAE, Cyprus, Turkey, Central Asian states | Common intermediary jurisdictions for adversarial-nation capital routing |
| **OPACITY** | Cayman Islands, BVI, Bermuda, Seychelles, Maldives, Panama, Liechtenstein | Secrecy jurisdictions with limited beneficial ownership disclosure |
| **MONITORED** | Taiwan, Pakistan, Saudi Arabia, FATF grey-list states | Elevated risk but not adversarial |
| **STANDARD** | US, UK, EU, Japan, Australia, Canada | Allied nations with transparent regulatory regimes |

---

## State-Actor Affiliation Detection

| Category | Examples | Nations Covered |
|----------|---------|----------------|
| **SOE** | SASAC entities, Sinopec, PetroChina, China National Chemical Corp | PRC, Russia, Iran |
| **Party-Controlled** | CCP/CPC apparatus, Propaganda Department entities | PRC |
| **MCF** | AVIC, NORINCO, CETC (military-civil fusion entities) | PRC |
| **UFWD** | Confucius Institutes, Thousand Talents-linked entities | PRC |
| **SWF** | GIC (Singapore), ADIA (Abu Dhabi), CIC (China) | Global |
| **Shell-Proxy** | Nominee directors, registered agent-only entities | Any jurisdiction |
| **PEP** | Politically exposed persons | Global |

---

## State SOS Integration

SECMap catalogs access methods for all 50 states + DC:

| Tier | Count | States |
|------|-------|--------|
| **API** (free programmatic) | 9 | CA, CO, CT, DE, MA, MI, OR, PA, WA |
| **Bulk Download** (free CSV) | 21 | AK, FL, GA, IA, IL, IN, KS, MD, MN, MO, NC, NE, NH, NJ, OH, OK, SC, TN, UT, VA, WI |
| **Web Scrape** (free, scraping required) | 20 | AL, AR, AZ, DC, HI, ID, KY, LA, ME, MS, MT, ND, NM, NV, NY, RI, SD, VT, WV, WY |
| **Paywall** | 1 | TX ($1/page, cold storage, hours-to-days delivery) |

The gap analyser compares SEC ownership chains against state entity registrations, risk-scoring entities visible at the state level but invisible to federal databases.

---

## Testing

```bash
# Run full test suite (258 tests)
python -m pytest tests/ -v

# Run specific test categories
python -m pytest tests/test_people_extractor.py -v
python -m pytest tests/test_sc13_parser.py -v
python -m pytest tests/test_reproducibility.py -v

# Generate HTML report
python run_tests.py
```

The test suite includes three categories of quality assurance tests that serve distinct purposes:

| Test | Purpose | Academic Relevance |
|------|---------|-------------------|
| **Golden Regression** (`test_golden_regression.py`) | Validates that a known synthetic input produces CSV output with correct entity names, relationship types, ownership percentages, accession numbers, and column structure | Proves the tool produces **correct output** for a known case -- citable in methodology sections |
| **Integration** (`test_integration_end_to_end.py`, `test_integration_sc13.py`) | Validates that pipeline modules are correctly wired -- parsers called, edge builders invoked, CSV files created with expected edge counts | Proves the **pipeline is connected** end-to-end without gaps |
| **Reproducibility** (`test_reproducibility.py`) | Validates that identical inputs produce byte-for-byte identical CSV output across two independent runs | Proves **deterministic output** -- the guarantee that makes SECMap suitable for academic citation and peer review |

Additional test coverage includes unit tests for all core modules (XBRL SUB parser, descension engine, Exhibit 21 parser, jurisdiction inference, state affiliation detection, role taxonomy, people/institution extraction, SC 13D/G parsing, CSV writer, CIK discovery, and configuration).

---

## Air-Gapped Operation & Cache Architecture

SECMap runs entirely offline using its disk cache. After one network-connected run (or a cache warming pass), all SEC data is cached locally:

```
cache/
  data.sec.gov/submissions/    # Company metadata JSON
  www.sec.gov/Archives/edgar/  # Filing documents
```

Subsequent runs serve from cache with zero network requests. This enables operation in air-gapped environments and eliminates SEC rate-limit concerns for iterative development.

The `cache_warmer.py` script pre-populates the cache using async HTTP (~50-80 filings/second vs ~6/second synchronous):

```bash
# Warm cache for all adversarial-nation CIKs
python cache_warmer.py --all-adversarial --xbrl-dir data/SEC/aqfsn

# Warm cache for specific CIKs
python cache_warmer.py --cik-list 91388 1123661 313927

# Warm cache for XBRL-identified Chinese entities
python cache_warmer.py --xbrl-search CN --xbrl-dir data/SEC/aqfsn
```

The async fetcher and synchronous pipeline share the same cache directory. Once warmed, the analysis pipeline reads from cache with zero network latency, and multiprocessing (`--workers 4`) can process CIKs in parallel without SEC rate-limit contention.

---

## Known Limitations

SECMap is a research instrument, not a comprehensive surveillance system. These limitations are documented here because transparency about boundaries increases credibility.

| Limitation | Impact | Mitigation |
|-----------|--------|-----------|
| **SEC-only primary visibility** | Private entities (LLCs, LPs, trusts) that don't file with the SEC are invisible to the core pipeline | AFIDA parser identifies the gap; state SOS integration addresses it for individual states |
| **Descension requires XBRL data** | Downward ownership traversal (what an entity owns) requires XBRL AQFSN data files, which are not included in the repository | Download quarterly/monthly AQFSN ZIPs from SEC EDGAR; the descension engine loads them automatically |
| **No access to FinCEN CTA database** | The Corporate Transparency Act beneficial ownership database is not publicly accessible | CTA-AFIDA integration is a policy recommendation, not a technical capability |
| **State SOS integration is catalog-only** | Automated retrieval implemented for Texas PDF only; other states require manual data collection | State registry catalogs all 51 jurisdictions with access method, cost, and latency |
| **BFS traversal capped at 100 CIKs per target** | Very large ownership networks may not be fully explored | Configurable via `max_depth` and CIK visit limits |
| **Jurisdiction inference is heuristic-based** | Country assignment from entity names may occasionally be incorrect | Conservative defaults; adversarial/conduit classifications are manually reviewable |
| **SC 13D/G percentage extraction is best-effort** | Ownership percentages from unstructured filing text may be imprecise | Values are flagged with extraction method for audit |
| **AFIDA fuzzy matching produces false positives** | Name-based cross-reference at 0.80 threshold matches unrelated entities | Manual verification required; all matches include confidence scores |
| **County-level spatial resolution** | AFIDA reports county, not parcel coordinates; centroid error is ±10-35 miles depending on county size | Enrichment ratios remain valid (error is symmetric); absolute distances reported at 100-mile threshold where error is <20%; sub-county parcel geolocation planned |

---

## Reproducing the Paper's Results

To reproduce the findings in Green (2026b), "Through the Looking Glass":

### The 92.7% Visibility Gap (Section 4)

```bash
# Download AFIDA 2024 data from fsa.usda.gov
# Download company_tickers.json from sec.gov/files/company_tickers.json

python afida_parser.py \
    --afida AFIDACurrentHoldingsYR2024.xlsx \
    --tickers company_tickers.json \
    --out output/

# Expected output: 82 unique entities, 6 fuzzy matches (all false positives),
# 76 unmatched (92.7%), 248,775 total acres
```

### The 507,957-Edge Production Run (Section 3.5)

```bash
# Ensure TARGET_CIKS in run_production.py contains these 14 CIKs:
# 91388, 313927, 854775, 898745, 940942, 1059213, 1123658, 1123661,
# 1350487, 1502557, 1534254, 1593899, 1620087, 1650575

python run_production.py

# Expected output: 507,957 edges, 7,462 adversarial edges,
# 9,463 state-affiliated entities, 1,753 obscuring roles,
# 12 CRITICAL ratings, adversarial jurisdictions: Belarus, China, Cuba, Iran, Russia
```

### The Comparative Adversarial-Nation Analysis (Section 7)

```bash
python run_research.py --search "china"
# Expected: 24 Chinese-named registrants, 705,915 edges

python run_research.py --search "russia"
# Expected: 0 registrants (with country-name search only)

python run_research.py --search "iran"
# Expected: 0 registrants

python run_research.py --all-adversarial
# Expected: ~84 registrants across all adversarial nations (with expanded search)
```

### Configuration

| Parameter | Value |
|-----------|-------|
| Form types | 10-K, 20-F, SC 13D, SC 13G, SC 13D/A, SC 13G/A |
| Max depth | 10 |
| Max filings per CIK | 50 |
| BFS CIK visit limit | 100 per target |
| AFIDA fuzzy match threshold | 0.80 |

---

## Data Sources

Data files are **not included** in this repository. Users download directly from authoritative government sources:

| Data | Source | URL |
|------|--------|-----|
| AFIDA Holdings (2024) | USDA Farm Service Agency | fsa.usda.gov/resources/economic-policy-analysis/afida |
| SEC Company Tickers | SEC EDGAR | sec.gov/files/company_tickers.json |
| SEC XBRL AQFSN Data Sets | SEC EDGAR | sec.gov/data-research/sec-markets-data/financial-statement-notes-data-sets |
| SEC XBRL Quarterly Notes | SEC EDGAR | sec.gov/dera/data/financial-statement-and-notes-data-set |
| County Centroids | NOAA | weather.gov/gis/Counties |

---

## Citation

If you use SECMap in research, policy analysis, or publications, please cite:

```bibtex
@software{green_secmap_2026,
  author       = {Green, Robert J.},
  title        = {{SECMap}: Deterministic Ownership \& Governance Mapping System},
  version      = {2.0.0},
  year         = {2026},
  url          = {https://github.com/rjgreenresearch/secmap},
  license      = {Apache-2.0}
}
```

See [CITATION.cff](CITATION.cff) for machine-readable citation metadata.

---

## Research Context

SECMap is the primary research instrument for a PhD-track programme examining foreign agricultural ownership in the United States:

- **Article 1** (published): Spatial clustering of Chinese-linked holdings near military installations -- 3.4× enrichment, 12.7× against nuclear-capable sites
- **Article 2** (in preparation): Ownership networks and the three-system visibility gap -- 92.7% of Chinese-linked AFIDA entities invisible to federal ownership analysis
- **Article 3** (planned): CFIUS regulatory gap simulation and regression discontinuity design

The companion repository [**afida-spatial-analysis**](https://github.com/rjgreenresearch/afida-spatial-analysis) contains the Monte Carlo permutation testing framework for Article 1.

The methodology was initially developed through creative practice in the novel *[Digital Harvest](https://www.digitalharvestbook.com)* (The Silent Conquest Series) and subsequently validated against federal primary-source data.

---

## License

Apache 2.0. See [LICENSE](LICENSE) for full terms.

"SECMap" is a trademark of Robert J. Green. The Apache 2.0 license includes an express patent license and patent retaliation clause.

Government agencies may use, modify, and distribute this software without fee under the terms of the Apache 2.0 license.
