"""
gap_analyzer.py

Identifies the visibility gap between federal (SEC/AFIDA) and state
(SOS) business entity records.

Designed to work incrementally — state data arrives at different times
and through different channels (API, bulk download, PDF, manual request).
The analyzer maintains a growing picture of the gap as data is ingested.

Core analytical contribution:
  USDA AFIDA relies on self-reporting by foreign investors.
  SEC EDGAR only covers public companies and their direct filers.
  State SOS records cover ALL business entities — including the private
  LLCs, LPs, and trusts that adversarial nations use as terminal nodes
  in layered ownership chains.

  The gap between these three systems is where adversarial ownership
  hides. This module quantifies that gap.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional

logger = logging.getLogger(__name__)


@dataclass
class StateEntity:
    """An entity registered with a state Secretary of State."""
    name: str
    state: str
    entity_type: str = ""       # LLC, LP, Corp, Trust, etc.
    status: str = ""            # Active, Inactive, Forfeited, etc.
    formation_date: str = ""
    registered_agent: str = ""
    registered_agent_address: str = ""
    officers: List[str] = field(default_factory=list)
    jurisdiction_of_formation: str = ""
    source_file: str = ""
    source_method: str = ""     # "api", "bulk", "scrape", "pdf", "manual"
    ingestion_date: str = ""


@dataclass
class GapEntry:
    """A single gap finding — an entity visible at state level but not federal."""
    entity_name: str
    state: str
    entity_type: str
    gap_type: str       # "no_sec_filing", "no_afida", "private_only", "shell_indicator"
    risk_score: float = 0.0
    risk_indicators: List[str] = field(default_factory=list)
    related_sec_entities: List[str] = field(default_factory=list)
    registered_agent: str = ""
    officers: List[str] = field(default_factory=list)
    notes: str = ""


class GapAnalyzer:
    """
    Analyzes the gap between SEC ownership chains and state SOS records.

    Supports incremental ingestion — call load_state_entities() multiple
    times as data arrives from different states and access methods.

    Usage:
        analyzer = GapAnalyzer()
        analyzer.load_sec_entities(sec_edges)

        # As state data arrives (may be days apart for paywall states):
        analyzer.load_state_entities(california_entities)
        analyzer.load_state_entities(texas_entities)

        gaps = analyzer.find_gaps()
        report = analyzer.generate_report(gaps)

        # Save/load state for long-running research
        analyzer.save_state("gap_analysis.json")
        analyzer.load_state("gap_analysis.json")
    """

    def __init__(self):
        self.sec_entities: Set[str] = set()
        self.sec_entity_details: Dict[str, dict] = {}
        self.state_entities: List[StateEntity] = []
        self.states_ingested: Set[str] = set()

    def load_sec_entities(self, edges: list):
        """Extract all entity names from SEC ownership edges."""
        for edge in edges:
            src = getattr(edge.source, "cleaned_name", "") if hasattr(edge, "source") else ""
            tgt = getattr(edge.target, "cleaned_name", "") if hasattr(edge, "target") else ""
            rel = getattr(edge, "relationship", "")

            if src:
                self.sec_entities.add(src.upper())
                self.sec_entity_details[src.upper()] = {
                    "type": getattr(edge.source, "entity_type", ""),
                    "relationship": rel,
                }
            if tgt:
                self.sec_entities.add(tgt.upper())

    def load_state_entities(self, entities: List[StateEntity]):
        """
        Load state SOS entity records. Can be called multiple times
        as data arrives from different states.
        """
        self.state_entities.extend(entities)
        for e in entities:
            self.states_ingested.add(e.state)
        logger.info(
            "Loaded %d state entities (total: %d, states: %s)",
            len(entities), len(self.state_entities),
            ", ".join(sorted(self.states_ingested)),
        )

    def find_gaps(self) -> List[GapEntry]:
        """
        Identify entities in state records that are NOT in SEC filings.
        """
        gaps = []

        for entity in self.state_entities:
            name_upper = entity.name.upper()

            # Exact match
            if name_upper in self.sec_entities:
                continue

            # Fuzzy containment match
            if any(name_upper in sec or sec in name_upper
                   for sec in self.sec_entities if len(sec) > 5):
                continue

            risk_indicators = []
            risk_score = 0.0

            # Shell/layering name patterns
            shell_keywords = [
                "holdings", "properties", "investments", "ventures",
                "capital", "partners", "associates", "enterprises",
                "international", "global", "overseas", "pacific",
                "atlantic", "highland", "meadow", "ranch",
            ]
            lower_name = entity.name.lower()
            matched_shell = [kw for kw in shell_keywords if kw in lower_name]
            if matched_shell:
                risk_indicators.append(f"shell_name_pattern: {', '.join(matched_shell)}")
                risk_score += 0.2 * len(matched_shell)

            # Privacy-state registration
            privacy_states = {"DE", "NV", "WY", "SD"}
            if entity.state in privacy_states:
                risk_indicators.append(f"privacy_state: {entity.state}")
                risk_score += 0.3

            # Layering vehicle type
            layering_types = {"LP", "LLC", "LLP", "Trust"}
            if entity.entity_type in layering_types:
                risk_indicators.append(f"layering_vehicle: {entity.entity_type}")
                risk_score += 0.2

            # Foreign jurisdiction of formation
            if entity.jurisdiction_of_formation and entity.jurisdiction_of_formation != entity.state:
                risk_indicators.append(f"foreign_formation: {entity.jurisdiction_of_formation}")
                risk_score += 0.3

            # Registered agent is a known agent service (not a person)
            agent_services = [
                "ct corporation", "national registered agents",
                "registered agents inc", "cogency global",
                "corporation service company", "csc",
                "united agent group", "northwest registered agent",
            ]
            if entity.registered_agent:
                agent_lower = entity.registered_agent.lower()
                if any(svc in agent_lower for svc in agent_services):
                    risk_indicators.append("commercial_registered_agent")
                    risk_score += 0.1

            gap = GapEntry(
                entity_name=entity.name,
                state=entity.state,
                entity_type=entity.entity_type,
                gap_type="private_only" if entity.entity_type in layering_types else "no_sec_filing",
                risk_score=min(risk_score, 1.0),
                risk_indicators=risk_indicators,
                registered_agent=entity.registered_agent,
                officers=entity.officers,
                notes=f"Formation: {entity.formation_date}" if entity.formation_date else "",
            )
            gaps.append(gap)

        # Sort by risk score descending
        gaps.sort(key=lambda g: g.risk_score, reverse=True)

        logger.info(
            "Gap analysis: %d state entities, %d SEC entities, %d gaps found",
            len(self.state_entities), len(self.sec_entities), len(gaps),
        )
        return gaps

    def generate_report(self, gaps: List[GapEntry]) -> str:
        """Generate a human-readable gap analysis report."""
        lines = [
            "=" * 70,
            "FEDERAL/STATE VISIBILITY GAP ANALYSIS",
            "=" * 70,
            f"SEC entities tracked: {len(self.sec_entities)}",
            f"State entities examined: {len(self.state_entities)}",
            f"States ingested: {', '.join(sorted(self.states_ingested)) or 'none'}",
            f"Gaps identified: {len(gaps)}",
            "",
        ]

        high = [g for g in gaps if g.risk_score >= 0.6]
        medium = [g for g in gaps if 0.3 <= g.risk_score < 0.6]
        low = [g for g in gaps if g.risk_score < 0.3]

        lines.append(f"High risk (score >= 0.6): {len(high)}")
        lines.append(f"Medium risk (0.3-0.6):   {len(medium)}")
        lines.append(f"Low risk (< 0.3):        {len(low)}")
        lines.append("")

        if high:
            lines.append("-" * 70)
            lines.append("HIGH RISK GAPS — Likely adversarial ownership blind spots")
            lines.append("-" * 70)
            for g in high[:50]:
                lines.append(f"\n  {g.entity_name}")
                lines.append(f"    State: {g.state} | Type: {g.entity_type} | Score: {g.risk_score:.2f}")
                lines.append(f"    Risk: {', '.join(g.risk_indicators)}")
                if g.registered_agent:
                    lines.append(f"    Agent: {g.registered_agent}")
                if g.officers:
                    lines.append(f"    Officers: {', '.join(g.officers[:5])}")
                if g.notes:
                    lines.append(f"    Notes: {g.notes}")

        return "\n".join(lines)

    # -----------------------------------------------------------------
    # Persistence for long-running research
    # -----------------------------------------------------------------

    def save_state(self, path: str):
        """Save analyzer state to JSON for resumable research."""
        data = {
            "sec_entities": list(self.sec_entities),
            "states_ingested": list(self.states_ingested),
            "state_entities": [
                {
                    "name": e.name, "state": e.state,
                    "entity_type": e.entity_type, "status": e.status,
                    "formation_date": e.formation_date,
                    "registered_agent": e.registered_agent,
                    "officers": e.officers,
                    "source_method": e.source_method,
                }
                for e in self.state_entities
            ],
        }
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info("Gap analyzer state saved to %s", path)

    def load_saved_state(self, path: str):
        """Load previously saved analyzer state."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.sec_entities = set(data.get("sec_entities", []))
        self.states_ingested = set(data.get("states_ingested", []))
        for e in data.get("state_entities", []):
            self.state_entities.append(StateEntity(**e))
        logger.info(
            "Loaded saved state: %d SEC entities, %d state entities",
            len(self.sec_entities), len(self.state_entities),
        )
