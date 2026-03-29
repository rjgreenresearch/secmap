# SECMap — System Block Diagram
Version 2.0 — Patent‑Grade

> **Author:** Robert J. Green
> **Web:** [www.rjgreenresearch.org](https://www.rjgreenresearch.org)
> **Email:** [robert@rjgreenresearch.org](mailto:robert@rjgreenresearch.org)
> **ORCID:** [0009-0002-9097-1021](https://orcid.org/0009-0002-9097-1021)
> **SSRN:** [https://ssrn.com/author=10825096](https://ssrn.com/author=10825096)


ASCII Block Diagram

```
+-----------------------------------------------------------------------+
|                          SECMap System v2.0                            |
+-----------------------------------------------------------------------+
|                                                                       |
|  +------------------+      +------------------+                       |
|  |  Config Layer    |      | Logging Layer    |                       |
|  |  (3-layer:       |      | (console + file) |                       |
|  |  defaults/env/   |      +------------------+                       |
|  |  CLI, max depth  |                                                 |
|  |  ceiling = 10)   |                                                 |
|  +------------------+                                                 |
|           |                                                           |
|           v                                                           |
|  +-----------------------------------------------------------------+  |
|  |              Pipeline Orchestrator (ownership_mapper)           |  |
|  +-----------------------------------------------------------------+  |
|           |                                                           |
|  =========|===========================================================|
|  | LAYER 1: FETCH & CACHE                                         |  |
|  |  +------------------+      +-------------------------------+   |  |
|  |  | SEC Fetch        | ---> | Disk Cache                    |   |  |
|  |  | (rate limited,   |      | (URL → filepath mapping,      |   |  |
|  |  |  retry + backoff)|      |  offline operation)            |   |  |
|  |  +------------------+      +-------------------------------+   |  |
|  =================================================================|  |
|           |                                                           |
|  =========|===========================================================|
|  | LAYER 2: DISCOVERY                                             |  |
|  |  +------------------+      +-------------------------------+   |  |
|  |  | CIK Discovery    |      | Company Metadata              |   |  |
|  |  | (BFS, depth 10,  | ---> | (name, SIC, state of inc.,    |   |  |
|  |  |  CIK extraction) |      |  incorporated_in edges)        |   |  |
|  |  +------------------+      +-------------------------------+   |  |
|  =================================================================|  |
|           |                                                           |
|  =========|===========================================================|
|  | LAYER 3: PARSE & EXTRACT                                      |  |
|  |  +------------------+      +-------------------------------+   |  |
|  |  | Filing Parser    | ---> | Section Extraction            |   |  |
|  |  | (HTML/XBRL strip)|      | (full_text, sigs, narrative)  |   |  |
|  |  +------------------+      +-------------------------------+   |  |
|  |           |                         |                          |  |
|  |           v                         v                          |  |
|  |  +------------------+      +-------------------------------+   |  |
|  |  | People Extractor |      | Institution Extractor         |   |  |
|  |  | (positional /s/, |      | (corporate suffix patterns,   |   |  |
|  |  |  By:, Name+age,  |      |  length cap, fragment reject) |   |  |
|  |  |  title adjacency)|      +-------------------------------+   |  |
|  |  +------------------+                                          |  |
|  |           |                                                    |  |
|  |           v                                                    |  |
|  |  +------------------+                                          |  |
|  |  | SC-13 Parser     |                                          |  |
|  |  | (cover page      |                                          |  |
|  |  |  structure, IRS  |                                          |  |
|  |  |  ID skip, name   |                                          |  |
|  |  |  validation)     |                                          |  |
|  |  +------------------+                                          |  |
|  =================================================================|  |
|           |                                                           |
|  =========|===========================================================|
|  | LAYER 4: CLASSIFICATION & RISK                                 |  |
|  |  +------------------+  +----------------+  +-----------------+ |  |
|  |  | Jurisdiction     |  | State-Actor    |  | Role            | |  |
|  |  | Inference        |  | Affiliation    |  | Taxonomy        | |  |
|  |  | (5 risk tiers,   |  | (PRC/RU/IR/KP, |  | (50+ roles,     | |  |
|  |  |  135+ countries, |  |  SWF, Shell,   |  |  Deputy {X},    | |  |
|  |  |  city tokens)    |  |  PEP)          |  |  semantic flags, | |  |
|  |  +------------------+  +----------------+  |  word boundary)  | |  |
|  |                                             +-----------------+ |  |
|  =================================================================|  |
|           |                                                           |
|  =========|===========================================================|
|  | LAYER 5: EDGE CONSTRUCTION & OUTPUT                            |  |
|  |  +------------------+      +-------------------------------+   |  |
|  |  | Relationship     | ---> | Ownership Edges               |   |  |
|  |  | Builder          |      | (25-field dataclass,          |   |  |
|  |  +------------------+      |  jurisdiction, risk tier,     |   |  |
|  |                             |  state affiliation, flags)    |   |  |
|  |                             +-------------------------------+   |  |
|  |                                      |                          |  |
|  |                                      v                          |  |
|  |                             +-------------------------------+   |  |
|  |                             | Deduplication                 |   |  |
|  |                             | (deterministic merge)         |   |  |
|  |                             +-------------------------------+   |  |
|  |                                      |                          |  |
|  |                                      v                          |  |
|  |  +------------------+      +-------------------------------+   |  |
|  |  | Metadata +       | ---> | CSV Writer                    |   |  |
|  |  | Chain Summary     |      | (25 columns, pipe-delimited,  |   |  |
|  |  | (adversarial/     |      |  metadata header, column hdr) |   |  |
|  |  |  conduit/opacity  |      +-------------------------------+   |  |
|  |  |  counts)          |                                          |  |
|  |  +------------------+                                          |  |
|  =================================================================|  |
|           |                                                           |
|  =========|===========================================================|
|  | LAYER 6: RESEARCH & GAP ANALYSIS                              |  |
|  |  +------------------+  +----------------+  +-----------------+ |  |
|  |  | SEC Universe     |  | State SOS      |  | Gap Analyzer    | |  |
|  |  | (10,438 cos,     |  | Registry       |  | (fed vs state,  | |  |
|  |  |  28,183 funds,   |  | (51 states,    |  |  risk scoring,  | |  |
|  |  |  exchange filter) |  |  access tiers) |  |  incremental,   | |  |
|  |  +------------------+  +----------------+  |  persistence)   | |  |
|  |                                             +-----------------+ |  |
|  |  +------------------+  +----------------+                      |  |
|  |  | Research Runner  |  | Texas SOS      |                      |  |
|  |  | (batch, resume,  |  | PDF Parser     |                      |  |
|  |  |  progress, ETA)  |  +----------------+                      |  |
|  |  +------------------+                                          |  |
|  =================================================================|  |
|                                                                       |
+-----------------------------------------------------------------------+
```


Description for Patent Application

The system architecture comprises six processing layers coordinated by a pipeline orchestrator:

Layer 1 (Fetch & Cache) retrieves regulatory filings from SEC EDGAR with rate limiting and disk‑based caching, enabling offline operation.

Layer 2 (Discovery) performs breadth‑first recursive CIK traversal to a depth of ten layers, collecting company metadata and constructing incorporated_in edges.

Layer 3 (Parse & Extract) transforms filings into structured sections and extracts entities using positional patterns for persons, corporate suffix patterns for institutions, and cover page structure parsing for SC‑13 beneficial ownership.

Layer 4 (Classification & Risk) classifies every entity by five‑tier jurisdiction risk, multi‑nation state‑actor affiliation, and semantic role flags including an obscuring indicator for layered ownership.

Layer 5 (Edge Construction & Output) generates 25‑field typed edges, deduplicates deterministically, computes chain analysis summaries, and produces reproducible pipe‑delimited CSV artifacts.

Layer 6 (Research & Gap Analysis) ingests the complete SEC filing universe for research‑scale batch execution and bridges the federal/state visibility gap through state SOS integration with incremental ingestion and risk‑scored gap identification.
