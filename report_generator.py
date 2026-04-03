#!/usr/bin/env python3
"""
report_generator.py — v2.0

Generates research-grade ownership chain summary reports from SECMap
CSV output. Produces per-CIK markdown reports with:

- Overall risk rating (CRITICAL / HIGH / ELEVATED / MODERATE / LOW)
- Supply chain vulnerability assessment (SIC → critical sector mapping)
- Ownership chain narrative (root → terminus path description)
- AFIDA depth comparison (actual depth vs AFIDA's 2-3 layer limit)
- ALL beneficial owners (no truncation)
- ALL institutional relationships (no truncation)
- State-actor affiliation findings
- Key personnel organized by role
- Obscuring-role flags
- Jurisdiction risk distribution
- Country associations
- Temporal filing coverage

Usage:
    python report_generator.py output/run_XXXX/per_cik/cik_91388.csv
    python report_generator.py output/run_XXXX/per_cik/
    python report_generator.py output/run_XXXX/per_cik/ --out reports/
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List


# ---------------------------------------------------------------------------
# Critical sector mapping (SIC code ranges → sector)
# ---------------------------------------------------------------------------

CRITICAL_SECTORS = {
    "Agriculture & Food": [
        (100, 999), (2000, 2099), (2010, 2099), (5140, 5159),
    ],
    "Pharmaceuticals & Biotech": [
        (2830, 2836), (2860, 2869), (3841, 3851), (5122, 5122),
        (8731, 8734),
    ],
    "Chemicals & Petrochemicals": [
        (2800, 2829), (2840, 2899), (2910, 2999),
    ],
    "Semiconductors & Electronics": [
        (3559, 3559), (3570, 3579), (3660, 3699), (3674, 3674),
        (3710, 3799),
    ],
    "Defense & Aerospace": [
        (3720, 3729), (3760, 3769), (3812, 3812), (3761, 3769),
    ],
    "Energy & Utilities": [
        (1300, 1399), (2900, 2912), (4900, 4999),
    ],
    "Telecommunications": [
        (4800, 4899), (3669, 3669),
    ],
    "Mining & Rare Earth": [
        (1000, 1499),
    ],
    "Financial Services": [
        (6000, 6799),
    ],
    "Transportation & Logistics": [
        (4000, 4799),
    ],
}


def classify_sector(sic_str: str) -> List[str]:
    """Map a SIC code to critical sector(s)."""
    try:
        sic = int(sic_str.strip())
    except (ValueError, AttributeError):
        return []
    sectors = []
    for sector, ranges in CRITICAL_SECTORS.items():
        for low, high in ranges:
            if low <= sic <= high:
                sectors.append(sector)
                break
    return sectors


# ---------------------------------------------------------------------------
# Risk rating
# ---------------------------------------------------------------------------

def compute_risk_rating(summary: Dict) -> tuple:
    """Compute overall risk rating and justification."""
    score = 0
    reasons = []

    adv = len(summary["adversarial_jurisdictions"])
    if adv > 0:
        score += 40
        reasons.append(f"Adversarial-nation jurisdictions detected: {', '.join(sorted(summary['adversarial_jurisdictions']))}")

    sa_count = len({(sa["entity"], sa["category"]) for sa in summary["state_affiliations"]})
    if sa_count >= 3:
        score += 25
        reasons.append(f"{sa_count} state-actor affiliated entities")
    elif sa_count > 0:
        score += 15
        reasons.append(f"{sa_count} state-actor affiliated entity(ies)")

    conduit = len(summary["conduit_jurisdictions"])
    if conduit > 0:
        score += 10
        reasons.append(f"Conduit jurisdictions: {', '.join(sorted(summary['conduit_jurisdictions']))}")

    opacity = len(summary["opacity_jurisdictions"])
    if opacity > 0:
        score += 10
        reasons.append(f"Opacity jurisdictions: {', '.join(sorted(summary['opacity_jurisdictions']))}")

    obs = len({o["entity"] for o in summary["obscuring_roles"]})
    if obs > 0:
        score += 10
        reasons.append(f"{obs} obscuring-role entities (nominees, proxies, intermediaries)")

    if summary["max_chain_depth"] >= 5:
        score += 5
        reasons.append(f"Deep ownership chain (depth {summary['max_chain_depth']})")

    if summary["critical_sectors"]:
        score += 10
        reasons.append(f"Critical sector(s): {', '.join(summary['critical_sectors'])}")

    if score >= 60:
        rating = "CRITICAL"
    elif score >= 40:
        rating = "HIGH"
    elif score >= 25:
        rating = "ELEVATED"
    elif score >= 10:
        rating = "MODERATE"
    else:
        rating = "LOW"

    return rating, score, reasons


# ---------------------------------------------------------------------------
# CSV loading
# ---------------------------------------------------------------------------

def load_csv(path: str) -> List[Dict[str, str]]:
    rows = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        header_line = None
        for line in f:
            if line.startswith("#"):
                continue
            header_line = line.strip()
            break
        if not header_line:
            return rows
        fields = header_line.split("|")
        reader = csv.DictReader(f, fieldnames=fields, delimiter="|")
        for row in reader:
            if row.get("source"):
                rows.append(row)
    return rows


def extract_metadata(path: str) -> Dict[str, str]:
    meta = {}
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.startswith("#"):
                break
            line = line.lstrip("#").strip()
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
    return meta


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze_rows(rows: List[Dict]) -> Dict:
    summary = {
        "total_edges": len(rows),
        "relationships": Counter(),
        "persons": [],
        "beneficial_owners": [],
        "institutions": [],
        "countries": [],
        "incorporated_in": [],
        "state_affiliations": [],
        "obscuring_roles": [],
        "risk_tiers": Counter(),
        "adversarial_jurisdictions": set(),
        "conduit_jurisdictions": set(),
        "opacity_jurisdictions": set(),
        "company_names": set(),
        "company_ciks": set(),
        "max_chain_depth": 0,
        "unique_sources": set(),
        "unique_targets": set(),
        "filing_dates": set(),
        "filing_forms": Counter(),
        "sic_code": "",
        "sic_description": "",
        "critical_sectors": [],
    }

    seen_persons = set()
    seen_bo = set()
    seen_inst = set()

    for row in rows:
        rel = row.get("relationship", "")
        summary["relationships"][rel] += 1

        src = row.get("source", "")
        tgt = row.get("target", "")
        summary["unique_sources"].add(src)
        summary["unique_targets"].add(tgt)

        cn = row.get("company_name", "")
        cc = row.get("company_cik", "")
        if cn:
            summary["company_names"].add(cn)
        if cc:
            summary["company_ciks"].add(cc)

        fd = row.get("filing_date", "")
        if fd:
            summary["filing_dates"].add(fd)
        ff = row.get("filing_form", "")
        if ff:
            summary["filing_forms"][ff] += 1

        try:
            depth = int(row.get("chain_depth", "0") or "0")
            if depth > summary["max_chain_depth"]:
                summary["max_chain_depth"] = depth
        except ValueError:
            pass

        for tier_col in ["source_risk_tier", "target_risk_tier"]:
            tier = row.get(tier_col, "")
            if tier:
                summary["risk_tiers"][tier] += 1
                jur = row.get(tier_col.replace("risk_tier", "jurisdiction"), "")
                if tier == "ADVERSARIAL" and jur:
                    summary["adversarial_jurisdictions"].add(jur)
                elif tier == "CONDUIT" and jur:
                    summary["conduit_jurisdictions"].add(jur)
                elif tier == "OPACITY" and jur:
                    summary["opacity_jurisdictions"].add(jur)

        sa = row.get("state_affiliation", "")
        sa_sub = row.get("state_affiliation_sub", "")
        sa_detail = row.get("state_affiliation_detail", "")
        if sa:
            summary["state_affiliations"].append({
                "entity": src, "category": sa,
                "subcategory": sa_sub, "detail": sa_detail,
                "relationship": rel,
            })

        if row.get("role_is_obscuring") == "Y":
            summary["obscuring_roles"].append({
                "entity": src, "role": row.get("detail", ""),
                "relationship": rel,
            })

        if rel == "person_role" and src not in seen_persons:
            seen_persons.add(src)
            summary["persons"].append({
                "name": src,
                "role": row.get("detail", ""),
                "is_executive": row.get("role_is_executive", "") == "Y",
                "is_board": row.get("role_is_board", "") == "Y",
                "is_ownership": row.get("role_is_ownership", "") == "Y",
                "jurisdiction": row.get("source_jurisdiction", ""),
                "risk_tier": row.get("source_risk_tier", ""),
                "state_affiliation": sa,
                "filing": ff, "date": fd,
            })

        if rel == "beneficial_owner" and src not in seen_bo:
            seen_bo.add(src)
            try:
                bo_depth = int(row.get("chain_depth", "0") or "0")
            except ValueError:
                bo_depth = 0
            summary["beneficial_owners"].append({
                "name": src, "target": tgt,
                "detail": row.get("detail", ""),
                "jurisdiction": row.get("source_jurisdiction", ""),
                "risk_tier": row.get("source_risk_tier", ""),
                "state_affiliation": sa,
                "state_affiliation_sub": sa_sub,
                "filing": ff, "date": fd,
                "_depth": bo_depth,
            })

        if rel == "institution_role" and src not in seen_inst:
            seen_inst.add(src)
            summary["institutions"].append({
                "name": src,
                "role": row.get("detail", ""),
                "jurisdiction": row.get("source_jurisdiction", ""),
                "risk_tier": row.get("source_risk_tier", ""),
                "state_affiliation": sa,
                "state_affiliation_sub": sa_sub,
            })

        if rel == "country_association":
            summary["countries"].append({
                "country": tgt, "risk_tier": row.get("target_risk_tier", ""),
            })

        if rel == "incorporated_in":
            summary["incorporated_in"].append({
                "company": src, "jurisdiction": tgt,
                "detail": row.get("detail", ""),
                "notes": row.get("notes", ""),
            })
            # Extract SIC from notes
            notes = row.get("notes", "")
            if "SIC:" in notes:
                parts = notes.split("SIC:", 1)[1].strip()
                if parts:
                    sic_parts = parts.split(None, 1)
                    summary["sic_code"] = sic_parts[0] if sic_parts else ""
            detail = row.get("detail", "")
            if detail:
                summary["sic_description"] = detail

    # Classify critical sectors
    if summary["sic_code"]:
        summary["critical_sectors"] = classify_sector(summary["sic_code"])

    # Build ownership tree from directed edges
    summary["ownership_tree"] = _build_ownership_tree(rows, summary)

    return summary


# ---------------------------------------------------------------------------
# Ownership tree builder
# ---------------------------------------------------------------------------

def _build_ownership_tree(rows: List[Dict], summary: Dict) -> Dict:
    """
    Build a directed ownership graph from CSV edges and compute the
    full chain tree with the investigated entity positioned in context.
    """
    # Identify the root entity using company_cik matching
    # The root CIK's company name is the most frequent company_name in the data
    root_name = ""
    cik_name_counts = Counter()
    for r in rows:
        cn = (r.get("company_name") or "").strip()
        cc = (r.get("company_cik") or "").strip()
        if cn and cc:
            cik_name_counts[(cc, cn)] += 1

    # Pick the company_name associated with the most edges at depth 0
    depth0_names = Counter()
    for r in rows:
        try:
            d = int(r.get("chain_depth", "0") or "0")
        except ValueError:
            d = 0
        if d == 0:
            cn = (r.get("company_name") or "").strip()
            if cn:
                depth0_names[cn] += 1
    if depth0_names:
        root_name = depth0_names.most_common(1)[0][0]
    elif cik_name_counts:
        root_name = cik_name_counts.most_common(1)[0][1]

    # Fallback: most common target of person_role edges
    if not root_name:
        target_counts = Counter()
        for r in rows:
            if r.get("relationship") in ("person_role", "institution_role"):
                target_counts[r.get("target", "")] += 1
        if target_counts:
            root_name = target_counts.most_common(1)[0][0]

    if not root_name:
        root_name = sorted(summary["company_names"])[0] if summary["company_names"] else ""

    # Build adjacency: who_owns[entity] = list of owners (upward)
    #                   subsidiaries[entity] = list of children (downward)
    who_owns: Dict[str, List[Dict]] = defaultdict(list)
    subsidiaries: Dict[str, List[Dict]] = defaultdict(list)

    # Entity metadata lookup
    entity_meta: Dict[str, Dict] = {}

    def _record_meta(name, row, role=""):
        if name and name not in entity_meta:
            entity_meta[name] = {
                "jurisdiction": row.get("source_jurisdiction", "") if name == row.get("source", "") else row.get("target_jurisdiction", ""),
                "risk_tier": row.get("source_risk_tier", "") if name == row.get("source", "") else row.get("target_risk_tier", ""),
                "state_affiliation": row.get("state_affiliation", ""),
                "role": role,
            }

    # Deduplicate beneficial_owner edges by (source, target) pair
    seen_bo_pairs = set()
    for r in rows:
        rel = r.get("relationship", "")
        src = (r.get("source") or "").strip()
        tgt = (r.get("target") or "").strip()
        if not src or not tgt:
            continue

        if rel == "beneficial_owner":
            pair = (src, tgt)
            if pair in seen_bo_pairs:
                continue
            seen_bo_pairs.add(pair)
            who_owns[tgt].append({"name": src, "detail": r.get("detail", ""), "depth": r.get("chain_depth", "0")})
            _record_meta(src, r, "beneficial_owner")
            _record_meta(tgt, r)

        elif rel == "consolidated_subsidiary":
            subsidiaries[src].append({"name": tgt, "detail": r.get("detail", ""), "depth": r.get("chain_depth", "0")})
            _record_meta(src, r)
            _record_meta(tgt, r, "subsidiary")

    # Walk upward from root to find ancestor chain (BFS, deduplicated)
    ancestors = []  # ordered from root upward: [(name, level), ...]
    visited_up = {root_name}
    frontier = [root_name]
    level = 0
    while frontier and level < 20:
        level += 1
        next_frontier = []
        for entity in frontier:
            for owner_info in who_owns.get(entity, []):
                owner = owner_info["name"]
                if owner not in visited_up:
                    visited_up.add(owner)
                    ancestors.append((owner, level, owner_info.get("detail", "")))
                    next_frontier.append(owner)
        frontier = next_frontier

    # Walk downward from root to find descendant chain (BFS, deduplicated)
    descendants = []  # ordered from root downward: [(name, level), ...]
    visited_down = {root_name}
    frontier = [root_name]
    level = 0
    while frontier and level < 20:
        level += 1
        next_frontier = []
        for entity in frontier:
            for child_info in subsidiaries.get(entity, []):
                child = child_info["name"]
                if child not in visited_down:
                    visited_down.add(child)
                    descendants.append((child, level, child_info.get("detail", "")))
                    next_frontier.append(child)
        frontier = next_frontier

    # Compute chain length
    max_ancestor_depth = max((lvl for _, lvl, _ in ancestors), default=0)
    max_descendant_depth = max((lvl for _, lvl, _ in descendants), default=0)
    chain_length = max_ancestor_depth + 1 + max_descendant_depth  # ancestors + root + descendants

    # Build ASCII tree
    tree_lines = []

    # Render ancestors top-down (highest ancestor first)
    ancestors_by_level = defaultdict(list)
    for name, lvl, detail in ancestors:
        ancestors_by_level[lvl].append((name, detail))

    for lvl in range(max_ancestor_depth, 0, -1):
        indent = "  " * (max_ancestor_depth - lvl)
        for name, detail in ancestors_by_level.get(lvl, []):
            meta = entity_meta.get(name, {})
            jur = meta.get("jurisdiction", "")
            tier = meta.get("risk_tier", "")
            sa = meta.get("state_affiliation", "")
            tags = []
            if jur:
                tags.append(jur)
            if tier and tier != "STANDARD":
                tags.append(tier)
            if sa:
                tags.append(sa)
            tag_str = f" ({', '.join(tags)})" if tags else ""
            pct = f" [{detail}]" if detail else ""
            tree_lines.append(f"{indent}{name}{pct}{tag_str}")
            if lvl > 1:
                tree_lines.append(f"{indent}  |")

    # Render root entity (starred)
    root_indent = "  " * max_ancestor_depth
    if max_ancestor_depth > 0:
        tree_lines.append(f"{root_indent}  |")
    root_meta = entity_meta.get(root_name, {})
    root_jur = root_meta.get("jurisdiction", "")
    root_tag = f" ({root_jur})" if root_jur else ""
    tree_lines.append(f"{root_indent}* {root_name}{root_tag}  <-- INVESTIGATED ENTITY")

    # Render descendants
    def _render_descendants(parent, indent_level, visited):
        children = subsidiaries.get(parent, [])
        for child_info in children:
            child = child_info["name"]
            if child in visited:
                continue
            visited.add(child)
            indent = "  " * (max_ancestor_depth + indent_level)
            meta = entity_meta.get(child, {})
            jur = meta.get("jurisdiction", "")
            tier = meta.get("risk_tier", "")
            sa = meta.get("state_affiliation", "")
            tags = []
            if jur:
                tags.append(jur)
            if tier and tier != "STANDARD":
                tags.append(tier)
            if sa:
                tags.append(sa)
            tag_str = f" ({', '.join(tags)})" if tags else ""
            tree_lines.append(f"{indent}  |-- {child}{tag_str}")
            _render_descendants(child, indent_level + 1, visited)

    if descendants:
        desc_visited = {root_name}
        _render_descendants(root_name, 1, desc_visited)

    return {
        "root_name": root_name,
        "ancestors": ancestors,
        "descendants": descendants,
        "chain_length": chain_length,
        "max_ancestor_depth": max_ancestor_depth,
        "max_descendant_depth": max_descendant_depth,
        "tree_text": "\n".join(tree_lines),
        "entity_meta": entity_meta,
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_executive_summary(summary: Dict, meta: Dict, source_file: str, rows_for_title: List[Dict] = None) -> str:
    """Generate a concise executive summary report (1-2 pages)."""
    lines = []
    if rows_for_title is None:
        rows_for_title = []

    company_names = sorted(summary["company_names"])
    company_ciks = sorted(summary["company_ciks"])
    root_cik = meta.get("Root CIK", "").strip()
    title_name = None
    if root_cik:
        for row in rows_for_title:
            if row.get("company_cik", "").strip() == root_cik and row.get("company_name", "").strip():
                title_name = row["company_name"].strip()
                break
    if not title_name:
        title_name = company_names[0] if company_names else "Unknown Entity"
    title_cik = root_cik or (company_ciks[0] if company_ciks else "")

    # Risk rating
    rating, score, reasons = compute_risk_rating(summary)
    emoji = {"CRITICAL": "\U0001f534", "HIGH": "\U0001f7e0", "ELEVATED": "\U0001f7e1",
             "MODERATE": "\U0001f535", "LOW": "\U0001f7e2"}.get(rating, "")

    # Header
    lines.append(f"# Executive Summary: {title_name}")
    lines.append("")
    lines.append("> **Author:** Robert J. Green")
    lines.append("> **Web:** [www.rjgreenresearch.org](https://www.rjgreenresearch.org)")
    lines.append("> **Email:** [robert@rjgreenresearch.org](mailto:robert@rjgreenresearch.org)")
    lines.append("> **ORCID:** [0009-0002-9097-1021](https://orcid.org/0009-0002-9097-1021)")
    lines.append("> **SSRN:** [https://ssrn.com/author=10825096](https://ssrn.com/author=10825096)")
    lines.append("")
    lines.append(f"Generated: {datetime.utcnow().isoformat()} UTC")
    lines.append("")

    # Risk rating box
    lines.append("---")
    lines.append("")
    lines.append(f"## {emoji} Risk Rating: **{rating}** (score: {score}/100)")
    lines.append("")

    # Entity identification
    lines.append("| | |")
    lines.append("|---|---|")
    lines.append(f"| **Entity** | {title_name} |")
    if title_cik:
        lines.append(f"| **CIK** | {title_cik} |")

    # Incorporation
    for inc in summary["incorporated_in"]:
        if inc["company"].upper() == title_name.upper() or title_name.upper() in inc["company"].upper():
            lines.append(f"| **Incorporated** | {inc['jurisdiction']} |")
            if inc["detail"]:
                lines.append(f"| **Industry** | {inc['detail']} |")
            break

    if summary["critical_sectors"]:
        lines.append(f"| **Critical Sector** | {', '.join(summary['critical_sectors'])} |")

    lines.append(f"| **Edges Analyzed** | {summary['total_edges']} |")
    lines.append(f"| **Entities Discovered** | {len(summary['unique_sources'] | summary['unique_targets'])} |")
    lines.append(f"| **BFS Depth Reached** | {summary['max_chain_depth']} |")
    lines.append("")

    # Risk factors
    if reasons:
        lines.append("---")
        lines.append("")
        lines.append("## Risk Factors")
        lines.append("")
        for r in reasons:
            lines.append(f"- {r}")
        lines.append("")

    # Ownership chain tree (compact version for executive summary)
    tree = summary.get("ownership_tree", {})
    if tree.get("tree_text"):
        lines.append("---")
        lines.append("")
        lines.append("## Ownership Chain")
        lines.append("")
        chain_len = tree.get("chain_length", 0)
        anc = tree.get("max_ancestor_depth", 0)
        desc = tree.get("max_descendant_depth", 0)
        lines.append(f"**{chain_len}-tier chain** ({anc} owners above, {desc} subsidiaries below)")
        lines.append("")
        lines.append("```")
        # Truncate tree for executive summary — show max 15 lines
        tree_lines = tree["tree_text"].split("\n")
        if len(tree_lines) > 15:
            lines.extend(tree_lines[:15])
            lines.append(f"  ... ({len(tree_lines) - 15} more lines in detailed report)")
        else:
            lines.extend(tree_lines)
        lines.append("```")
        lines.append("")

    # Adversarial exposure summary
    has_adversarial = bool(summary["adversarial_jurisdictions"])
    has_conduit = bool(summary["conduit_jurisdictions"])
    has_opacity = bool(summary["opacity_jurisdictions"])

    if has_adversarial or has_conduit or has_opacity:
        lines.append("---")
        lines.append("")
        lines.append("## Jurisdictional Exposure")
        lines.append("")
        if has_adversarial:
            lines.append(f"- **Adversarial:** {', '.join(sorted(summary['adversarial_jurisdictions']))}")
        if has_conduit:
            lines.append(f"- **Conduit:** {', '.join(sorted(summary['conduit_jurisdictions']))}")
        if has_opacity:
            lines.append(f"- **Opacity:** {', '.join(sorted(summary['opacity_jurisdictions']))}")
        lines.append("")

    # State-actor affiliations (deduplicated, compact)
    if summary["state_affiliations"]:
        seen = set()
        unique_sa = []
        for sa in summary["state_affiliations"]:
            key = (sa["entity"], sa["category"])
            if key not in seen:
                seen.add(key)
                unique_sa.append(sa)

        if unique_sa:
            lines.append("---")
            lines.append("")
            lines.append("## State-Actor Affiliations")
            lines.append("")
            for sa in unique_sa:
                sub = f" ({sa['subcategory']})" if sa.get("subcategory") else ""
                lines.append(f"- **{sa['category']}{sub}:** {sa['entity']}")
            lines.append("")

    # Key personnel (compact — just names and roles)
    if summary["persons"]:
        lines.append("---")
        lines.append("")
        execs = [p for p in summary["persons"] if p["is_executive"]]
        board = [p for p in summary["persons"] if p["is_board"] and not p["is_executive"]]

        if execs or board:
            lines.append("## Key Personnel")
            lines.append("")
            if execs:
                exec_str = "; ".join(f"{p['name']} ({p['role']})" for p in execs[:8])
                lines.append(f"**Executives:** {exec_str}")
                lines.append("")
            if board:
                board_str = "; ".join(f"{p['name']}" for p in board[:8])
                lines.append(f"**Board:** {board_str}")
                lines.append("")

    # Supply chain alert
    if summary["critical_sectors"] and has_adversarial:
        lines.append("---")
        lines.append("")
        lines.append(f"> **\u26a0 SUPPLY CHAIN ALERT:** {title_name} operates in ")
        lines.append(f"> **{', '.join(summary['critical_sectors'])}** with ownership exposure to ")
        lines.append(f"> **{', '.join(sorted(summary['adversarial_jurisdictions']))}**.")
        lines.append("")

    # Footer with link to detailed report
    lines.append("---")
    lines.append("")
    detail_name = os.path.splitext(os.path.basename(source_file))[0] + "_report.md"
    lines.append(f"*See detailed report: `{detail_name}`*")
    lines.append("")
    lines.append("*Generated by SECMap Report Generator v2.0*")
    lines.append("")

    return "\n".join(lines)


def generate_report(summary: Dict, meta: Dict, source_file: str, rows_for_title: List[Dict] = None) -> str:
    lines = []
    if rows_for_title is None:
        rows_for_title = []
    company_names = sorted(summary["company_names"])
    company_ciks = sorted(summary["company_ciks"])
    # Use the root CIK's company name from metadata, not alphabetical first
    root_cik = meta.get("Root CIK", "").strip()
    title_name = None
    if root_cik:
        # Find the company name associated with the root CIK
        for row in rows_for_title:
            if row.get("company_cik", "").strip() == root_cik and row.get("company_name", "").strip():
                title_name = row["company_name"].strip()
                break
    if not title_name:
        title_name = company_names[0] if company_names else "Unknown Entity"
    title_cik = root_cik or (company_ciks[0] if company_ciks else "")

    # Header
    lines.append(f"# Ownership Chain Summary: {title_name}")
    lines.append("")
    lines.append("> **Author:** Robert J. Green")
    lines.append("> **Web:** [www.rjgreenresearch.org](https://www.rjgreenresearch.org)")
    lines.append("> **Email:** [robert@rjgreenresearch.org](mailto:robert@rjgreenresearch.org)")
    lines.append("> **ORCID:** [0009-0002-9097-1021](https://orcid.org/0009-0002-9097-1021)")
    lines.append("> **SSRN:** [https://ssrn.com/author=10825096](https://ssrn.com/author=10825096)")
    lines.append("")
    lines.append(f"Generated: {datetime.utcnow().isoformat()} UTC")
    lines.append(f"Source: `{os.path.basename(source_file)}`")
    lines.append("")

    # Overall risk rating
    rating, score, reasons = compute_risk_rating(summary)
    emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "ELEVATED": "🟡", "MODERATE": "🔵", "LOW": "🟢"}.get(rating, "⚪")

    lines.append("---")
    lines.append("")
    lines.append(f"## {emoji} Overall Risk Rating: **{rating}** (score: {score}/100)")
    lines.append("")
    if reasons:
        for r in reasons:
            lines.append(f"- {r}")
        lines.append("")

    # Supply chain vulnerability
    if summary["critical_sectors"] or summary["sic_description"]:
        lines.append("---")
        lines.append("")
        lines.append("## Supply Chain Vulnerability Assessment")
        lines.append("")
        lines.append(f"| Attribute | Value |")
        lines.append(f"|---|---|")
        if summary["sic_code"]:
            lines.append(f"| **SIC Code** | {summary['sic_code']} |")
        if summary["sic_description"]:
            lines.append(f"| **Industry** | {summary['sic_description']} |")
        if summary["critical_sectors"]:
            lines.append(f"| **Critical Sector(s)** | {', '.join(summary['critical_sectors'])} |")
        adv_bo = [bo for bo in summary["beneficial_owners"] if bo.get("risk_tier") == "ADVERSARIAL" or bo.get("state_affiliation")]
        lines.append(f"| **Adversarial Beneficial Owners** | {len(adv_bo)} |")
        adv_inst = [i for i in summary["institutions"] if i.get("risk_tier") == "ADVERSARIAL" or i.get("state_affiliation")]
        lines.append(f"| **Adversarial-Linked Institutions** | {len(adv_inst)} |")
        lines.append("")

        if summary["critical_sectors"] and summary["adversarial_jurisdictions"]:
            lines.append(f"> **⚠ SUPPLY CHAIN ALERT:** This entity operates in **{', '.join(summary['critical_sectors'])}** ")
            lines.append(f"> and has ownership chain exposure to **{', '.join(sorted(summary['adversarial_jurisdictions']))}**. ")
            lines.append(f"> This combination represents a potential critical supply chain vulnerability.")
            lines.append("")

    # AFIDA depth comparison — use the ownership tree chain length
    tree = summary.get("ownership_tree", {})
    tree_chain_length = tree.get("chain_length", 0)
    all_jurisdictions = set()
    for bo in summary["beneficial_owners"]:
        j = bo.get("jurisdiction", "")
        if j:
            all_jurisdictions.add(j)
    for inc in summary["incorporated_in"]:
        j = inc.get("jurisdiction", "")
        if j:
            all_jurisdictions.add(j)
    all_jurisdictions.update(summary["adversarial_jurisdictions"])
    all_jurisdictions.update(summary["conduit_jurisdictions"])
    all_jurisdictions.update(summary["opacity_jurisdictions"])

    effective_depth = max(summary["max_chain_depth"], len(all_jurisdictions), tree_chain_length)

    lines.append("---")
    lines.append("")
    lines.append("## AFIDA Depth Comparison")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| **SECMap BFS Depth** | {summary['max_chain_depth']} layers |")
    lines.append(f"| **Beneficial Owner Entities** | {len(summary['beneficial_owners'])} |")
    lines.append(f"| **Jurisdictions Traversed** | {len(all_jurisdictions)} ({', '.join(sorted(all_jurisdictions)) or 'none'}) |")
    lines.append(f"| **Effective Chain Depth** | {effective_depth} layers |")
    lines.append(f"| **AFIDA Typical Depth** | 2-3 layers (self-reported) |")
    depth_gap = max(0, effective_depth - 3)
    lines.append(f"| **Depth Gap** | {depth_gap} layers beyond AFIDA visibility |")
    lines.append("")
    # Show gap alert if there's any adversarial exposure OR depth exceeds AFIDA
    has_adversarial = bool(summary["adversarial_jurisdictions"])
    if depth_gap > 0 or (has_adversarial and effective_depth > 1):
        if depth_gap == 0 and has_adversarial:
            depth_gap = effective_depth - 1  # at minimum, the adversarial hop is invisible
        lines.append(f"> **AFIDA DISCLOSURE GAP:** This ownership chain traverses **{len(all_jurisdictions)} jurisdictions** ")
        lines.append(f"> with **{len(summary['beneficial_owners'])} beneficial owner entities**, representing an effective depth of **{effective_depth} layers** — ")
        lines.append(f"> **{depth_gap} layers beyond** AFIDA's typical self-reporting depth.")
        lines.append("")

    # Ownership Chain Tree
    tree = summary.get("ownership_tree", {})
    if tree.get("tree_text"):
        lines.append("---")
        lines.append("")
        lines.append("## Ownership Chain Tree")
        lines.append("")
        lines.append("Reads top-down: ultimate owners at top, subsidiaries at bottom.")
        lines.append(f"The investigated entity is marked with `*`.")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|---|---|")
        lines.append(f"| **Chain Length** | {tree.get('chain_length', 0)} tiers |")
        lines.append(f"| **Owners Above** | {tree.get('max_ancestor_depth', 0)} levels ({len(tree.get('ancestors', []))} entities) |")
        lines.append(f"| **Subsidiaries Below** | {tree.get('max_descendant_depth', 0)} levels ({len(tree.get('descendants', []))} entities) |")
        lines.append("")
        lines.append("```")
        lines.append(tree["tree_text"])
        lines.append("```")
        lines.append("")

    # Executive summary
    lines.append("---")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| **Company** | {title_name} |")
    if title_cik:
        lines.append(f"| **CIK** | {title_cik} |")
    lines.append(f"| **Total Edges** | {summary['total_edges']} |")
    lines.append(f"| **Unique Entities** | {len(summary['unique_sources'] | summary['unique_targets'])} |")
    lines.append(f"| **Max Chain Depth** | {summary['max_chain_depth']} |")
    lines.append(f"| **Persons Identified** | {len(summary['persons'])} |")
    lines.append(f"| **Beneficial Owners** | {len(summary['beneficial_owners'])} |")
    lines.append(f"| **Institutions** | {len(summary['institutions'])} |")
    lines.append(f"| **State-Affiliated Entities** | {len(set((sa['entity'], sa['category']) for sa in summary['state_affiliations']))} |")
    lines.append(f"| **Obscuring Roles** | {len(set(o['entity'] for o in summary['obscuring_roles']))} |")
    lines.append(f"| **Adversarial Jurisdictions** | {', '.join(sorted(summary['adversarial_jurisdictions'])) or 'None'} |")
    lines.append(f"| **Conduit Jurisdictions** | {', '.join(sorted(summary['conduit_jurisdictions'])) or 'None'} |")
    lines.append(f"| **Opacity Jurisdictions** | {', '.join(sorted(summary['opacity_jurisdictions'])) or 'None'} |")
    lines.append("")

    # Filing coverage
    if summary["filing_dates"]:
        dates = sorted(summary["filing_dates"])
        lines.append("---")
        lines.append("")
        lines.append("## Filing Coverage")
        lines.append("")
        lines.append(f"- **Date range:** {dates[0]} to {dates[-1]}")
        lines.append(f"- **Filing types:** {', '.join(f'{k} ({v})' for k, v in summary['filing_forms'].most_common())}")
        lines.append("")

    # Risk tier distribution
    if summary["risk_tiers"]:
        lines.append("---")
        lines.append("")
        lines.append("## Jurisdiction Risk Distribution")
        lines.append("")
        lines.append("| Risk Tier | Edge Count |")
        lines.append("|---|---|")
        for tier in ["ADVERSARIAL", "CONDUIT", "OPACITY", "MONITORED", "STANDARD"]:
            count = summary["risk_tiers"].get(tier, 0)
            if count:
                lines.append(f"| **{tier}** | {count} |")
        lines.append("")

    # Incorporation
    if summary["incorporated_in"]:
        lines.append("---")
        lines.append("")
        lines.append("## Incorporation")
        lines.append("")
        for inc in summary["incorporated_in"]:
            lines.append(f"- **{inc['company']}** → {inc['jurisdiction']}")
            if inc["detail"]:
                lines.append(f"  - Industry: {inc['detail']}")
            if inc["notes"]:
                lines.append(f"  - {inc['notes']}")
        lines.append("")

    # State-actor affiliations
    if summary["state_affiliations"]:
        lines.append("---")
        lines.append("")
        lines.append("## State-Actor Affiliations")
        lines.append("")
        lines.append("| Entity | Category | Subcategory | Detail |")
        lines.append("|---|---|---|---|")
        seen = set()
        for sa in summary["state_affiliations"]:
            key = (sa["entity"], sa["category"])
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"| {sa['entity']} | **{sa['category']}** | {sa['subcategory']} | {sa['detail']} |")
        lines.append("")

    # ALL beneficial owners
    if summary["beneficial_owners"]:
        lines.append("---")
        lines.append("")
        lines.append(f"## Beneficial Owners ({len(summary['beneficial_owners'])} total)")
        lines.append("")
        lines.append("| Reporting Person | Target | Ownership | Jurisdiction | Risk Tier | State Affil. | Filing | Date |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for bo in summary["beneficial_owners"]:
            sa_label = f"{bo.get('state_affiliation', '')}"
            if bo.get("state_affiliation_sub"):
                sa_label += f" ({bo['state_affiliation_sub']})"
            lines.append(
                f"| {bo['name']} | {bo['target']} | {bo['detail']} | "
                f"{bo['jurisdiction']} | {bo['risk_tier']} | {sa_label} | {bo['filing']} | {bo['date']} |"
            )
        lines.append("")

    # Key personnel
    if summary["persons"]:
        lines.append("---")
        lines.append("")
        lines.append(f"## Key Personnel ({len(summary['persons'])} total)")
        lines.append("")

        execs = [p for p in summary["persons"] if p["is_executive"]]
        board = [p for p in summary["persons"] if p["is_board"] and not p["is_executive"]]
        ownership = [p for p in summary["persons"] if p["is_ownership"]]
        other = [p for p in summary["persons"] if not p["is_executive"] and not p["is_board"] and not p["is_ownership"]]

        def _person_table(title, people):
            if not people:
                return
            lines.append(f"### {title}")
            lines.append("")
            lines.append("| Name | Role | Jurisdiction | Risk Tier | State Affil. | Filing | Date |")
            lines.append("|---|---|---|---|---|---|---|")
            for p in people:
                lines.append(
                    f"| {p['name']} | {p['role']} | {p['jurisdiction']} | "
                    f"{p['risk_tier']} | {p['state_affiliation']} | {p['filing']} | {p['date']} |"
                )
            lines.append("")

        _person_table("Executives", execs)
        _person_table("Board Members", board)
        _person_table("Ownership Roles", ownership)
        _person_table("Other Signatories", other)

    # ALL institutions
    if summary["institutions"]:
        lines.append("---")
        lines.append("")
        lines.append(f"## Institutional Relationships ({len(summary['institutions'])} total)")
        lines.append("")
        lines.append("| Institution | Role | Jurisdiction | Risk Tier | State Affiliation |")
        lines.append("|---|---|---|---|---|")
        for inst in summary["institutions"]:
            sa_label = inst["state_affiliation"]
            if inst.get("state_affiliation_sub"):
                sa_label += f" ({inst['state_affiliation_sub']})"
            lines.append(
                f"| {inst['name']} | {inst['role']} | {inst['jurisdiction']} | "
                f"{inst['risk_tier']} | {sa_label} |"
            )
        lines.append("")

    # Obscuring roles
    if summary["obscuring_roles"]:
        lines.append("---")
        lines.append("")
        lines.append("## Obscuring Roles (Layering Indicators)")
        lines.append("")
        lines.append("These roles indicate potential ownership layering or opacity:")
        lines.append("")
        lines.append("| Entity | Role | Relationship |")
        lines.append("|---|---|---|")
        seen = set()
        for obs in summary["obscuring_roles"]:
            if obs["entity"] in seen:
                continue
            seen.add(obs["entity"])
            lines.append(f"| {obs['entity']} | {obs['role']} | {obs['relationship']} |")
        lines.append("")

    # Country associations
    if summary["countries"]:
        lines.append("---")
        lines.append("")
        lines.append("## Country Associations")
        lines.append("")
        country_tiers = defaultdict(list)
        seen_countries = set()
        for c in summary["countries"]:
            if c["country"] in seen_countries:
                continue
            seen_countries.add(c["country"])
            country_tiers[c["risk_tier"]].append(c["country"])
        for tier in ["ADVERSARIAL", "CONDUIT", "OPACITY", "MONITORED", "STANDARD", ""]:
            countries = country_tiers.get(tier, [])
            if countries:
                label = tier if tier else "Unclassified"
                lines.append(f"- **{label}:** {', '.join(sorted(countries))}")
        lines.append("")

    # Relationship breakdown
    lines.append("---")
    lines.append("")
    lines.append("## Relationship Breakdown")
    lines.append("")
    lines.append("| Relationship Type | Count |")
    lines.append("|---|---|")
    for rel, count in summary["relationships"].most_common():
        lines.append(f"| {rel} | {count} |")
    lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("*Report generated by SECMap Report Generator v2.0*")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# File processing
# ---------------------------------------------------------------------------

def process_file(csv_path: str, out_dir: str):
    basename = os.path.splitext(os.path.basename(csv_path))[0]
    rows = load_csv(csv_path)
    meta = extract_metadata(csv_path)
    if not rows:
        print(f"  SKIP (no data): {basename}")
        return
    summary = analyze_rows(rows)

    # Executive summary
    exec_report = generate_executive_summary(summary, meta, csv_path, rows_for_title=rows)
    exec_path = os.path.join(out_dir, f"{basename}_summary.md")
    os.makedirs(out_dir, exist_ok=True)
    with open(exec_path, "w", encoding="utf-8") as f:
        f.write(exec_report)

    # Detailed report
    detail_report = generate_report(summary, meta, csv_path, rows_for_title=rows)
    detail_path = os.path.join(out_dir, f"{basename}_report.md")
    with open(detail_path, "w", encoding="utf-8") as f:
        f.write(detail_report)

    rating, score, _ = compute_risk_rating(summary)
    print(f"  {basename}: {summary['total_edges']} edges, risk={rating} ({score})")
    print(f"    -> {exec_path}")
    print(f"    -> {detail_path}")


def process_directory(dir_path: str, out_dir: str):
    for fname in sorted(os.listdir(dir_path)):
        if fname.endswith(".csv"):
            process_file(os.path.join(dir_path, fname), out_dir)


def main():
    parser = argparse.ArgumentParser(description="SECMap Ownership Chain Summary Report Generator v2.0")
    parser.add_argument("input", help="CSV file or directory of CSV files")
    parser.add_argument("--out", default=None, help="Output directory for reports")
    args = parser.parse_args()

    if os.path.isdir(args.input):
        out_dir = args.out or os.path.join(args.input, "reports")
        print(f"Processing directory: {args.input}")
        process_directory(args.input, out_dir)
    elif os.path.isfile(args.input):
        out_dir = args.out or os.path.dirname(args.input) or "."
        print(f"Processing file: {args.input}")
        process_file(args.input, out_dir)
    else:
        print(f"ERROR: Not found: {args.input}")
        sys.exit(1)
    print("Done.")


if __name__ == "__main__":
    main()
