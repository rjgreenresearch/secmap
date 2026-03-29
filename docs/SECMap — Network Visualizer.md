# SECMap — Network Visualizer

> **Author:** Robert J. Green
> **Web:** [www.rjgreenresearch.org](https://www.rjgreenresearch.org)
> **Email:** [robert@rjgreenresearch.org](mailto:robert@rjgreenresearch.org)
> **ORCID:** [0009-0002-9097-1021](https://orcid.org/0009-0002-9097-1021)
> **SSRN:** [https://ssrn.com/author=10825096](https://ssrn.com/author=10825096)

Version 2.0 · March 2026

---

## 1. Purpose

The Network Visualizer generates hierarchical ownership chain diagrams from SECMap's pipe-delimited CSV output. It produces both static publication-quality graphics (PDF, SVG, PNG via Graphviz) and interactive HTML explorations (via PyVis), enabling analysts and researchers to visually trace beneficial ownership chains across corporate structures, jurisdictions, and adversarial-nation boundaries.

The visualizer is designed to consume the 25-column CSV output from any SECMap execution mode — single-CIK runs, production batch runs, or research-scale exchange scans — and render the ownership graph with typed nodes, colored edges, depth-based subgraphs, and embedded metadata provenance.

---

## 2. Architecture

```
SECMap CSV Output (25-column, pipe-delimited)
    │
    ▼
┌──────────────────────────────────┐
│     Metadata Header Parser       │
│  (run_id, timestamp, root_cik,   │
│   tool_version)                  │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│        Graph Builder             │
│  - Typed nodes (company, person, │
│    country, institution)         │
│  - Labeled edges (relationship + │
│    detail)                       │
│  - Adjacency index for BFS      │
└──────────────┬───────────────────┘
               │
        ┌──────┴──────┐
        │             │
        ▼             ▼
┌──────────────┐ ┌──────────────┐
│   Graphviz   │ │    PyVis     │
│  (static)    │ │ (interactive)│
│              │ │              │
│ - PDF/SVG/PNG│ │ - HTML       │
│ - Clustered  │ │ - Hierarchical│
│   by type    │ │   layout     │
│ - Paginated  │ │ - Hover info │
│ - Legend     │ │ - Zoom/pan   │
│ - Methods    │ │ - Methods    │
│   footer     │ │   footer     │
└──────────────┘ └──────────────┘
```

### 2.1 Components

| Component | Purpose |
|---|---|
| **Metadata Parser** | Reads the `#`-prefixed header lines from SECMap CSV to extract run provenance (run ID, timestamp, root CIK, tool version). Embedded in all output for traceability. |
| **Graph Builder** | Parses the CSV data rows into a typed directed graph. Nodes are classified by `source_type` / `target_type` (company, person, country, institution). Edges carry the relationship type and detail as labels. |
| **Subgraph Extractor** | Given a root node and depth, performs BFS to extract a depth-bounded subgraph. Enables layered visualization — depth 1 shows direct relationships, depth 2 shows one hop further, etc. |
| **Graphviz Renderer** | Produces publication-quality static diagrams using the Graphviz DOT engine. Nodes are clustered by type (companies, people, countries). Output is paginated for large graphs. Includes a legend and methods footer. |
| **PyVis Renderer** | Produces interactive HTML visualizations using the PyVis library. Hierarchical top-down layout with hover tooltips, zoom, and pan. Includes an HTML header with run metadata and a methods footer describing the extraction methodology. |

### 2.2 Node Types and Colors

| Node Type | Color | Shape (Graphviz) | Description |
|---|---|---|---|
| **Company** | Blue (`#3498DB`) | Box | SEC-registered companies, subsidiaries, holding entities |
| **Person** | Purple (`#9B59B6`) | Ellipse | Directors, officers, beneficial owners, signatories |
| **Country** | Green (`#2ECC71`) | Diamond | Jurisdictions, countries, states of incorporation |
| **Institution** | Gray (`#AAAAAA`) | Box | Financial institutions, funds, registered agents |

### 2.3 Edge Types

| Relationship | Description | Visual Style |
|---|---|---|
| `person_role` | Person → Company with role title (CEO, Director, etc.) | Standard arrow |
| `institution_role` | Institution → Company with role | Standard arrow |
| `beneficial_owner` | Reporting person → Issuer with ownership percentage | Standard arrow |
| `incorporated_in` | Company → Jurisdiction with SIC description | Standard arrow |
| `country_association` | Company → Country mentioned in filing | Standard arrow |
| `wholly_owned_subsidiary` | Parent → Subsidiary (if detected) | **Bold** arrow |

---

## 3. Installation

### 3.1 Required Dependencies

```bash
pip install pandas graphviz pyvis
```

### 3.2 Graphviz System Package

The Graphviz Python package requires the Graphviz system binaries:

- **Windows:** Download from [graphviz.org/download](https://graphviz.org/download/) and add to PATH
- **macOS:** `brew install graphviz`
- **Linux:** `apt install graphviz` or `yum install graphviz`

### 3.3 Optional (for matplotlib-based rendering)

```bash
pip install matplotlib networkx
```

---

## 4. Usage

### 4.1 Basic Usage

```bash
# Generate full network diagram from a single-CIK run
python network_visualizer.py output/run_XXXX/per_cik/cik_91388.csv \
    --cik 91388 --fmt pdf
```

This produces:
- `91388_network_graphviz.pdf` — Static paginated diagram
- `91388_network_full.html` — Interactive HTML visualization

### 4.2 Depth-Layered Visualization

```bash
# Generate depth-1 and depth-2 subgraphs rooted at a specific entity
python network_visualizer.py output/run_XXXX/per_cik/cik_1123661.csv \
    --cik 1123661 \
    --root "SYNGENTA AG" \
    --depth1 1 \
    --depth2 3 \
    --fmt svg
```

This produces:
- `1123661_network_graphviz.svg` — Full network (static)
- `1123661_network_depth1.html` — Direct relationships only (interactive)
- `1123661_network_depth3.html` — Three hops from root (interactive)
- `1123661_network_full.html` — Complete network (interactive)

### 4.3 Combined Output Visualization

```bash
# Visualize the combined output from a production or research run
python network_visualizer.py output/run_XXXX/combined.csv \
    --cik combined --fmt png
```

### 4.4 Output Format Options

| Format | Flag | Engine | Use Case |
|---|---|---|---|
| PDF | `--fmt pdf` | Graphviz | Publication, print, multi-page |
| SVG | `--fmt svg` | Graphviz | Web embedding, scalable |
| PNG | `--fmt png` | Graphviz | Presentations, reports |
| HTML | (always produced) | PyVis | Interactive exploration, briefings |

---

## 5. Command-Line Reference

```
python network_visualizer.py <input_csv> [options]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `input` | Yes | — | Path to SECMap CSV file (pipe-delimited, with metadata header) |
| `--cik` | No | `network` | CIK or label used as output filename prefix |
| `--root` | No | None | Root node label for depth-bounded subgraphs. Must match an entity name exactly as it appears in the CSV `source` or `target` column. |
| `--depth1` | No | `1` | Depth for the first subgraph layer (direct relationships) |
| `--depth2` | No | `2` | Depth for the second subgraph layer |
| `--fmt` | No | `pdf` | Static output format: `pdf`, `svg`, or `png` |

---

## 6. Input Format

The visualizer reads SECMap's standard 25-column pipe-delimited CSV. The columns it uses:

| Column | Used For |
|---|---|
| `source` | Source node label |
| `source_type` | Node type classification (company, person, country, institution) |
| `target` | Target node label |
| `target_type` | Node type classification |
| `relationship` | Edge type label |
| `detail` | Edge detail (appended to relationship label) |

The metadata header lines (prefixed with `#`) are parsed for run provenance:

```
# SECMap CSV Output
# Generated: 2026-03-27T15:17:30.123456 UTC
# Root CIK: 91388
# Delimiter: |
```

---

## 7. Output Files

For a run with `--cik 91388 --root "SMITHFIELD FOODS INC" --depth1 1 --depth2 3 --fmt pdf`:

| File | Type | Description |
|---|---|---|
| `91388_network_graphviz.pdf` | Static | Full network, clustered by node type, paginated, with legend and methods footer |
| `91388_network_depth1.html` | Interactive | Direct relationships from root only |
| `91388_network_depth3.html` | Interactive | Three hops from root |
| `91388_network_full.html` | Interactive | Complete network with all nodes and edges |

### 7.1 Graphviz Output Features

- **Clustered layout** — Nodes grouped into Companies, People, Countries, Other
- **Typed shapes** — Boxes for companies, ellipses for people, diamonds for countries
- **Color-coded** — Blue/purple/green/gray by node type
- **Paginated** — Large graphs split across 8.5×11 pages for printing
- **Legend** — Color/shape key embedded in the diagram
- **Methods footer** — Run ID, timestamp, tool version for provenance

### 7.2 PyVis Output Features

- **Hierarchical layout** — Top-down directed layout showing ownership flow
- **Interactive** — Zoom, pan, drag nodes, hover for tooltips
- **Hover tooltips** — Show node name and type on hover
- **HTML header** — Run metadata, node color key
- **Methods footer** — Full methodology description embedded in the HTML

---

## 8. Integration with SECMap Pipeline

### 8.1 Single-CIK Workflow

```bash
# Step 1: Run SECMap
secmap run --cik 91388 --forms 10-K SC\ 13D SC\ 13G --depth 10 --limit 50 --out smithfield.csv

# Step 2: Visualize
python network_visualizer.py smithfield.csv \
    --cik 91388 --root "SMITHFIELD FOODS INC" --depth1 1 --depth2 3 --fmt pdf
```

### 8.2 Production Run Workflow

```bash
# Step 1: Run production batch
python run_production.py

# Step 2: Visualize each CIK
for f in output/run_XXXX/per_cik/cik_*.csv; do
    cik=$(basename $f .csv | sed 's/cik_//')
    python network_visualizer.py $f --cik $cik --fmt svg
done

# Step 3: Visualize combined
python network_visualizer.py output/run_XXXX/combined.csv --cik combined --fmt pdf
```

### 8.3 Research-Scale Workflow

```bash
# Step 1: Run research scan
python run_research.py --exchange OTC --limit 100

# Step 2: Visualize high-risk CIKs identified in results.json
python network_visualizer.py output/research/XXXX/per_cik/cik_1123658.csv \
    --cik 1123658 --root "CHINA PETROLEUM & CHEMICAL CORP" --depth1 2 --depth2 5 --fmt pdf
```

---

## 9. Interpreting the Output

### 9.1 Reading the Graph

- **Top-down flow** represents ownership/control direction (owner → owned)
- **Blue boxes** are companies — follow the chain upward to find the ultimate controller
- **Purple ellipses** are people — directors, officers, beneficial owners
- **Green diamonds** are jurisdictions — show where entities are incorporated or associated
- **Bold edges** indicate wholly-owned subsidiary relationships (strongest control)
- **Edge labels** show the relationship type and detail (e.g., `beneficial_owner (5.2% of Common Stock)`)

### 9.2 Identifying Adversarial Ownership Chains

Look for patterns like:
1. A chain of blue boxes leading from a US company upward through CONDUIT jurisdictions (Hong Kong, Singapore, Cyprus) to an ADVERSARIAL jurisdiction (China, Russia)
2. Purple ellipses with Deputy titles (Deputy Director, Deputy General Manager) — common in PRC state-controlled entities
3. Green diamonds showing incorporation in OPACITY jurisdictions (Cayman Islands, BVI) as intermediate layers
4. Edge labels showing `beneficial_owner` with large percentages flowing to foreign entities

### 9.3 The Syngenta AG Example

A visualization of CIK 1123661 (Syngenta AG) would show:

```
SASAC (PRC State Council) [green diamond - ADVERSARIAL]
    │
    ▼ beneficial_owner
China National Chemical Corp [blue box]
    │
    ▼ subsidiary
ChemChina Holdings [blue box]
    │
    ▼ subsidiary
CNAC Saturn BV [blue box - Netherlands, STANDARD]
    │
    ▼ beneficial_owner
SYNGENTA AG [blue box - Switzerland, STANDARD]
    │
    ├── person_role (Director) ──▶ [purple ellipses]
    ├── incorporated_in ──▶ Switzerland [green diamond]
    └── country_association ──▶ China, US, UK [green diamonds]
```

This chain is 5+ layers deep — invisible to AFIDA's 2-3 layer self-reporting requirement.

---

## 10. Dependencies

| Package | Version | Purpose |
|---|---|---|
| pandas | ≥ 1.5 | CSV parsing |
| graphviz | ≥ 0.20 | Static diagram rendering (requires system Graphviz) |
| pyvis | ≥ 0.3 | Interactive HTML visualization |

Install all:

```bash
pip install pandas graphviz pyvis
```

---

## 11. Limitations

- **Large graphs** (1000+ nodes) may render slowly in Graphviz and produce cluttered layouts. Use `--root` with depth bounds to focus on specific chains.
- **Node label overlap** is possible in dense graphs. SVG output allows post-processing in vector editors.
- **PyVis hierarchical layout** works best for tree-like structures. Highly interconnected graphs may benefit from physics-enabled layout (edit the `set_options` call).
- **The visualizer reads the CSV as-is** — it does not re-fetch from SEC or re-classify entities. All risk tiers, state affiliations, and role flags come from the SECMap pipeline output.

---

## 12. License

Apache 2.0 License. See `LICENSE` file in the project root.
