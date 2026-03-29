# SECMap — Concept of Operations (CONOPS)
Version 2.0 — DoD‑Style Operational Document

> **Author:** Robert J. Green
> **Web:** [www.rjgreenresearch.org](https://www.rjgreenresearch.org)
> **Email:** [robert@rjgreenresearch.org](mailto:robert@rjgreenresearch.org)
> **ORCID:** [0009-0002-9097-1021](https://orcid.org/0009-0002-9097-1021)
> **SSRN:** [https://ssrn.com/author=10825096](https://ssrn.com/author=10825096)


## 1. Purpose

This CONOPS describes the operational use, mission context, and user interactions for SECMap, a deterministic system for tracing beneficial ownership chains through SEC filings to their ultimate terminus — including chains that route through adversarial nations, conduit jurisdictions, and opacity havens — with extensions for state‑level entity gap analysis.


## 2. System Overview

SECMap is a command‑line, modular, deterministic processing system that:

- Discovers related entities via recursive CIK traversal to 10 layers of depth  
- Retrieves and caches SEC filings and company metadata  
- Extracts people from structural signature positions (/s/, By:)  
- Extracts institutions from corporate suffix patterns  
- Parses SC‑13 cover pages for beneficial ownership entries  
- Classifies every entity by jurisdiction risk tier (5 tiers, 135+ countries)  
- Detects state‑actor affiliation across 6 adversarial nations  
- Flags obscuring roles (nominee, proxy, intermediary) that indicate layered ownership  
- Produces 25‑column deterministic CSV artifacts with chain analysis summary  
- Ingests the full SEC filing universe (10,438 companies across 5 exchanges)  
- Executes research‑scale batch runs across entire markets  
- Catalogs state SOS access methods for all 50 states + DC  
- Analyzes the federal/state visibility gap for private entity discovery  


## 3. Operational Need

### 3.1 AFIDA Depth Limitation
The USDA Agricultural Foreign Investment Disclosure Act relies on self‑reporting and typically traces ownership to 2–3 layers. Real‑world adversarial ownership structures use 7+ layers (e.g., Syngenta AG: SASAC → CNAC → ChemChina → CNAC Saturn BV → Syngenta AG → state‑registered subsidiaries). SECMap traces to 10 layers.

### 3.2 SEC Scope Limitation
SEC EDGAR covers public companies and their direct filers. Ownership chains frequently terminate in private entities (LLCs, LPs, trusts) registered at the state level that are invisible to federal databases.

### 3.3 Federal/State Visibility Gap
State Secretary of State records cover ALL business entities including private ones, but these records are siloed across 50 separate systems with no federal aggregation. Adversarial nations exploit this gap. Example: Brazos Highland Properties LP (Texas) → Guangxin Sun (former PLA officer, largest Chinese landowner in US) was only discoverable through Texas SOS records.

### 3.4 No Existing Deterministic Tool
Existing systems are proprietary black boxes, non‑deterministic, and do not provide reproducible artifact‑grade output suitable for econometric research or regulatory proceedings.


## 4. Operational Environment

SECMap operates in:

- Analyst workstations (Windows, macOS, Linux)  
- Research environments (university compute clusters)  
- CI/CD pipelines (automated regression testing)  
- Air‑gapped systems (offline mode using disk cache)  
- Cloud compute environments (batch processing)  

Requirements: Python 3.10+, filesystem access, optional network access for SEC EDGAR.


## 5. User Roles

### 5.1 Econometrics Researchers
Run systematic scans across entire exchanges to build reproducible datasets for PhD research on foreign ownership patterns, AFIDA adequacy, and adversarial‑nation investment flows.

### 5.2 Intelligence Analysts
Trace beneficial ownership chains to identify adversarial‑nation terminus entities, state‑actor affiliations (SOE, MCF, UFWD, IRGC), and obscuring structures (nominees, proxies, shell companies).

### 5.3 SEC/USDA/CFIUS Analysts
Use outputs for beneficial ownership enforcement, AFIDA foreign ownership screening, and CFIUS cross‑border control risk assessment.

### 5.4 Policy Specialists
Evaluate the adequacy of current disclosure regimes by quantifying the federal/state visibility gap and the depth limitation of AFIDA.

### 5.5 Compliance Officers
Screen entities for sanctions exposure, PEP associations, and sovereign wealth fund involvement.

### 5.6 Engineers
Integrate SECMap into larger analytical pipelines, extend with new extractors or classifiers, and maintain the test suite.


## 6. Operational Scenarios

Scenario 1: Single‑CIK Ownership Chain Trace
An analyst runs:
```
secmap run --cik 1123658 --forms 10-K 20-F SC\ 13D SC\ 13G --depth 10 --limit 50 --out sinopec.csv
```
System produces a 25‑column CSV tracing Sinopec's ownership chain through SASAC, with every entity classified by risk tier and state affiliation.

Scenario 2: Research‑Scale Exchange Scan
A PhD researcher runs:
```
python run_research.py --exchange OTC
```
System processes all 2,575 OTC‑listed companies (highest opacity risk), producing per‑CIK CSVs and a combined dataset. Run is resumable if interrupted.

Scenario 3: Adversarial‑Nation Screening
An intelligence analyst runs:
```
python run_research.py --search "china"
```
System processes all 24 China‑related SEC filers, flagging SOE, MCF, UFWD, and Party‑Controlled affiliations in the output.

Scenario 4: AFIDA Depth Adequacy Analysis
A policy researcher compares SECMap's 10‑layer chain output against AFIDA's 2–3 layer self‑reported data for the same entities, quantifying the disclosure gap.

Scenario 5: State SOS Gap Analysis
A researcher loads SEC ownership chains and Texas SOS entity records into the gap analyzer:
```python
analyzer = GapAnalyzer()
analyzer.load_sec_entities(sec_edges)
analyzer.load_state_entities(texas_entities)
gaps = analyzer.find_gaps()
report = analyzer.generate_report(gaps)
```
System identifies entities visible at state level but invisible to SEC/AFIDA, risk‑scored by shell‑structure patterns and privacy‑state registration.

Scenario 6: Production Batch Run
An operations team runs:
```
python run_production.py
```
System processes a configured list of target CIKs with per‑CIK output, combined CSV, chain analysis summary, and production log.

Scenario 7: Air‑Gapped Operation
SECMap runs entirely offline using the disk cache populated from a previous network‑connected run. All SEC data is served from ./cache/ with zero network requests.

Scenario 8: Risk Triage
An analyst runs a production batch against 100 CIKs. The system produces risk-prefixed CSV files (`CRITICAL_cik_*.csv`, `LOW_cik_*.csv`) and a `TRIAGE_MANIFEST.md` sorted by risk score. The analyst opens the manifest, identifies 12 CRITICAL-rated entities, and generates detailed reports and network visualizations for only those 12 — ignoring the 88 LOW/MODERATE files.

Scenario 9: Network Visualization
An analyst generates an ownership chain diagram:
```
python network_visualizer.py output/run_XXXX/per_cik/cik_91388.csv --format svg
```
System produces a hierarchical graph showing companies, persons, countries, and their relationships.


## 7. System Capabilities

- 10‑layer recursive CIK discovery  
- Positional person extraction (zero false positives from boilerplate)  
- SC‑13 cover page parsing (handles repeating pages, IRS ID lines)  
- 5‑tier jurisdiction risk classification (135+ countries)  
- Multi‑nation state‑actor affiliation detection (PRC, Russia, Iran, DPRK, Belarus, Myanmar, Syria, Cuba, Venezuela)  
- Sovereign wealth fund detection  
- Shell/proxy/nominee detection  
- 50+ role categories with Deputy {X} variants  
- Semantic role flags (executive, board, ownership, obscuring)  
- 25‑column deterministic CSV with chain analysis summary  
- Disk caching (zero redundant SEC requests)  
- SEC universe ingestion (10,438 companies, 28,183 mutual funds)  
- Research‑scale batch execution with resume support  
- 51‑jurisdiction state SOS access catalog  
- Federal/state visibility gap analysis with risk scoring  
- 143+ automated tests  


## 8. Support and Maintenance

- Modular codebase (22 modules across 4 layers)  
- Full test suite (143 tests: unit, integration, regression, smoke)  
- HTML and Markdown test reports  
- Disk cache for development iteration without SEC hits  
- Resumable research runs  
- Apache 2.0 license  
- CITATION.cff for academic citation  
