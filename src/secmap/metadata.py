"""
metadata.py

Defines a structured metadata object for SECMap runs.

Responsibilities:
- Capture run-level metadata (root CIK, depth, forms, timestamps)
- Capture chain-analysis summary statistics
- Provide a serializable representation for CSV headers or JSON output
- Ensure reproducibility and auditability of SECMap runs
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import List, Dict, Any, Optional


@dataclass(frozen=True)
class ChainAnalysisSummary:
    """Risk-analysis summary computed from edges."""
    total_edges: int = 0
    adversarial_edges: int = 0
    conduit_edges: int = 0
    opacity_edges: int = 0
    state_affiliated_edges: int = 0
    obscuring_role_edges: int = 0
    ownership_edges: int = 0
    max_chain_depth: int = 0
    unique_jurisdictions: List[str] = field(default_factory=list)
    adversarial_jurisdictions: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class RunMetadata:
    """Immutable metadata describing a single SECMap run."""
    run_id: str
    timestamp_utc: str
    root_cik: str
    form_types: List[str]
    max_depth: int
    max_filings_per_cik: int
    visited_ciks: List[str]
    filings_processed: int
    secmap_version: str = "1.1.0"
    chain_summary: Optional[ChainAnalysisSummary] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_header_lines(self) -> List[str]:
        lines = [
            f"# SECMap Run ID: {self.run_id}",
            f"# Timestamp (UTC): {self.timestamp_utc}",
            f"# Root CIK: {self.root_cik}",
            f"# Form Types: {', '.join(self.form_types)}",
            f"# Max Depth: {self.max_depth}",
            f"# Max Filings Per CIK: {self.max_filings_per_cik}",
            f"# CIKs Visited: {len(self.visited_ciks)}",
            f"# Filings Processed: {self.filings_processed}",
            f"# SECMap Version: {self.secmap_version}",
        ]

        if self.chain_summary:
            cs = self.chain_summary
            lines.extend([
                "#",
                "# --- Chain Analysis Summary ---",
                f"# Total Edges: {cs.total_edges}",
                f"# Adversarial-Tier Edges: {cs.adversarial_edges}",
                f"# Conduit-Tier Edges: {cs.conduit_edges}",
                f"# Opacity-Tier Edges: {cs.opacity_edges}",
                f"# State-Affiliated Edges: {cs.state_affiliated_edges}",
                f"# Obscuring-Role Edges: {cs.obscuring_role_edges}",
                f"# Ownership Edges: {cs.ownership_edges}",
                f"# Max Chain Depth: {cs.max_chain_depth}",
                f"# Unique Jurisdictions: {', '.join(cs.unique_jurisdictions) or 'None'}",
                f"# Adversarial Jurisdictions: {', '.join(cs.adversarial_jurisdictions) or 'None'}",
            ])

        return lines


def compute_chain_summary(edges) -> ChainAnalysisSummary:
    """Compute chain-analysis summary from a list of OwnershipEdge objects."""
    from .jurisdiction_inference import RISK_ADVERSARIAL, RISK_CONDUIT, RISK_OPACITY

    adversarial = 0
    conduit = 0
    opacity = 0
    state_affiliated = 0
    obscuring = 0
    ownership = 0
    max_depth = 0
    jurisdictions = set()
    adversarial_jurs = set()

    for e in edges:
        for tier_val in [getattr(e, "source_risk_tier", None), getattr(e, "target_risk_tier", None)]:
            if tier_val == RISK_ADVERSARIAL:
                adversarial += 1
                break
            elif tier_val == RISK_CONDUIT:
                conduit += 1
                break
            elif tier_val == RISK_OPACITY:
                opacity += 1
                break

        if getattr(e, "state_affiliation", None):
            state_affiliated += 1

        if getattr(e, "role_is_obscuring", False):
            obscuring += 1

        if getattr(e, "role_is_ownership", False):
            ownership += 1

        depth = getattr(e, "chain_depth", 0)
        if depth > max_depth:
            max_depth = depth

        for jur in [getattr(e, "source_jurisdiction", None), getattr(e, "target_jurisdiction", None)]:
            if jur:
                jurisdictions.add(jur)

        for jur, tier in [
            (getattr(e, "source_jurisdiction", None), getattr(e, "source_risk_tier", None)),
            (getattr(e, "target_jurisdiction", None), getattr(e, "target_risk_tier", None)),
        ]:
            if jur and tier == RISK_ADVERSARIAL:
                adversarial_jurs.add(jur)

    return ChainAnalysisSummary(
        total_edges=len(edges),
        adversarial_edges=adversarial,
        conduit_edges=conduit,
        opacity_edges=opacity,
        state_affiliated_edges=state_affiliated,
        obscuring_role_edges=obscuring,
        ownership_edges=ownership,
        max_chain_depth=max_depth,
        unique_jurisdictions=sorted(jurisdictions),
        adversarial_jurisdictions=sorted(adversarial_jurs),
    )


def generate_run_metadata(
    root_cik: str,
    form_types: List[str],
    max_depth: int,
    max_filings_per_cik: int,
    visited_ciks: List[str],
    filings_processed: int,
    run_id: str,
    edges=None,
) -> RunMetadata:
    """Factory function to generate a RunMetadata object."""
    timestamp = datetime.utcnow().isoformat() + "Z"

    chain_summary = None
    if edges is not None:
        chain_summary = compute_chain_summary(edges)

    return RunMetadata(
        run_id=run_id,
        timestamp_utc=timestamp,
        root_cik=root_cik,
        form_types=form_types,
        max_depth=max_depth,
        max_filings_per_cik=max_filings_per_cik,
        visited_ciks=visited_ciks,
        filings_processed=filings_processed,
        chain_summary=chain_summary,
    )
