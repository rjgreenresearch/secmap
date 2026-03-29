# SECMap — System Architecture Document (SAD)
IEEE 42010‑Style System Architecture Description  
Version 2.0

> **Author:** Robert J. Green
> **Web:** [www.rjgreenresearch.org](https://www.rjgreenresearch.org)
> **Email:** [robert@rjgreenresearch.org](mailto:robert@rjgreenresearch.org)
> **ORCID:** [0009-0002-9097-1021](https://orcid.org/0009-0002-9097-1021)
> **SSRN:** [https://ssrn.com/author=10825096](https://ssrn.com/author=10825096)


## 1. Introduction

### 1.1 Purpose
This System Architecture Document describes the structure, components, interfaces, and architectural rationale for SECMap, a deterministic beneficial ownership mapping system that traces ownership chains through SEC filings to their ultimate terminus across adversarial nations, conduit jurisdictions, and opacity havens, with extensions for state‑level entity gap analysis.

### 1.2 Scope
SECMap ingests SEC filings, extracts structured entities and relationships, classifies them by jurisdiction risk tier and state‑actor affiliation, and produces deterministic CSV artifacts. The architecture supports 10‑layer recursive discovery, multi‑nation risk classification, disk caching, research‑scale batch execution, and state SOS integration.

### 1.3 Stakeholders
- Econometrics researchers — reproducible datasets for PhD research  
- Intelligence analysts — adversarial‑nation ownership chain tracing  
- SEC/USDA/CFIUS analysts — beneficial ownership enforcement, AFIDA screening  
- Policy specialists — foreign investment risk assessment  
- Developers — maintain and extend the system  
- Operators — run CLI and batch pipelines  


## 2. Architectural Drivers

### 2.1 Functional Drivers
- 10‑layer recursive CIK discovery  
- Filing retrieval with disk caching  
- Positional entity extraction (structural, not generic regex)  
- SC‑13 cover page parsing  
- 5‑tier jurisdiction risk classification  
- Multi‑nation state‑actor affiliation detection  
- Role classification with semantic flags  
- 25‑column edge construction with chain‑analysis metadata  
- SEC universe ingestion (10,438 companies, 28,183 funds)  
- Research‑scale batch execution  
- State SOS gap analysis  

### 2.2 Quality Attribute Drivers
- Determinism — identical input + cache → identical output  
- Reproducibility — golden‑file regression, hash comparison  
- Robustness — malformed filings handled gracefully  
- Testability — 143+ tests (unit, integration, regression, smoke)  
- Modularity — each function isolated in its own module  
- Traceability — structured logging, metadata headers, chain analysis summary  
- Cacheability — zero redundant SEC requests across runs  
- Resumability — research runs survive interruption  

### 2.3 Constraints
- Python 3.10+  
- No external database  
- Must run offline for tests (mocked SEC data)  
- Must comply with SEC EDGAR fair‑access policy  
- Maximum recursion depth: 10  


## 3. System Overview

SECMap is a modular pipeline composed of six architectural layers:

1. **Fetch & Cache Layer** — SEC EDGAR HTTP client with disk caching  
2. **Discovery Layer** — BFS recursive CIK traversal with company metadata  
3. **Parse & Extract Layer** — Filing parsing, positional person extraction, institution extraction, SC‑13 parsing  
4. **Classification & Risk Layer** — Jurisdiction inference, state affiliation, role taxonomy  
5. **Edge Construction & Output Layer** — Typed edges, deduplication, 25‑column CSV, metadata  
6. **Research & Gap Analysis Layer** — SEC universe, batch runner, state SOS registry, gap analyzer  

Plus cross‑cutting: Config, Logging, CLI.


## 4. Architectural Views

### 4.1 Logical View — Module Inventory

Core Pipeline:
- sec_fetch.py — HTTP client + disk cache  
- cik_discovery.py — BFS CIK traversal + company metadata  
- parse_filings.py — HTML/XBRL stripping, section extraction  
- people_extractor.py — Positional /s/ and By: extraction  
- institution_extractor.py — Corporate suffix extraction  
- sc13_parser.py — SC‑13 cover page parser  
- relationship_builder.py — Combines extractors, classifies roles  
- ownership_edges.py — OwnershipEdge dataclass (25 fields), edge builders, deduplication  
- ownership_mapper.py — Pipeline orchestrator  
- csv_writer.py — 25‑column pipe‑delimited CSV  
- metadata.py — Run metadata + chain analysis summary  

Classification:
- jurisdiction_inference.py — 5 risk tiers, 135+ countries, city tokens  
- state_affiliation.py — 10 categories, 6 adversarial nations, SWF, shell/proxy, PEP  
- role_taxonomy.py — 50+ roles, semantic flags, Deputy variants, word‑boundary regex  
- entity_classification.py — Entity type heuristics  
- entity_extraction.py — Name cleaning, org detection  

SEC Universe:
- sec_universe.py — 3 SEC ticker endpoints, exchange filtering  

State SOS:
- state_sos/state_registry.py — 51 jurisdictions, access tier catalog  
- state_sos/gap_analyzer.py — Federal/state visibility gap, risk scoring, persistence  
- state_sos/texas_sos.py — PDF parser for Texas SOS documents  

Cross‑cutting:
- config.py — 3‑layer config, validation  
- logging_config.py — Structured logging  
- cli.py, main.py — CLI entrypoints  

Key Data Structures:
- Entity (raw_name, cleaned_name, entity_type, notes)  
- OwnershipEdge (25 fields including jurisdiction, risk tier, state affiliation, role flags, chain depth)  
- SECMapResult (root_cik, visited_ciks, filings_processed, edges, company_info)  
- RoleClassification (canonical_role, confidence, is_executive, is_board, is_ownership, is_obscuring)  
- StateAffiliation (category, subcategory, details, confidence)  
- JurisdictionResult (country, risk_tier, matched_token)  
- ChainAnalysisSummary (adversarial/conduit/opacity/state‑affiliated/obscuring counts)  


### 4.2 Process View — Pipeline Execution Flow

```
CLI / Batch Runner
    │
    ▼
Config + Logging
    │
    ▼
CIK Discovery (BFS, depth 0..10)
    ├── fetch_company_submissions() → company name, SIC, state of inc.
    ├── fetch_filings_for_cik() → primaryDocument content (cached)
    └── extract_ciks_from_text() → enqueue discovered CIKs
    │
    ▼
For each filing:
    ├── parse_filing_to_sections() → full_text, signatures, narrative, countries
    ├── extract_people_from_signatures(full_text) → /s/ positional extraction
    ├── extract_people_from_narrative(narrative) → Name,age + title adjacency
    ├── extract_institutions_from_narrative(narrative) → corporate suffixes
    ├── classify_role(name, context) → RoleClassification with flags
    ├── infer_jurisdiction_with_risk(name) → JurisdictionResult
    ├── classify_state_affiliation(name, role, country) → StateAffiliation
    ├── parse_sc13_beneficial_ownership(full_text) → cover page entries
    └── build edges → OwnershipEdge with all 25 fields
    │
    ▼
build_incorporated_in_edges(company_info) → state code → full name
    │
    ▼
merge_and_deduplicate_edges()
    │
    ▼
compute_chain_summary() → adversarial/conduit/opacity counts
    │
    ▼
write_edges_to_csv() → 25‑column pipe‑delimited CSV + metadata header
```


### 4.3 Development View

- Each module is isolated and independently testable  
- No circular dependencies  
- All I/O at the edges (sec_fetch + csv_writer)  
- Core logic is pure and deterministic  
- Classification modules are stateless (keyword lists + regex)  
- State SOS module supports incremental ingestion and persistence  


### 4.4 Physical View

- Runs on any OS with Python 3.10+  
- Disk cache under ./cache/ (mirrors URL path structure)  
- Output under ./output/ (per‑run directories)  
- No external database or services required  
- Optional network access for SEC EDGAR (cached after first fetch)  


### 4.5 Scenarios (Use Cases)

#### UC‑1: Trace beneficial ownership chain for a single CIK to depth 10
#### UC‑2: Parse SC‑13 cover pages to extract reporting persons and percentages
#### UC‑3: Classify all entities in a chain by adversarial‑nation risk tier
#### UC‑4: Detect state‑actor affiliation (SOE, MCF, UFWD, IRGC, etc.)
#### UC‑5: Flag obscuring roles (nominee, proxy, intermediary) in ownership chains
#### UC‑6: Scan all NYSE‑listed companies for adversarial ownership patterns
#### UC‑7: Identify state‑registered entities invisible to SEC/AFIDA
#### UC‑8: Generate reproducible CSV artifact for econometric analysis
#### UC‑9: Resume interrupted research‑scale batch run
#### UC‑10: Parse Texas SOS PDF documents for gap analysis


## 5. Architecture Rationale

- Modularity → maintainability and independent testing  
- Determinism → scientific reproducibility for PhD research  
- Positional extraction → zero false positives from filing boilerplate  
- Risk tiers → quantifiable chain‑risk scoring  
- 25‑column CSV → rich enough for any downstream consumer  
- Disk caching → SEC fair‑access compliance + iteration speed  
- State SOS integration → bridges the federal/state visibility gap  
- Incremental gap analysis → accommodates heterogeneous state access timelines  


## 6. Appendices
- Module dependency graph  
- Risk tier country lists  
- State SOS access catalog  
- Example 25‑column CSV  
