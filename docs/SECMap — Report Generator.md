# SECMap -- Ownership Chain Summary Report Generator

> **Author:** Robert J. Green
> **Web:** [www.rjgreenresearch.org](https://www.rjgreenresearch.org)
> **Email:** [robert@rjgreenresearch.org](mailto:robert@rjgreenresearch.org)
> **ORCID:** [0009-0002-9097-1021](https://orcid.org/0009-0002-9097-1021)
> **SSRN:** [https://ssrn.com/author=10825096](https://ssrn.com/author=10825096)

Version 2.0 · March 2026

---

## 1. Purpose

The Report Generator produces research-grade markdown ownership chain summary reports from SECMap's CSV output. Each report provides a structured analysis of a single CIK's ownership chain including:

- Overall risk rating (CRITICAL / HIGH / ELEVATED / MODERATE / LOW) with composite scoring
- Supply chain vulnerability assessment (SIC → critical sector mapping with adversarial exposure alerts)
- AFIDA depth comparison (actual chain depth vs AFIDA's 2-3 layer self-reporting limit)
- ALL beneficial ownership entries from SC 13D/G filings (no truncation)
- ALL institutional relationships (no truncation)
- State-actor affiliation findings (SOE, MCF, UFWD, IRGC, etc.)
- Key personnel organized by role (executives, board, ownership roles, signatories)
- Obscuring-role flags indicating potential ownership layering
- Jurisdiction risk distribution across the five risk tiers
- Country associations grouped by risk tier
- Incorporation details with SIC classification
- Filing coverage (date range and form type breakdown)

Reports are designed for analyst review, research documentation, regulatory briefings, and inclusion in academic publications. The markdown format renders in GitHub, VS Code, Jupyter, and converts cleanly to PDF via pandoc.

---

## 2. Architecture

```
SECMap CSV Output (25-column, pipe-delimited)
    │
    ▼
┌──────────────────────────────────┐
│     Metadata Header Parser       │
│  (run_id, timestamp, root_cik)   │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│         CSV Row Loader           │
│  (skip # lines, parse fields)    │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│        Row Analyzer              │
│  - Classify by relationship type │
│  - Aggregate risk tiers          │
│  - Collect ALL persons, BO, inst │
│  - Identify state affiliations   │
│  - Flag obscuring roles          │
│  - Track chain depth             │
│  - Extract SIC → critical sector │
│  - Deduplicate within categories │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│       Risk Rating Engine         │
│  - Composite score (0-100)       │
│  - CRITICAL/HIGH/ELEVATED/       │
│    MODERATE/LOW rating           │
│  - Justification reasons         │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│      Markdown Report Writer      │
│  - Risk rating + justification   │
│  - Supply chain vulnerability    │
│  - AFIDA depth comparison        │
│  - Executive summary table       │
│  - Filing coverage               │
│  - Risk distribution table       │
│  - State affiliation table       │
│  - ALL beneficial owners table   │
│  - Personnel tables (4 groups)   │
│  - ALL institutions table        │
│  - Country associations by tier  │
│  - Relationship breakdown        │
│  - Author block + provenance     │
└──────────────────────────────────┘
               │
               ▼
          {cik}_report.md
```

---

## 3. Usage

> **Note:** Production and research runs prefix CSV filenames with the risk rating
> (e.g., `CRITICAL_cik_91388.csv`). The report generator handles these prefixed
> filenames transparently.

### 3.1 Single CSV File

```bash
python report_generator.py output/run_XXXX/per_cik/cik_91388.csv
```

Produces `cik_91388_report.md` in the same directory as the input file.

### 3.2 Entire Production Run

```bash
python report_generator.py output/run_XXXX/per_cik/
```

Processes all CSV files in the directory and writes reports to a `reports/` subdirectory. Skips files with no data rows.

### 3.3 Custom Output Directory

```bash
python report_generator.py output/run_XXXX/per_cik/ --out my_reports/
```

---

## 4. Command-Line Reference

```
python report_generator.py <input> [--out <directory>]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `input` | Yes | -- | Path to a CSV file or directory of CSV files |
| `--out` | No | Same as input (or `reports/` subdirectory for directories) | Output directory for generated reports |

---

## 5. Report Sections

### 5.1 Overall Risk Rating

A composite risk score (0-100) with a rating of CRITICAL, HIGH, ELEVATED, MODERATE, or LOW. Displayed with a color emoji indicator (🔴🟠🟡🔵🟢).

| Factor | Points | Condition |
|---|---|---|
| Adversarial jurisdictions | +40 | Any ADVERSARIAL-tier jurisdiction detected |
| State-actor affiliations (3+) | +25 | Three or more affiliated entities |
| State-actor affiliations (1-2) | +15 | One or two affiliated entities |
| Conduit jurisdictions | +10 | Any CONDUIT-tier jurisdiction detected |
| Opacity jurisdictions | +10 | Any OPACITY-tier jurisdiction detected |
| Obscuring roles | +10 | Any nominee, proxy, or intermediary roles |
| Critical sector | +10 | SIC code maps to a critical sector |
| Deep chain (5+ layers) | +5 | Ownership chain extends 5+ layers |

| Score Range | Rating |
|---|---|
| 60-100 | 🔴 CRITICAL |
| 40-59 | 🟠 HIGH |
| 25-39 | 🟡 ELEVATED |
| 10-24 | 🔵 MODERATE |
| 0-9 | 🟢 LOW |

### 5.2 Supply Chain Vulnerability Assessment

Maps the company's SIC code to critical sectors:

| Sector | SIC Ranges |
|---|---|
| Agriculture & Food | 100-999, 2000-2099 |
| Pharmaceuticals & Biotech | 2830-2836, 3841-3851 |
| Chemicals & Petrochemicals | 2800-2899, 2910-2999 |
| Semiconductors & Electronics | 3570-3579, 3660-3699 |
| Defense & Aerospace | 3720-3729, 3760-3769 |
| Energy & Utilities | 1300-1399, 4900-4999 |
| Telecommunications | 4800-4899 |
| Mining & Rare Earth | 1000-1499 |
| Financial Services | 6000-6799 |
| Transportation & Logistics | 4000-4799 |

When a critical sector entity has adversarial-nation ownership exposure, a **⚠ SUPPLY CHAIN ALERT** callout is generated.

### 5.3 AFIDA Depth Comparison

Compares the actual chain depth traced by SECMap against AFIDA's typical 2-3 layer self-reporting depth. The depth gap quantifies how many layers of ownership are invisible to USDA foreign investment screening. When a gap exists, an **AFIDA DISCLOSURE GAP** callout is generated.

### 5.4 Executive Summary

A table of key metrics at a glance: company name, CIK, total edges, unique entities, max chain depth, persons, beneficial owners, institutions, state-affiliated entities, obscuring roles, and adversarial/conduit/opacity jurisdictions.

### 5.5 Filing Coverage

Date range of filings analyzed and breakdown by form type (10-K, 20-F, SC 13D, SC 13G, etc.).

### 5.6 Jurisdiction Risk Distribution

Counts of edges touching each risk tier. A high ADVERSARIAL count indicates direct exposure to adversarial-nation entities. High CONDUIT counts suggest layered routing through intermediate jurisdictions.

### 5.7 Incorporation

Where the company is incorporated, with SIC code and industry description. State codes are mapped to full names.

### 5.8 State-Actor Affiliations

Table of entities matching state-actor affiliation keywords, with category, subcategory, and the specific keyword that triggered the match.

### 5.9 Beneficial Owners

ALL SC 13D/G reporting persons -- no truncation. Table includes jurisdiction, risk tier, state affiliation, and state affiliation subcategory columns to cross-reference beneficial owners against adversarial-nation indicators.

### 5.10 Key Personnel

Organized into four sub-tables:

- **Executives** -- CEO, CFO, COO, VP, and other C-suite/senior roles
- **Board Members** -- Directors, Chairman, Lead Independent Director
- **Ownership Roles** -- Beneficial owners, controlling persons, significant shareholders
- **Other Signatories** -- Filing signatories without a classified role

Each table includes jurisdiction, risk tier, and state affiliation columns.

### 5.11 Institutional Relationships

ALL institutional entities -- no truncation. Table includes jurisdiction, risk tier, and state affiliation to identify adversarial-linked institutions.

### 5.12 Obscuring Roles

Entities flagged with the `role_is_obscuring` flag -- nominees, proxies, intermediaries, registered agents. These indicate potential ownership layering or opacity in the chain.

### 5.13 Country Associations

Countries mentioned in filings, grouped by risk tier (ADVERSARIAL, CONDUIT, OPACITY, MONITORED, STANDARD).

### 5.14 Relationship Breakdown

Count of edges by relationship type.

---

## 6. Integration with SECMap Pipeline

### 6.1 Production Run → Reports

```bash
python run_production.py
python report_generator.py output/run_XXXX/per_cik/
```

### 6.2 Research Run → Reports

```bash
python run_research.py --exchange OTC --limit 50
python report_generator.py output/research/XXXX/per_cik/ --out output/research/XXXX/reports/
```

### 6.3 Single Investigation → Report + Visualization

```bash
secmap run --cik 91388 --forms 10-K SC\ 13D SC\ 13G --depth 10 --limit 50 --out smithfield.csv
python report_generator.py smithfield.csv
python network_visualizer.py smithfield.csv --cik 91388 --root "SMITHFIELD FOODS INC" --fmt pdf
```

### 6.4 Converting to PDF

```bash
pandoc cik_91388_report.md -o cik_91388_report.pdf
```

---

## 7. Example Output

For Smithfield Foods (CIK 91388), the v2.0 report shows:

- **🔴 CRITICAL risk rating** (score 75/100)
- **Supply chain alert:** Agriculture & Food sector with China/Russia exposure
- **353 total edges** across 169 unique entities
- **Adversarial jurisdictions:** China, Russia
- **Conduit jurisdictions:** Hong Kong
- **38 persons identified** including Long Wan (Chairman), C. Shane Smith (CEO), and Chinese directors Lijun Guo, Hank Shenghua He, Hongwei Wan, Xiaoming Zhou
- **10 beneficial ownership entries** (all shown, no truncation)
- **102 institutional relationships** (all shown, no truncation) including WH Group and Starboard Value
- **Incorporated in:** Virginia (SIC 2011: Meat Packing Plants)
- **Filing coverage:** 2011-2026 across 10-K, SC 13D/A, SC 13G/A

This immediately surfaces the PRC ownership chain: Smithfield → WH Group Limited → Shuanghui International Holdings → ultimately Chinese state interests, operating in a critical agricultural supply chain sector.

---

## 8. Dependencies

No additional dependencies beyond Python standard library. The report generator reads the same CSV files produced by SECMap's `csv_writer.py`.

---

## 9. Limitations

- Reports reflect the data quality of the underlying CSV. SC-13 parser noise in older filings may appear in the Beneficial Owners section.
- The `Max Chain Depth` metric only reflects the depth reached in the current run. A depth-0 run shows 0 even if deeper chains exist.
- The supply chain vulnerability assessment uses SIC code ranges which may not capture all relevant entities (e.g., a holding company with SIC 6726 that controls agricultural subsidiaries).
- Risk scores are heuristic and should be validated by analyst review. A LOW score does not guarantee absence of adversarial ownership.
- Institution names may include sentence fragments from the institution extractor in older filing formats.

---

## 10. License

Apache 2.0 License. See `LICENSE` file in the project root.
