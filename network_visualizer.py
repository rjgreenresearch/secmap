#!/usr/bin/env python3
"""
Ownership Network Visualizer — v2
Layered, paged, typed, with legend and methods footer.

- Reads clean CSV from ownership_mapper_v4.2 (with metadata header)
- Builds typed graph (company/person/country/other)
- Graphviz PDF/SVG/PNG with pagination + legend + header
- PyVis HTML for depth1, depth2, full, with header + methods footer

Usage:
    python network_viz_v2.py 1123661_ownership_network_clean.csv \
        --cik 1123661 --root "Syngenta AG" --depth1 1 --depth2 2 --fmt pdf
"""

import os
import sys
import argparse
import pandas as pd
import graphviz
from pyvis.network import Network
from collections import defaultdict, deque
from datetime import datetime

# -------------------------------------------------------------------
# Metadata header parser
# -------------------------------------------------------------------

def parse_metadata_header(path):
    meta = {}
    with open(path, "r", encoding="utf-8") as f:
        line = f.readline()
        while line.startswith("#"):
            line = line.lstrip("#").strip()
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
            line = f.readline()

    # Defaults if missing
    meta.setdefault("run_id", "unknown")
    meta.setdefault("timestamp", datetime.now().isoformat(timespec="seconds"))
    meta.setdefault("tool_version", "Ownership Mapper v4.2")
    meta.setdefault("root_cik", "unknown")
    return meta

# -------------------------------------------------------------------
# Graph helpers
# -------------------------------------------------------------------

def gv_escape(s: str) -> str:
    if s is None:
        return ""
    s = str(s)
    s = s.replace("\\", "\\\\").replace("\"", "\\\"")
    return f"\"{s}\""

def sanitize_id(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    safe = []
    for ch in s:
        if ch.isalnum() or ch in "_":
            safe.append(ch)
        else:
            safe.append("_")
    return "".join(safe)

def load_graph(csv_path):
    df = pd.read_csv(csv_path, comment="#", delimiter="|")

    nodes = {}
    edges = []

    for _, row in df.iterrows():
        src = str(row.get("source","")).strip()
        tgt = str(row.get("target","")).strip()
        if not src or not tgt:
            continue

        src_type = str(row.get("source_type","other")).strip().lower() or "other"
        tgt_type = str(row.get("target_type","other")).strip().lower() or "other"
        rel = str(row.get("relationship","")).strip()
        detail = str(row.get("relationship_detail","")).strip()

        if src not in nodes:
            nodes[src] = {"type": src_type}
        if tgt not in nodes:
            nodes[tgt] = {"type": tgt_type}

        label = rel
        if detail:
            label = f"{rel} ({detail})"

        edges.append((src, tgt, label))

    return {"nodes": nodes, "edges": edges}

def build_adjacency(G):
    adj = defaultdict(list)
    for src, tgt, _ in G["edges"]:
        adj[src].append(tgt)
        adj[tgt].append(src)
    return adj

def subgraph_from_root(G, root, depth):
    if root not in G["nodes"]:
        return G

    adj = build_adjacency(G)
    visited = set([root])
    q = deque([(root, 0)])
    keep = set([root])

    while q:
        node, d = q.popleft()
        if d >= depth:
            continue
        for nb in adj[node]:
            if nb not in visited:
                visited.add(nb)
                keep.add(nb)
                q.append((nb, d+1))

    nodes = {n: G["nodes"][n] for n in keep}
    edges = [(s,t,l) for (s,t,l) in G["edges"] if s in keep and t in keep]
    return {"nodes": nodes, "edges": edges}

# -------------------------------------------------------------------
# Graphviz rendering
# -------------------------------------------------------------------

def render_graphviz(G, meta, cik, depth, fmt="pdf"):
    outname = f"{cik}_network_graphviz.{fmt}"

    run_id = meta.get("run_id","unknown")
    ts = meta.get("timestamp","")
    label = f"Ownership Network — {cik}\\nRun ID: {run_id} | {ts}\\nDepth: {depth}"

    dot = graphviz.Digraph(
        name=f"OwnershipNetwork_{cik}",
        format=fmt,
        graph_attr={
            "rankdir": "TB",
            "splines": "true",
            "overlap": "false",
            "labelloc": "t",
            "labeljust": "c",
            "fontsize": "10",
            "fontname": "Helvetica",
            "page": "8.5,11",
            "pagedir": "BL",
            "ratio": "compress",
            "label": label,
        },
        node_attr={
            "shape": "box",
            "style": "filled",
            "fontname": "Helvetica",
            "fontsize": "9",
        },
        edge_attr={
            "fontsize": "8",
            "fontname": "Helvetica",
        }
    )

    # clusters by type
    clusters = {
        "company": graphviz.Digraph(name="cluster_companies"),
        "person": graphviz.Digraph(name="cluster_people"),
        "country": graphviz.Digraph(name="cluster_countries"),
        "other": graphviz.Digraph(name="cluster_other"),
    }
    clusters["company"].attr(label="Companies")
    clusters["person"].attr(label="People")
    clusters["country"].attr(label="Countries")
    clusters["other"].attr(label="Other")

    for node, data in G["nodes"].items():
        ntype = data.get("type","other")
        color = {
            "company": "#3498DB",
            "person": "#9B59B6",
            "country": "#2ECC71",
            "other": "#AAAAAA",
        }.get(ntype, "#AAAAAA")
        shape = {
            "company": "box",
            "person": "ellipse",
            "country": "diamond",
            "other": "box",
        }.get(ntype, "box")

        node_id = sanitize_id(node)
        label = gv_escape(node)

        clusters.get(ntype, clusters["other"]).node(
            node_id, label=label, fillcolor=color, shape=shape, fontcolor="white"
        )

    for c in clusters.values():
        dot.subgraph(c)

    # legend
    legend = graphviz.Digraph(name="cluster_legend")
    legend.attr(label="Legend", fontsize="10")

    def legend_node(name, label, color, shape):
        legend.node(name, label=label, shape=shape, style="filled",
                    fillcolor=color, fontcolor="white")

    legend_node("leg_company", "Company", "#3498DB", "box")
    legend_node("leg_person", "Person", "#9B59B6", "ellipse")
    legend_node("leg_country", "Country", "#2ECC71", "diamond")
    legend_node("leg_other", "Other", "#AAAAAA", "box")

    dot.subgraph(legend)

    # edges
    for src, tgt, rel in G["edges"]:
        src_id = sanitize_id(src)
        tgt_id = sanitize_id(tgt)
        elabel = gv_escape(rel[:60])
        style = "bold" if "wholly" in rel.lower() else "solid"
        dot.edge(src_id, tgt_id, label=elabel, color="#555555", style=style)

    # methods footer
    dot.node(
        "methods_footer",
        label=f"Methods: Ownership Mapper v4.2 / Visualizer v2\\nRun ID: {run_id}",
        shape="note",
        fontsize="8",
        color="#888888"
    )

    dot.render(outname, cleanup=True)
    print(f"✔ Graphviz rendered → {outname}")

# -------------------------------------------------------------------
# PyVis rendering
# -------------------------------------------------------------------

def render_pyvis(G, meta, cik, suffix, root=None, depth=None):
    outname = f"{cik}_network_{suffix}.html"

    run_id = meta.get("run_id","unknown")
    ts = meta.get("timestamp","")
    root_cik = meta.get("root_cik","")
    tool_version = meta.get("tool_version","Ownership Mapper v4.2")

    net = Network(
        height="900px",
        width="100%",
        directed=True,
        bgcolor="#FFFFFF",
        font_color="black"
    )

    net.toggle_physics(False)
    net.hierarchical_layout(direction="UD", sort_method="directed")

    for node, data in G["nodes"].items():
        ntype = data.get("type","other")
        color = {
            "company": "#3498DB",
            "person": "#9B59B6",
            "country": "#2ECC71",
            "other": "#AAAAAA",
        }.get(ntype, "#AAAAAA")

        net.add_node(
            sanitize_id(node),
            label=node,
            color=color,
            title=f"{node} ({ntype})"
        )

    for src, tgt, rel in G["edges"]:
        net.add_edge(sanitize_id(src), sanitize_id(tgt), title=rel)

    # options
    net.set_options("""
    var options = {
      layout: {
        hierarchical: {
          enabled: true,
          direction: "UD",
          sortMethod: "directed"
        }
      },
      physics: {
        enabled: false
      }
    }
    """)

    # header + methods footer
    depth_str = f"{depth}" if depth is not None else "full"
    header = f"""
    <h2>Ownership Network — {cik} ({suffix})</h2>
    <p>Run ID: {run_id} | {ts} | Root CIK: {root_cik} | Depth: {depth_str}</p>
    <p>Node colors: Companies (blue), People (purple), Countries (green), Other (gray).</p>
    """

    methods_footer = f"""
    <hr>
    <h3>Methods</h3>
    <p>This visualization was generated using Ownership Mapper v4.2 and Ownership Network Visualizer v2.
    Data was extracted from SEC EDGAR filings and normalized into a typed ownership graph to support
    research on multi-layered ownership structures, AFIDA-related land transactions, and critical
    supply chain risk analysis in food, chemical, pharmaceutical, and petrochemical sectors.</p>
    <p>Run ID: {run_id}, Timestamp: {ts}, Root CIK: {root_cik}, Depth: {depth_str}, Tool: {tool_version}.</p>
    """

    net.html = header + (net.html or "") + methods_footer

    net.write_html(outname, open_browser=False, notebook=False)
    print(f"✔ PyVis interactive HTML → {outname}")

# -------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Ownership Network Visualizer v2")
    parser.add_argument("input", help="Clean input CSV (from v4.2 mapper)")
    parser.add_argument("--cik", help="CIK or label for output prefix", default="network")
    parser.add_argument("--root", help="Root node label for depth subgraphs", default=None)
    parser.add_argument("--depth1", type=int, default=1)
    parser.add_argument("--depth2", type=int, default=2)
    parser.add_argument("--fmt", default="pdf", choices=["pdf","svg","png"])
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: File not found → {args.input}")
        sys.exit(1)

    meta = parse_metadata_header(args.input)
    G = load_graph(args.input)
    print(f"Nodes: {len(G['nodes'])} | Edges: {len(G['edges'])}")

    # Full graphviz (paged)
    render_graphviz(G, meta, args.cik, depth="full", fmt=args.fmt)

    # PyVis layers
    if args.root and args.root in G["nodes"]:
        G1 = subgraph_from_root(G, args.root, args.depth1)
        G2 = subgraph_from_root(G, args.root, args.depth2)
        render_pyvis(G1, meta, args.cik, f"depth{args.depth1}", root=args.root, depth=args.depth1)
        render_pyvis(G2, meta, args.cik, f"depth{args.depth2}", root=args.root, depth=args.depth2)
    else:
        if args.root:
            print(f"Root node '{args.root}' not found; skipping depth subgraphs.")
        else:
            print("No root specified; skipping depth subgraphs.")

    render_pyvis(G, meta, args.cik, "full", depth=None)

    print("Done.")

if __name__ == "__main__":
    main()