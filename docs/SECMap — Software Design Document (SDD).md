# SECMap — Software Design Document (SDD)
IEEE 1016‑Style Software Design Description  
Version 2.0

> **Author:** Robert J. Green
> **Web:** [www.rjgreenresearch.org](https://www.rjgreenresearch.org)
> **Email:** [robert@rjgreenresearch.org](mailto:robert@rjgreenresearch.org)
> **ORCID:** [0009-0002-9097-1021](https://orcid.org/0009-0002-9097-1021)
> **SSRN:** [https://ssrn.com/author=10825096](https://ssrn.com/author=10825096)


## 1. Introduction

### 1.1 Purpose
This SDD describes the detailed design of SECMap v2.0, including module responsibilities, data structures, algorithms, interfaces, and error‑handling strategies for all 22 modules across 6 architectural layers.

### 1.2 Scope
Covers all software components required to execute the SECMap pipeline including 10‑layer recursive discovery, positional extraction, risk classification, and state SOS gap analysis.


## 2. Design Goals
- Deterministic output (byte‑identical for identical inputs + cache)  
- Zero false positives in person extraction (positional, not generic regex)  
- Multi‑nation risk classification  
- Disk caching for SEC fair‑access compliance  
- Research‑scale batch execution  
- Federal/state visibility gap analysis  
- 143+ test coverage  


## 3. Detailed Module Design

3.1 sec_fetch.py (Fetch & Cache Layer)
Responsibilities: SEC EDGAR HTTP client with disk caching  
Key functions: _fetch_text(), _fetch_json(), fetch_company_submissions(), fetch_filings_for_cik()  
Caching: URL → SHA-256 hash → filesystem path. Cache HIT returns disk content, MISS fetches + writes.  
Rate limiting: 150ms minimum delay, 429 backoff  
Error handling: Retry with exponential backoff, returns None on failure  

3.2 cik_discovery.py (Discovery Layer)
Responsibilities: BFS CIK traversal, company metadata collection  
Key structures: DiscoveryConfig, DiscoveredFiling (with company field), DiscoveryResult (with company_info dict)  
Algorithm: BFS queue with (cik, depth) tuples, max depth 10  
Outputs: visited CIKs, filings list, company_info per CIK  

3.3 parse_filings.py (Parse Layer)
Responsibilities: HTML/XBRL stripping, section extraction  
Sections: full_text, signatures, narrative, countries  
Design: Regex‑based, deterministic ordering  

3.4 people_extractor.py (Extract Layer)
Responsibilities: Positional person extraction from structural locations  
Algorithm: /s/ pattern with title‑keyword lookahead, By: pattern, Name+age pattern, title adjacency  
Key design: Lookahead handles concatenated text (e.g., "/s/ C. Shane SmithChief Executive Officer")  
Validation: Org suffix rejection, Roman numeral fragment rejection  
No generic [A-Z][a-z]+ scanning — structural positions only  

3.5 institution_extractor.py (Extract Layer)
Responsibilities: Corporate entity extraction  
Algorithm: Corporate suffix regex with 80‑char length cap  
Filtering: Sentence‑fragment rejection, lowercase‑start rejection  

3.6 sc13_parser.py (Extract Layer)
Responsibilities: SC‑13 cover page parsing  
Algorithm: Finds "NAME OF REPORTING PERSON" headers, extracts name from next non‑label line, skips IRS ID lines  
Validation: Rejects share counts, fund source codes, form field labels  
Output: BeneficialOwnershipEntry list  

3.7 jurisdiction_inference.py (Classification Layer)
Responsibilities: 5‑tier jurisdiction risk classification  
Data: 135+ countries organized by risk tier, city‑level tokens  
Key functions: infer_jurisdiction(), infer_jurisdiction_with_risk(), get_risk_tier()  
Priority: ADVERSARIAL matches win over lower tiers  

3.8 state_affiliation.py (Classification Layer)
Responsibilities: Multi‑nation state‑actor affiliation detection  
Categories: SOE, Party‑Controlled, MCF, UFWD (PRC), State‑Linked (Russia, Iran, DPRK, Belarus, Syria, Myanmar, Venezuela, Cuba), SWF, Shell‑Proxy, PEP  
Output: StateAffiliation(category, subcategory, details, confidence)  

3.9 role_taxonomy.py (Classification Layer)
Responsibilities: 50+ role classification with semantic flags  
Flags: is_executive, is_board, is_supervisory, is_ownership, is_obscuring  
Deputy variants: Deputy CEO, Deputy Director of Economics, Deputy Minister, etc.  
Regex: Word‑boundary patterns, longest‑first alternation  

3.10 ownership_edges.py (Edge Layer)
Responsibilities: 25‑field OwnershipEdge dataclass, edge builders, deduplication  
Fields: source/target entity, jurisdiction, risk tier, state affiliation (cat/sub/detail), role flags, chain depth, company name/CIK, filing metadata  
Deduplication: Deterministic key, preserves highest‑risk metadata on merge  

3.11 ownership_mapper.py (Orchestrator)
Responsibilities: Full pipeline coordination  
Flow: discovery → incorporated_in edges → per‑filing extraction → SC‑13 parsing → deduplication  
Company names: Resolved from filing metadata or discovery company_info, never raw CIK  
State code mapping: 50 US states + DC + Canadian provinces + SEC country codes → full names  

3.12 csv_writer.py (Output Layer)
Responsibilities: 25‑column pipe‑delimited CSV  
Columns: source, source_type, source_jurisdiction, source_risk_tier, target, target_type, target_jurisdiction, target_risk_tier, relationship, detail, company_name, company_cik, state_affiliation, state_affiliation_sub, state_affiliation_detail, role_is_executive, role_is_board, role_is_ownership, role_is_obscuring, chain_depth, filing_accession, filing_form, filing_date, method, notes  
Sanitization: Control chars, pipes, quotes  

3.13 metadata.py (Output Layer)
Responsibilities: Run metadata + ChainAnalysisSummary  
Summary fields: total/adversarial/conduit/opacity/state‑affiliated/obscuring/ownership edge counts, max chain depth, unique jurisdictions, adversarial jurisdictions  

3.14 sec_universe.py (Research Layer)
Responsibilities: SEC ticker universe ingestion  
Endpoints: company_tickers.json, company_tickers_exchange.json, company_tickers_mf.json  
Query: by_exchange(), search(), by_cik(), all_ciks()  

3.15 state_sos/state_registry.py (Gap Analysis Layer)
Responsibilities: 51‑jurisdiction access catalog  
Tiers: API (9), Bulk (21), Web (20), Paywall (1)  
Data: endpoint URL, cost, latency, capabilities per state  

3.16 state_sos/gap_analyzer.py (Gap Analysis Layer)
Responsibilities: Federal/state visibility gap identification  
Algorithm: Compare SEC entity set against state entity set, risk‑score gaps  
Persistence: save_state() / load_saved_state() for long‑running research  

3.17 state_sos/texas_sos.py (Gap Analysis Layer)
Responsibilities: Texas SOS PDF parsing  
Extraction: Entity name, type, status, formation date, registered agent, officers  

3.18–3.22 config.py, logging_config.py, cli.py, main.py, entity_classification.py, entity_extraction.py
(Unchanged from v1.0 design, see Architecture & Technical Reference for details)


## 4. Data Design

### 4.1 Key Data Structures (v2.0)

OwnershipEdge (25 fields):
  source, target, relationship, relationship_detail, filing,
  method, notes, source_jurisdiction, source_risk_tier,
  target_jurisdiction, target_risk_tier, state_affiliation,
  state_affiliation_sub, state_affiliation_detail,
  role_is_executive, role_is_board, role_is_ownership,
  role_is_obscuring, chain_depth

SECMapResult:
  root_cik, visited_ciks, filings_processed, edges, company_info

RoleClassification:
  canonical_role, raw_role_text, confidence,
  is_executive, is_board, is_supervisory, is_ownership, is_obscuring

JurisdictionResult:
  country, risk_tier, matched_token

StateAffiliation:
  category, subcategory, details, confidence

ChainAnalysisSummary:
  total_edges, adversarial_edges, conduit_edges, opacity_edges,
  state_affiliated_edges, obscuring_role_edges, ownership_edges,
  max_chain_depth, unique_jurisdictions, adversarial_jurisdictions


## 5. Error Handling
- All modules log errors and continue (no crash on malformed filings)  
- Orchestrator catches per‑filing exceptions  
- CSV writer never corrupts output  
- Cache read failures fall through to network fetch  
- Config validation prevents invalid states  


## 6. Test Design
143 tests covering:
- Unit tests for all extractors, parsers, classifiers  
- Integration tests for full pipeline with mocked SEC data  
- Golden‑file regression tests  
- Reproducibility tests (hash comparison)  
- CLI smoke tests  
- Cache read/write tests  
- State registry query tests  
