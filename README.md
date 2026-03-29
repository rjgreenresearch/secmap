# SECMap

**Deterministic Beneficial Ownership Chain Tracing Through SEC EDGAR Filings**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/downloads/)
[![Tests: 143](https://img.shields.io/badge/tests-143-brightgreen.svg)]()
[![Deterministic](https://img.shields.io/badge/output-deterministic-orange.svg)]()

SECMap traces beneficial ownership chains through SEC regulatory filings to their ultimate terminus — including chains that route through adversarial nations, conduit jurisdictions, and opacity havens. Given the same filings, it produces identical output, every time.

**Author:** Robert J. Green · [robert@rjgreenresearch.org](mailto:robert@rjgreenresearch.org) · [ORCID: 0009-0002-9097-1021](https://orcid.org/0009-0002-9097-1021) · [www.rjgreenresearch.org](https://www.rjgreenresearch.org)

---

## Why SECMap Exists

The USDA's Agricultural Foreign Investment Disclosure Act (AFIDA) traces foreign ownership of U.S. agricultural land to 2-3 layers. Real-world adversarial ownership structures use 7+ layers. The ChemChina → Syngenta acquisition chain runs through **seven corporate tiers** across **six jurisdictions** (China, Hong Kong, Luxembourg, Netherlands, Switzerland, United States) — using single-purpose vehicles that the SEC filing itself describes as having "not conducted any other activities or business."

AFIDA sees "Syngenta Seeds, LLC." The Chinese state-owned enterprise seven tiers above it is invisible.

SECMap was built to see through these structures. It is the primary research instrument for a PhD-track research programme on foreign agricultural ownership, spatial econometrics, and national security economics.

**Companion paper:** Green, R.J. (2026). "Spatial Clustering of Foreign Agricultural Acquisitions Near U.S. Military Installations: Comparative Evidence from USDA Primary Data." [SSRN](https://ssrn.com/author=10825096).

---

## What It Does

| Capability | Description |
|-----------|-------------|
| **Recursive CIK Discovery** | Breadth-first traversal to 10 layers of ownership depth |
| **Filing Parsing** | 10-K, 20-F, SC 13D, SC 13G, SC 13D/A, SC 13G/A, DEF 14A |
| **Person Extraction** | Positional extraction from signature blocks, age patterns, title adjacency — zero false positives from boilerplate |
| **SC 13D/G Parsing** | Cover page beneficial ownership entries with percentage stakes |
| **Jurisdiction Risk** | 5-tier classification across 135+ countries: adversarial, conduit, opacity, monitored, standard |
| **State-Actor Affiliation** | SOE, Party-controlled, military-civil fusion, sovereign wealth fund, shell/proxy, PEP — across PRC, Russia, Iran, DPRK, and others |
| **Obscuring Role Detection** | Nominee, proxy, intermediary, settlor, protector — flags layered ownership indicators |
| **State SOS Integration** | 51-jurisdiction access catalog, gap analyser comparing federal vs. state visibility |
| **Deterministic Output** | 25-column CSV with chain analysis metadata. Same input → same output, verified by test suite |

---

## Quick Start

### Installation

```bash
# Clone
git clone https://github.com/rjgreenresearch/secmap.git
cd secmap

# Install
pip install -e .

# Or with dev dependencies (tests, reporting)
pip install -e ".[dev]"
```

Requires Python 3.10+.

### Single Entity Trace

```bash
# Trace Smithfield Foods (WH Group subsidiary, largest Chinese-linked pork producer)
secmap run --cik 91388 --forms 10-K 20-F SC\ 13D SC\ 13G --depth 10 --limit 20 --out smithfield.csv

# Generate risk-rated ownership report
python report_generator.py smithfield.csv

# Generate ownership chain diagram
python network_visualizer.py smithfield.csv --cik 91388 --root "SMITHFIELD FOODS INC" --fmt pdf
```

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
├── per_cik/
│   ├── cik_91388.csv         # Smithfield Foods
│   ├── cik_1123661.csv       # Syngenta AG
│   └── ...
├── reports/
│   ├── cik_91388_report.md   # Risk-rated ownership summary
│   └── ...
└── reports_v2/               # Enhanced reports with supply chain alerts
```

### Research-Scale Exchange Scan

```bash
# Scan all OTC-listed companies (highest opacity risk)
python run_research.py --exchange OTC

# Search for China-related filers
python run_research.py --search "china"
```

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
| `relationship` | person_role, institution_role, beneficial_owner, incorporated_in, country_association |
| `role` | Specific role (CEO, Director, beneficial owner, etc.) |
| `role_category` | executive, board, ownership, filing, obscuring |
| `state_affiliation_category` | SOE, SWF, MCF, Party, UFWD, Shell-Proxy, PEP, or blank |
| `state_affiliation_detail` | Specific match (e.g., "Matched PRC SOE keywords: china national") |
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
│  │  │ Graphviz + PyVis │         │  + supply chain alert │  │  │
│  │  └─────────────────┘         └───────────────────────┘  │  │
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
| `sec_fetch.py` | 277 | SEC EDGAR HTTP client with rate limiting, retry, and disk cache |
| `cik_discovery.py` | 220 | Breadth-first recursive CIK traversal to depth 10 |
| `parse_filings.py` | 271 | HTML/XBRL stripping, text normalisation, section extraction |
| `ownership_mapper.py` | 246 | Top-level pipeline orchestrator |
| `people_extractor.py` | 236 | Positional person extraction from structural filing locations |
| `institution_extractor.py` | 132 | Corporate entity extraction using suffix patterns |
| `sc13_parser.py` | 217 | SC 13D/G cover page parsing for beneficial ownership |
| `jurisdiction_inference.py` | 411 | 5-tier jurisdiction risk classification (135+ countries) |
| `state_affiliation.py` | 438 | Multi-nation state-actor affiliation detection |
| `role_taxonomy.py` | 344 | 50+ role categories with semantic flags |
| `entity_classification.py` | 123 | Person/company/institution/government classification |
| `relationship_builder.py` | 164 | Edge construction and deduplication |
| `csv_writer.py` | 200 | 25-column deterministic CSV with metadata headers |
| `metadata.py` | 176 | Run metadata and chain analysis summary |
| `config.py` | 130 | Three-layer config: defaults → environment → CLI |
| `sec_universe.py` | 174 | SEC filing universe (10,447 companies, 28,183 mutual funds) |
| **Visualization & Reporting** | | |
| `report_generator.py` | 400+ | Risk-rated ownership chain summary reports (Markdown) |
| `network_visualizer.py` | 350+ | Hierarchical ownership chain diagrams (Graphviz/PyVis) |
| **State SOS Integration** | | |
| `state_sos/state_registry.py` | 317 | 51-jurisdiction access catalog |
| `state_sos/gap_analyzer.py` | 286 | Federal/state visibility gap analysis |
| `state_sos/texas_sos.py` | 171 | Texas SOS PDF parser |

### Visualization & Reporting

SECMap includes two output tools that consume the pipeline's CSV artifacts:

| Tool | Purpose |
|------|---------|
| `report_generator.py` | Generates per-CIK ownership chain summary reports in Markdown. Each report includes an overall risk rating (CRITICAL / HIGH / ELEVATED / MODERATE / LOW), supply chain vulnerability assessment with SIC-to-critical-sector mapping, AFIDA depth comparison, complete beneficial owner and institutional relationship listings, state-actor affiliation findings, key personnel organised by role, obscuring-role flags, jurisdiction risk distribution, and temporal filing coverage. |
| `network_visualizer.py` | Produces hierarchical ownership chain diagrams from per-CIK CSVs. Supports Graphviz (PDF/SVG/PNG) output with pagination, typed node colouring (company/person/country), and legend. Also generates PyVis interactive HTML graphs at configurable depth levels for browser-based exploration. |

#### Report Generator

```bash
# Single entity report
python report_generator.py output/run_XXXX/per_cik/cik_91388.csv

# Batch — all CIKs in a run
python report_generator.py output/run_XXXX/per_cik/

# Custom output directory
python report_generator.py output/run_XXXX/per_cik/ --out reports/
```

Example output (Smithfield Foods, CIK 91388):

```
## Overall Risk Rating: CRITICAL (score: 75/100)

- Adversarial-nation jurisdictions detected: China, Russia
- 2 state-actor affiliated entity(ies)
- Conduit jurisdictions: Hong Kong
- Critical sector(s): Agriculture & Food

## Supply Chain Vulnerability Assessment
⚠ SUPPLY CHAIN ALERT: This entity operates in Agriculture & Food
and has ownership chain exposure to China, Russia.
```

#### Network Visualizer

```bash
# Graphviz PDF with layered depth
python network_visualizer.py output/run_XXXX/per_cik/cik_1123661.csv \
    --cik 1123661 --root "Syngenta AG" --depth1 1 --depth2 2 --fmt pdf

# Interactive HTML for browser exploration
python network_visualizer.py output/run_XXXX/per_cik/cik_91388.csv \
    --cik 91388 --root "SMITHFIELD FOODS INC" --fmt html
```

Produces colour-coded ownership chain diagrams showing:
- **Blue nodes:** Companies and institutions
- **Purple nodes:** Named individuals
- **Green nodes:** Countries and jurisdictions
- **Red edges:** Wholly-owned subsidiary chains
- **Blue edges:** Beneficial ownership claims
- **Purple edges:** Officer and director relationships

Both tools are documented in detail in [`docs/`](docs/).

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

## Example: Production Run Output

```
======================================================================
SECMap Production Run Summary
======================================================================
Target CIKs     : 1123658, 1123661, 91388, 313927, ...
Form Types      : 10-K, 20-F, SC 13D, SC 13G, SC 13D/A, SC 13G/A
Max Depth       : 10

Aggregate Totals
----------------------------------------------------------------------
Total edges             : 1,734
Total adversarial edges : 399
Total state-affiliated  : 57
Total obscuring roles   : 1
Adversarial jurisdictions found: China, Russia
======================================================================
```

---

## Testing

```bash
# Run full test suite (143 tests)
python -m pytest tests/ -v

# Run specific test categories
python -m pytest tests/test_people_extractor.py -v
python -m pytest tests/test_sc13_parser.py -v
python -m pytest tests/test_reproducibility.py -v

# Generate HTML report
python run_tests.py
```

The reproducibility test verifies that identical inputs produce identical outputs — the deterministic guarantee that makes SECMap suitable for academic citation.

---

## Air-Gapped Operation

SECMap runs entirely offline using its disk cache. After one network-connected run, all SEC data is cached locally:

```
cache/
├── data.sec.gov/submissions/    # Company metadata JSON
└── www.sec.gov/Archives/edgar/  # Filing documents
```

Subsequent runs serve from cache with zero network requests. This enables operation in air-gapped environments and eliminates SEC rate-limit concerns for iterative development.

---

## Citation

If you use SECMap in research, policy analysis, or publications, please cite:

```bibtex
@software{green_secmap_2026,
  author       = {Green, Robert J.},
  title        = {{SECMap}: Deterministic Ownership \& Governance Mapping System},
  version      = {1.1.0},
  year         = {2026},
  url          = {https://github.com/rjgreenresearch/secmap},
  license      = {Apache-2.0}
}
```

See [CITATION.cff](CITATION.cff) for machine-readable citation metadata.

---

## Research Context

SECMap is the primary research instrument for a PhD-track programme examining foreign agricultural ownership in the United States:

- **Article 1** (published): Spatial clustering of Chinese-linked holdings near military installations — 3.4× enrichment, 12.7× against nuclear-capable sites
- **Article 2** (in preparation): Ownership networks and the three-system visibility gap — 92.7% of Chinese-linked AFIDA entities invisible to federal ownership analysis
- **Article 3** (planned): CFIUS regulatory gap simulation and regression discontinuity design

The methodology was initially developed through creative practice in the novel *[Digital Harvest](https://www.digitalharvestbook.com)* (The Silent Conquest Series) and subsequently validated against federal primary-source data.

---

## License

Apache 2.0. See [LICENSE](LICENSE) for full terms.

"SECMap" is a trademark of Robert J. Green. The Apache 2.0 license includes an express patent license and patent retaliation clause.

Government agencies may use, modify, and distribute this software without fee under the terms of the Apache 2.0 license.
