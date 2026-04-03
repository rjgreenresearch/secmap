

# SECMap -- Software Requirements Specification (SRS)
IEEE‑Style Requirements Document  
Version 2.0

> **Author:** Robert J. Green
> **Web:** [www.rjgreenresearch.org](https://www.rjgreenresearch.org)
> **Email:** [robert@rjgreenresearch.org](mailto:robert@rjgreenresearch.org)
> **ORCID:** [0009-0002-9097-1021](https://orcid.org/0009-0002-9097-1021)
> **SSRN:** [https://ssrn.com/author=10825096](https://ssrn.com/author=10825096)


## 1. Introduction

### 1.1 Purpose
This document defines the functional and non‑functional requirements for SECMap, a software system that extracts, normalizes, and maps beneficial ownership and governance relationships from SEC filings, with extensions for risk classification, adversarial‑nation detection, and state‑level entity gap analysis. The intended audience includes developers, maintainers, researchers, and stakeholders requiring a reproducible and auditable ownership‑mapping instrument.

### 1.2 Scope
SECMap ingests SEC filings, extracts structured entities and relationships, classifies them by jurisdiction risk tier and state‑actor affiliation, and produces a deterministic, pipe‑delimited CSV suitable for analytics, visualization, and research. The system supports recursive CIK discovery to 10 layers of depth, SC‑13 beneficial ownership parsing, positional person extraction, role classification with semantic flags, disk‑based caching, research‑scale batch execution across the full SEC filing universe, and state Secretary of State integration for federal/state visibility gap analysis.

### 1.3 Definitions
- CIK -- Central Index Key assigned by the SEC  
- SC‑13 -- Beneficial ownership filings (13D/13G and amendments)  
- Entity -- Person, institution, or company extracted from filings  
- Edge -- Typed relationship between entities with metadata  
- CSV Artifact -- Deterministic output file containing edges  
- BOI -- Beneficial Ownership Information  
- UBO -- Ultimate Beneficial Owner  
- Risk Tier -- Jurisdiction classification (ADVERSARIAL, CONDUIT, OPACITY, MONITORED, STANDARD)  
- State Affiliation -- Classification of entity relationship to state actors (SOE, MCF, UFWD, SWF, PEP, Shell‑Proxy)  
- AFIDA -- Agricultural Foreign Investment Disclosure Act  
- SOS -- Secretary of State (state‑level business entity registry)  

### 1.4 References
- IEEE 830 / 29148 SRS standards  
- SEC EDGAR Filer Manual  
- SECMap Architecture & Technical Reference (v1.1.0)  
- USDA AFIDA regulations (7 CFR Part 781)  


## 2. Overall Description

### 2.1 Product Perspective
SECMap is a standalone command‑line application with modular components for fetching, parsing, extraction, classification, risk scoring, and output generation. It integrates with local configuration, environment variables, CLI overrides, disk‑based caching, and the SEC ticker universe endpoints. It includes a state SOS integration module for bridging the federal/state visibility gap.

### 2.2 Product Functions
- Discover CIK universe recursively to depth 10  
- Fetch and cache SEC filings and company metadata  
- Parse filings into structured sections  
- Extract people using positional/structural patterns  
- Extract institutions using corporate suffix patterns  
- Parse SC‑13 beneficial ownership from cover page structure  
- Classify jurisdictions by risk tier (5 tiers, 135+ countries)  
- Classify entities by state‑actor affiliation (10 categories, 6 adversarial nations)  
- Classify roles with semantic flags (executive, board, ownership, obscuring)  
- Build typed edges with full chain‑analysis metadata  
- Build incorporated_in edges from company metadata  
- Deduplicate edges deterministically  
- Produce 25‑column deterministic CSV output with chain analysis summary  
- Ingest the full SEC filing universe (10,438 companies, 28,183 mutual funds)  
- Execute research‑scale batch runs across entire exchanges  
- Catalog state SOS access methods for all 50 states + DC  
- Analyze federal/state visibility gaps  
- Parse Texas SOS PDF documents  

### 2.3 User Characteristics
Users include:
- Econometrics researchers (PhD‑level, reproducible datasets)  
- Intelligence analysts (ownership chain tracing, adversarial‑nation detection)  
- SEC/USDA/CFIUS analysts (beneficial ownership enforcement, AFIDA screening)  
- Policy specialists (foreign investment risk assessment)  
- Compliance officers (AML, sanctions screening)  
- Investigative journalists (corporate structure mapping)  
- Engineers integrating SECMap into analytical pipelines  

### 2.4 Constraints
- Must not rely on network access during tests  
- Must produce deterministic output  
- Must sanitize all CSV fields  
- Must handle malformed filings gracefully  
- Must comply with SEC EDGAR fair‑access policy (rate limiting)  
- Maximum recursion depth shall not exceed 10  
- Must cache all SEC requests to disk to prevent redundant network hits  

### 2.5 Assumptions and Dependencies
- Python 3.10+  
- Local filesystem access  
- Optional network access for SEC EDGAR  
- Optional PyPDF2 or pdfplumber for Texas SOS PDF parsing  
- Optional networkx and matplotlib for visualization  


## 3. System Requirements

### 3.1 Functional Requirements

#### FR‑1: CIK Discovery
The system shall recursively discover related CIKs up to a user‑defined depth (maximum 10).

#### FR‑2: Filing Retrieval
The system shall retrieve filings for each discovered CIK, up to a user‑defined limit (maximum 50), using the primaryDocument field from the SEC submissions API.

#### FR‑3: Disk Caching
The system shall cache all SEC EDGAR responses to disk. Subsequent requests for the same URL shall be served from cache without network access.

#### FR‑4: Company Metadata
The system shall retrieve and store company metadata (name, SIC code, state of incorporation) for each discovered CIK from the SEC submissions JSON.

#### FR‑5: Filing Parsing
The system shall parse filings into structured sections including:
- Full text (HTML/XBRL stripped and normalized)  
- Signatures  
- Narrative  
- Country mentions  

#### FR‑6: Positional Person Extraction
The system shall extract person names only from structural locations:
- /s/ signature patterns (with lookahead for concatenated title keywords)  
- By: signature patterns  
- Name, age XX patterns  
- Title‑adjacent patterns  

#### FR‑7: Institution Extraction
The system shall extract institution names using corporate suffix patterns, with length capping (80 chars) and sentence‑fragment rejection.

#### FR‑8: SC‑13 Beneficial Ownership Parsing
The system shall parse SC 13D/G cover page structure to extract:
- Reporting person names (skipping IRS ID lines, share counts, fund source codes)  
- Ownership percentages  
- Class titles  
- Issuer names  

#### FR‑9: Jurisdiction Risk Classification
The system shall classify every entity jurisdiction into one of five risk tiers:
- ADVERSARIAL (10 nations)  
- CONDUIT (24 jurisdictions)  
- OPACITY (38 jurisdictions)  
- MONITORED (26 jurisdictions)  
- STANDARD (37 jurisdictions)  

#### FR‑10: State‑Actor Affiliation Classification
The system shall classify entities by state‑actor affiliation across:
- PRC (SOE, Party‑Controlled, MCF, UFWD)  
- Russia (state corporations, FSB/GRU‑adjacent)  
- Iran (IRGC, bonyads)  
- DPRK (front companies, Office 39)  
- Belarus, Syria, Myanmar, Venezuela, Cuba  
- Global: sovereign wealth funds, shell/proxy indicators, PEP  

#### FR‑11: Role Classification
The system shall classify roles into 50+ canonical categories with semantic flags:
- is_executive, is_board, is_supervisory, is_ownership, is_obscuring  
- Deputy {X} variants for foreign filings  
- Word‑boundary regex to prevent substring false positives  

#### FR‑12: Edge Construction
The system shall construct typed edges including:
- person_role  
- institution_role  
- beneficial_owner  
- incorporated_in  
- country_association  

Each edge shall carry: source/target jurisdiction, risk tier, state affiliation (category + subcategory + detail), role flags, chain depth, company name, and CIK.

#### FR‑13: Incorporated_in Edges
The system shall build incorporated_in edges from company metadata, mapping state codes to full jurisdiction names (50 US states + DC + Canadian provinces + SEC country codes).

#### FR‑14: Deduplication
The system shall merge and deduplicate edges deterministically, preserving the highest‑risk metadata from merged edges.

#### FR‑15: CSV Output
The system shall write a deterministic, pipe‑delimited CSV with 25 columns, a metadata header, a column header row, and a chain analysis summary including adversarial/conduit/opacity edge counts.

#### FR‑16: CLI Interface
The system shall provide a command‑line interface supporting:
- Single‑CIK runs  
- Required and optional arguments  
- Logging configuration  

#### FR‑17: SEC Universe Ingestion
The system shall pull the complete SEC filing universe from:
- company_tickers.json  
- company_tickers_exchange.json  
- company_tickers_mf.json  

#### FR‑18: Research‑Scale Execution
The system shall support batch execution across entire exchanges (NYSE, Nasdaq, OTC) with:
- Resumable runs  
- Progress tracking and ETA estimation  
- Per‑CIK and combined output  
- Run manifest and results JSON  

#### FR‑19: State SOS Registry
The system shall catalog the access method, endpoint URL, cost, and latency for all 50 states + DC, classified by access tier (API, Bulk, Web, Paywall, Restricted).

#### FR‑20: Federal/State Gap Analysis
The system shall compare SEC ownership chains against state SOS entity registrations to identify entities visible at state level but invisible to federal databases, with risk scoring based on shell‑structure name patterns, privacy‑state registration, layering vehicle type, and commercial registered agent usage.

#### FR‑21: Texas SOS PDF Parsing
The system shall extract entity name, type, status, formation date, registered agent, and officers from Texas SOS PDF documents, including ZIP archives.


### 3.2 Non‑Functional Requirements

#### NFR‑1: Determinism
Given identical inputs and cache state, the system shall produce byte‑identical CSV output.

#### NFR‑2: Performance
The system shall process a synthetic micro‑universe in < 200 ms on modern hardware.

#### NFR‑3: Robustness
The system shall not crash on malformed filings, missing fields, or network errors.

#### NFR‑4: Logging
The system shall provide structured, timestamped logs with module identifiers.

#### NFR‑5: Testability
The system shall include 143+ tests covering:
- Unit tests for all extractors, parsers, and classifiers  
- Integration tests for the full pipeline  
- Golden‑file regression tests  
- Reproducibility tests  
- CLI smoke tests  

#### NFR‑6: Portability
The system shall run on Linux, macOS, and Windows.

#### NFR‑7: SEC Fair Access
The system shall enforce a minimum 150ms delay between SEC EDGAR requests and respect HTTP 429 rate‑limit responses with exponential backoff.

#### NFR‑8: Cache Efficiency
The system shall serve all previously‑fetched SEC data from disk cache, producing zero redundant network requests across runs.

#### NFR‑9: Resumability
Research‑scale runs shall be resumable after interruption, skipping already‑completed CIKs.


## 4. External Interface Requirements

### 4.1 CLI Interface
The system shall expose a secmap command with subcommands and arguments.

### 4.2 SEC EDGAR Interface
The system shall communicate with:
- data.sec.gov (submissions JSON)  
- www.sec.gov (filing documents)  
- www.sec.gov/files/ (ticker universe endpoints)  

### 4.3 File Interface
The system shall read and write UTF‑8 text files. Cache files shall mirror the URL path structure.

### 4.4 Logging Interface
The system shall write logs to console and optionally to a file.

### 4.5 State SOS Interface
The system shall support ingestion from:
- State APIs (9 states)  
- Bulk downloads (21 states)  
- Web scraping (20 states)  
- PDF documents (Texas paywall)  


## 5. Traceability Matrix

| Requirement | Module(s) |
|---|---|
| FR‑1 | cik_discovery.py |
| FR‑2 | sec_fetch.py |
| FR‑3 | sec_fetch.py (cache functions) |
| FR‑4 | cik_discovery.py, sec_fetch.py |
| FR‑5 | parse_filings.py |
| FR‑6 | people_extractor.py |
| FR‑7 | institution_extractor.py |
| FR‑8 | sc13_parser.py |
| FR‑9 | jurisdiction_inference.py |
| FR‑10 | state_affiliation.py |
| FR‑11 | role_taxonomy.py |
| FR‑12 | ownership_edges.py |
| FR‑13 | ownership_mapper.py |
| FR‑14 | ownership_edges.py |
| FR‑15 | csv_writer.py, metadata.py |
| FR‑16 | cli.py, main.py |
| FR‑17 | sec_universe.py |
| FR‑18 | run_research.py |
| FR‑19 | state_sos/state_registry.py |
| FR‑20 | state_sos/gap_analyzer.py |
| FR‑21 | state_sos/texas_sos.py |


## 6. Appendices
- Glossary  
- Example 25‑column CSV output  
- Example CLI invocations  
- Risk tier country lists  
- State SOS access catalog  


---

## Performance Requirements (Added v2.0)

| ID | Requirement | Priority |
|---|---|---|
| **NFR-10** | The system shall support async HTTP fetching with configurable concurrency (default 8 concurrent connections) for cache warming | HIGH |
| **NFR-11** | The system shall support multiprocessing with configurable worker count for parallel CIK processing | HIGH |
| **NFR-12** | The system shall support XBRL-based pre-filtering to skip CIKs not present in structured data | MEDIUM |
| **NFR-13** | The system shall maintain constant memory usage per CIK regardless of total CIKs processed | HIGH |
| **NFR-14** | The async and synchronous fetchers shall share a common disk cache for interoperability | HIGH |
| **NFR-15** | The cache warmer shall achieve >= 50 filings/second throughput on broadband connections | MEDIUM |
