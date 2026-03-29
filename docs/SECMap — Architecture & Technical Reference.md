# SECMap — Architecture & Technical Reference

> **Author:** Robert J. Green
> **Web:** [www.rjgreenresearch.org](https://www.rjgreenresearch.org)
> **Email:** [robert@rjgreenresearch.org](mailto:robert@rjgreenresearch.org)
> **ORCID:** [0009-0002-9097-1021](https://orcid.org/0009-0002-9097-1021)
> **SSRN:** [https://ssrn.com/author=10825096](https://ssrn.com/author=10825096)


**Deterministic Beneficial Ownership & Governance Mapping System**

Version 1.1.0 · March 2026
PhD Economics (Econometrics) Research Instrument

---

## 1. Purpose

SECMap is a research-grade system for tracing beneficial ownership chains through SEC EDGAR filings to their ultimate terminus — including chains that route through multiple layers of corporate structure across adversarial nations, conduit jurisdictions, and opacity havens.

The system was designed to address three specific failures in the current U.S. regulatory framework:

1. **USDA AFIDA depth limitation** — The Agricultural Foreign Investment Disclosure Act relies on self-reporting and typically traces ownership to 2–3 layers. Real-world adversarial ownership structures (e.g., Syngenta AG) use 7+ layers, rendering AFIDA determinations inadequate.

2. **SEC EDGAR scope limitation** — SEC filings cover public companies and their direct filers, but ownership chains frequently terminate in private entities (LLCs, LPs, trusts) registered at the state level that are invisible to federal databases.

3. **Federal/state visibility gap** — State Secretary of State business entity records cover ALL entities including private ones, but these records are siloed across 50 separate systems with no federal aggregation. Adversarial nations exploit this gap by routing ownership through state-registered private vehicles.

SECMap traces ownership chains to a depth of 10 layers, classifies every entity and jurisdiction by risk tier, and bridges the federal/state gap through systematic state SOS integration.

---

## 2. System Architecture

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
│  └──────────┘                                 └────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Classification & Risk Scoring               │  │
│  │  ┌────────────┐  ┌──────────────┐  ┌─────────────────┐  │  │
│  │  │Jurisdiction│  │    State     │  │      Role       │  │  │
│  │  │ Inference  │  │ Affiliation  │  │    Taxonomy     │  │  │
│  │  │ + Risk Tier│  │ PRC/RU/IR/KP │  │ + Deputy roles  │  │  │
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

---

## 3. Module Reference

### 3.1 Core Pipeline

| Module | Purpose |
|---|---|
| `sec_fetch.py` | SEC EDGAR HTTP client with rate limiting, retry logic, and disk-based caching. Fetches company submissions JSON from `data.sec.gov` and filing documents from `www.sec.gov`. Cache eliminates redundant SEC hits across runs. |
| `cik_discovery.py` | Breadth-first recursive CIK discovery. Starting from a root CIK, fetches filings, extracts referenced CIKs, and recurses up to depth 10. Collects company metadata (name, SIC, state of incorporation) per CIK. |
| `parse_filings.py` | HTML/XBRL stripping, text normalization, and section extraction (signature blocks, narrative sections, country mentions). Converts raw filing content into structured text blocks. |
| `ownership_mapper.py` | Top-level orchestrator. Runs the full pipeline: discovery → parse → extract → edge construction → deduplication. Builds `incorporated_in` edges from company metadata. Returns a structured result with edges and company info. |
| `csv_writer.py` | Writes pipe-delimited CSV with 25 columns including jurisdiction, risk tier, state affiliation, role flags, and chain depth. Includes metadata header block. |
| `metadata.py` | Run metadata and chain analysis summary. Computes aggregate statistics: adversarial/conduit/opacity edge counts, state-affiliated entities, obscuring roles, max chain depth. |
| `config.py` | Three-layer configuration: defaults → environment variables → CLI overrides. Validates all parameters including max depth ceiling of 10. |
| `cli.py` | Command-line interface for single-CIK runs. |
| `main.py` | Alternative CLI entrypoint with metadata header prepending. |

### 3.2 Entity Extraction

| Module | Purpose |
|---|---|
| `people_extractor.py` | **Positional extraction** of person names from SEC filings. Only extracts from structural locations: `/s/` signature blocks, `By:` patterns, `Name, age XX` patterns, and title-adjacent patterns. Uses lookahead for title keywords to handle HTML-stripped concatenated text (e.g., `/s/ C. Shane SmithChief Executive Officer`). Zero false positives from filing boilerplate. |
| `institution_extractor.py` | Extracts institution/company names using corporate suffix patterns (LLC, Inc, Corp, Ltd, etc.). Length-capped at 80 characters with sentence-fragment rejection. |
| `entity_classification.py` | Entity type classification (person, company, institution, government) using keyword heuristics and name pattern analysis. |
| `entity_extraction.py` | Lower-level entity extraction with org-keyword detection and person name cleaning. |
| `sc13_parser.py` | Parses SC 13D/G cover page structure to extract beneficial ownership entries. Handles the repeating cover page format where each reporting person gets their own page with numbered fields. Skips IRS ID lines, share counts, and fund source codes. Validates extracted names against noise patterns. |

### 3.3 Classification & Risk Scoring

| Module | Purpose |
|---|---|
| `jurisdiction_inference.py` | Maps entity names and filing context to jurisdictions. **Five risk tiers**: ADVERSARIAL (China, Russia, Iran, DPRK, Belarus, Myanmar, Syria, Cuba, Venezuela, Nicaragua), CONDUIT (Hong Kong, UAE, Singapore, Cyprus, Turkey, Central Asian states, Baltic states), OPACITY (Cayman Islands, BVI, Bermuda, Seychelles, Maldives, Panama, and 30+ other secrecy jurisdictions), MONITORED (Taiwan, Pakistan, Saudi Arabia, FATF grey-list states), STANDARD (US, UK, EU, Japan, Australia, allied nations). Includes city-level tokens (Beijing, Dubai, Limassol, etc.) for name-based inference. |
| `state_affiliation.py` | Classifies entities by state-actor affiliation across all primary adversarial nations. **PRC**: SOE (SASAC, Sinopec, PetroChina, etc.), Party-Controlled (CCP/CPC apparatus), MCF (military-civil fusion, AVIC, NORINCO, CETC), UFWD (united front, Confucius Institutes, Thousand Talents). **Russia**: Gazprom, Rostec, Rosatom, FSB/GRU-adjacent. **Iran**: IRGC, bonyads, NIOC. **DPRK**: KOMID, Office 39, front companies. Also detects sovereign wealth funds, shell/proxy indicators, and politically exposed persons globally. |
| `role_taxonomy.py` | Classifies roles with semantic flags for chain analysis. 50+ canonical roles including C-suite, board, SEC-filing-specific (PFO, PAO, PEO), ownership (beneficial owner, controlling person, significant shareholder), and **obscuring roles** (nominee, agent, proxy, intermediary, settlor, protector) that indicate layering. Includes Deputy {X} variants common in foreign SC-13 filings. Word-boundary regex prevents false positives. |

### 3.4 SEC Universe

| Module | Purpose |
|---|---|
| `sec_universe.py` | Pulls the complete SEC filing universe from three official endpoints: `company_tickers.json` (10,447 tickers), `company_tickers_exchange.json` (10,438 companies across NYSE/Nasdaq/OTC/CBOE), `company_tickers_mf.json` (28,183 mutual fund series). Filterable by exchange, name search, or CIK. Cached to disk. |

### 3.5 State SOS Integration

| Module | Purpose |
|---|---|
| `state_sos/state_registry.py` | Catalogs the access method, endpoint URL, cost, and latency for all 50 states + DC. **9 API states** (CA, CO, CT, DE, MA, MI, OR, PA, WA), **21 bulk-download states** (FL, GA, IL, VA, etc.), **20 web-scrape states** (NY, NV, WY, SD, etc.), **1 paywall state** (TX: $1/page, cold storage, hours-to-days delivery). |
| `state_sos/gap_analyzer.py` | Compares SEC ownership chains against state SOS entity registrations. Identifies entities visible at state level but invisible to federal databases. Risk-scores gaps based on shell-structure name patterns, privacy-state registration (DE/NV/WY/SD), layering vehicle type (LP/LLC/Trust), foreign jurisdiction of formation, and commercial registered agent usage. Supports incremental ingestion and persistence for long-running research. |
| `state_sos/texas_sos.py` | PDF parser for Texas Secretary of State documents. Extracts entity name, type, status, formation date, registered agent, and officers from the PDF format Texas SOS delivers after payment. Handles ZIP archives of multiple PDFs. |

---

## 4. Data Flow

### 4.1 Single-CIK Pipeline

```
Root CIK (e.g., 1123658 = Sinopec)
    │
    ▼
fetch_company_submissions() ──▶ company name, SIC, state of incorporation
    │
    ▼
fetch_filings_for_cik() ──▶ 10-K, 20-F, SC 13D/G filings (up to 50)
    │
    ▼
For each filing:
    ├── parse_filing_to_sections() ──▶ full_text, signatures, narrative, countries
    ├── extract_people_from_signatures() ──▶ /s/ Name patterns
    ├── extract_institutions_from_narrative() ──▶ corporate suffix patterns
    ├── parse_sc13_beneficial_ownership() ──▶ reporting persons + percent
    ├── classify_role() ──▶ CEO, Director, Beneficial Owner, Nominee, etc.
    ├── infer_jurisdiction_with_risk() ──▶ country + risk tier
    ├── classify_state_affiliation() ──▶ SOE, MCF, UFWD, SWF, Shell-Proxy, PEP
    └── build edges ──▶ OwnershipEdge with all metadata
    │
    ▼
Extract CIKs from filing text ──▶ enqueue for BFS at depth+1
    │
    ▼ (recurse up to depth 10)
    │
    ▼
merge_and_deduplicate_edges()
    │
    ▼
write_edges_to_csv() ──▶ 25-column pipe-delimited CSV
```

### 4.2 Ownership Edge Schema (CSV Columns)

| Column | Description |
|---|---|
| `source` | Entity name (person, company, institution) |
| `source_type` | person, company, institution, country |
| `source_jurisdiction` | Inferred country of source entity |
| `source_risk_tier` | ADVERSARIAL, CONDUIT, OPACITY, MONITORED, STANDARD |
| `target` | Target entity name |
| `target_type` | person, company, institution, country |
| `target_jurisdiction` | Inferred country of target entity |
| `target_risk_tier` | Risk tier of target jurisdiction |
| `relationship` | person_role, institution_role, beneficial_owner, incorporated_in, country_association |
| `detail` | Role title, ownership percentage, SIC description |
| `company_name` | Resolved company name (not raw CIK) |
| `company_cik` | SEC CIK number |
| `state_affiliation` | SOE, Party-Controlled, MCF, UFWD, State-Linked, SWF, Shell-Proxy, PEP, None |
| `state_affiliation_sub` | PRC, Russia, Iran, DPRK, Belarus, etc. |
| `state_affiliation_detail` | Matched keyword or pattern |
| `role_is_executive` | Y if C-suite or senior executive |
| `role_is_board` | Y if board-level role |
| `role_is_ownership` | Y if beneficial owner, controlling person, etc. |
| `role_is_obscuring` | Y if nominee, agent, proxy, intermediary |
| `chain_depth` | BFS depth from root CIK (0 = direct) |
| `filing_accession` | SEC filing accession number |
| `filing_form` | 10-K, 20-F, SC 13D, SC 13G, etc. |
| `filing_date` | Filing date |
| `method` | Extraction method (role_extraction, sc13, company_metadata, country_extraction) |
| `notes` | Additional context |

---

## 5. Risk Tier Classification

### 5.1 Jurisdiction Risk Tiers

| Tier | Definition | Examples | Count |
|---|---|---|---|
| **ADVERSARIAL** | Nations with state-directed economic warfare, espionage, or sanctions programs targeting the US | China, Russia, Iran, North Korea, Belarus, Myanmar, Syria, Cuba, Venezuela, Nicaragua | 10 |
| **CONDUIT** | Jurisdictions frequently used as intermediate layering nodes in adversarial ownership chains | Hong Kong, Singapore, UAE, Turkey, Cyprus, Malta, Kazakhstan, Latvia, Estonia | 24 |
| **OPACITY** | Secrecy jurisdictions with weak beneficial-ownership disclosure | Cayman Islands, BVI, Bermuda, Seychelles, Maldives, Panama, Liechtenstein, Jersey | 38 |
| **MONITORED** | Partial transparency or FATF grey-list history | Taiwan, Pakistan, Saudi Arabia, Qatar, Ukraine, Cambodia, Nigeria | 26 |
| **STANDARD** | Allied or transparent jurisdictions | US, UK, Germany, Japan, Australia, Canada, South Korea | 37 |

### 5.2 State Affiliation Categories

| Category | Subcategory | Description |
|---|---|---|
| **SOE** | PRC | State-owned enterprises (SASAC, Sinopec, PetroChina, CNOOC, etc.) |
| **Party-Controlled** | PRC | CCP/CPC apparatus (party committees, discipline inspection, propaganda) |
| **MCF** | PRC | Military-civil fusion entities (AVIC, CASIC, NORINCO, CETC) |
| **UFWD** | PRC | United front work (Confucius Institutes, Thousand Talents, CPPCC) |
| **State-Linked** | Russia | Gazprom, Rostec, Rosatom, Sberbank, VTB, RDIF, FSB/GRU-adjacent |
| **State-Linked** | Iran | IRGC, bonyads, NIOC, Bank Melli, IRISL |
| **State-Linked** | DPRK | KOMID, Office 39, Korea Tangun, front companies |
| **SWF** | Global | Sovereign wealth funds (CIC, GIC, ADIA, Mubadala, QIA, PIF, Temasek) |
| **Shell-Proxy** | Global | Nominee, shell company, SPV, VIE, holding company, trust arrangement |
| **PEP** | Global | Politically exposed persons (ministers, governors, ambassadors, generals) |

---

## 6. Execution Modes

### 6.1 Single-CIK CLI

```bash
secmap run --cik 1123658 --forms 10-K SC\ 13D --depth 10 --limit 50 --out sinopec.csv
```

### 6.2 Production Batch Run

```bash
python run_production.py
```

Processes a configured list of target CIKs with per-CIK output, combined CSV, and summary report. Current configuration: 8 CIKs, depth 10, 50 filings/CIK.

After processing, each CSV file is renamed with a risk-rating prefix based on a composite score (0-100):

```
per_cik/
├── CRITICAL_cik_91388.csv      # Smithfield Foods — PRC ownership, agriculture
├── CRITICAL_cik_1123658.csv    # Sinopec — PRC SOE, petrochemicals
├── MODERATE_cik_1350487.csv    # WisdomTree — no adversarial exposure
└── LOW_cik_898745.csv          # Principal Funds — unremarkable
```

A `TRIAGE_MANIFEST.md` is generated with a priority-sorted table of all CIKs by risk score, enabling analysts to focus on CRITICAL files first and skip LOW/MODERATE noise.

### 6.3 Research-Scale Run

```bash
# All NYSE-listed companies (3,273)
python run_research.py --exchange NYSE

# All OTC companies (2,575 — highest opacity risk)
python run_research.py --exchange OTC

# China-related companies
python run_research.py --search "china"

# Resume interrupted run
python run_research.py --exchange NYSE --resume output/research/20260327_NYSE
```

Supports resumable runs, progress tracking, ETA estimation, and manifest/results JSON.

### 6.4 Report Generation

```bash
# Generate summary reports for all CIKs in a run
python report_generator.py output/run_XXXX/per_cik/

# Single file
python report_generator.py output/run_XXXX/per_cik/CRITICAL_cik_91388.csv
```

Produces per-CIK markdown reports with overall risk rating, supply chain vulnerability assessment, AFIDA depth comparison, and complete beneficial ownership / personnel / institutional tables.

### 6.5 Network Visualization

```bash
python network_visualizer.py output/run_XXXX/per_cik/cik_91388.csv
python network_visualizer.py output/run_XXXX/combined.csv --no-countries --format svg
```

Generates hierarchical ownership chain diagrams using NetworkX and Matplotlib.

---

## 7. The Federal/State Visibility Gap

### 7.1 The Problem

| System | Scope | Depth | Entity Coverage | Access |
|---|---|---|---|---|
| **SEC EDGAR** | Public companies + direct filers | 2–3 layers typical | Public only | Free, programmatic |
| **USDA AFIDA** | Agricultural foreign investment | Self-reported, 2–3 layers | Self-reported only | FOIA required |
| **State SOS** | ALL business entities | Complete | Public + private | Varies by state |

The gap between SEC/AFIDA and state SOS records is where adversarial ownership hides. A chain like:

```
SASAC (PRC State Council)
  └── China National Chemical Corp (CNAC)
       └── ChemChina Holdings
            └── CNAC Saturn (Netherlands) BV
                 └── Syngenta AG (Swiss, CIK 1123661)
                      └── Syngenta Crop Protection LLC (Delaware)
                           └── [state-registered subsidiaries]
```

...is only partially visible through SEC filings. The terminal nodes — state-registered LLCs, LPs, and trusts — are invisible to federal databases.

### 7.2 The Brazos Highland Case

Brazos Highland Properties LP, registered in Texas, was traced through Texas SOS records to Guangxin Sun — a former PLA officer who became the single largest Chinese landowner in the United States. This entity was:

- **Not in SEC EDGAR** (private LP, no SEC filing obligation)
- **Not in USDA AFIDA** (AFIDA relies on self-reporting)
- **Only discoverable through Texas SOS** (paywall access, $1/page, cold storage delivery)

SECMap's state SOS integration module catalogs access methods for all 50 states + DC and provides a gap analyzer that identifies entities visible at state level but invisible to federal databases.

### 7.3 State Access Landscape

| Access Tier | States | Method | Cost |
|---|---|---|---|
| **API** (9) | CA, CO, CT, DE, MA, MI, OR, PA, WA | Programmatic | Free |
| **Bulk** (21) | FL, GA, IL, IN, VA, NC, OH, etc. | CSV download | Free |
| **Web** (20) | NY, NV, WY, SD, AL, AZ, etc. | Scraping | Free |
| **Paywall** (1) | TX | Payment + cold storage | $1/page, hours-days |

---

## 8. Testing

143 tests covering unit, integration, regression, and reproducibility:

```bash
python run_tests.py
```

Test categories:
- Unit tests for all extractors, parsers, and classifiers
- Integration tests for the full pipeline with mocked SEC data
- Golden-file regression tests for output stability
- Reproducibility tests (identical input → identical output)
- CLI smoke tests

Reports generated in `test_reports/report.html` and `test_reports/report.md`.

---

## 9. Caching

All SEC EDGAR requests are cached to disk under `./cache/`:

```
cache/
├── data.sec.gov/submissions/    # Company submissions JSON
├── www.sec.gov/Archives/        # Filing documents
└── universe/                    # SEC ticker endpoint data
```

First run fetches from SEC. Subsequent runs use cache exclusively. Delete `./cache/` to force fresh fetches. Cache location configurable via `SECMAP_CACHE_DIR` environment variable.

---

## 10. Dependencies

| Package | Version | Purpose |
|---|---|---|
| Python | ≥ 3.10 | Runtime |
| requests | ≥ 2.31.0 | SEC EDGAR HTTP client |
| pytest | ≥ 8.0.0 | Test framework (dev) |
| pytest-html | ≥ 4.0.0 | HTML test reports (dev) |
| pytest-md | ≥ 0.2.0 | Markdown test reports (dev) |
| networkx | — | Network visualization (optional) |
| matplotlib | — | Graph rendering (optional) |
| PyPDF2 / pdfplumber | — | Texas SOS PDF parsing (optional) |

Install: `pip install -e ".[dev]"`

---

## 11. License & Citation

Apache 2.0 License. See `LICENSE` file.

If you use SECMap in research, policy analysis, or publications, cite as:

> Green, R. J. (2026). *SECMap: Deterministic Ownership & Governance Mapping System* (Version 1.1.0) [Software]. https://github.com/rjgreenresearch/secmap

See `CITATION.cff` for machine-readable citation metadata.

---

## 12. Contact

Robert J. Green
[www.rjgreenresearch.org](https://www.rjgreenresearch.org) · [robert@rjgreenresearch.org](mailto:robert@rjgreenresearch.org)
ORCID: [0009-0002-9097-1021](https://orcid.org/0009-0002-9097-1021) · SSRN: [https://ssrn.com/author=10825096](https://ssrn.com/author=10825096)
PhD Economics (Econometrics)
