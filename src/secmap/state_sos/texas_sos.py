"""
texas_sos.py

Parser for Texas Secretary of State business entity documents.

Texas SOS provides entity information as PDF documents containing:
  - Entity name and type (LP, LLC, Corp, etc.)
  - Filing number
  - Status (Active, Inactive)
  - Formation/registration date
  - Registered agent name and address
  - Officers/directors/managers/partners
  - Jurisdiction of formation

This module extracts structured data from these PDFs for gap analysis
against SEC EDGAR records.

Requirements:
    pip install PyPDF2  (or pdfplumber for better table extraction)
"""

from __future__ import annotations

import logging
import os
import re
import zipfile
from dataclasses import dataclass, field
from typing import List, Optional

from .gap_analyzer import StateEntity

logger = logging.getLogger(__name__)

# Try to import PDF libraries
try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False


def _extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from a PDF file using available library."""
    if HAS_PDFPLUMBER:
        with pdfplumber.open(pdf_path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    elif HAS_PYPDF2:
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        logger.warning("No PDF library available. Install PyPDF2 or pdfplumber.")
        return ""


class TexasSOSParser:
    """
    Parse Texas Secretary of State entity documents.

    Usage:
        parser = TexasSOSParser()

        # From a ZIP of PDFs (as downloaded from Texas SOS)
        entities = parser.parse_zip("1569619280005-34406822.zip")

        # From a single PDF
        entity = parser.parse_pdf("entity_filing.pdf")
    """

    # Regex patterns for Texas SOS PDF fields
    _ENTITY_NAME_RE = re.compile(r"(?:Entity Name|Filing Name)[:\s]*(.+?)(?:\n|$)", re.IGNORECASE)
    _ENTITY_TYPE_RE = re.compile(r"(?:Entity Type|Type of Entity)[:\s]*(.+?)(?:\n|$)", re.IGNORECASE)
    _STATUS_RE = re.compile(r"(?:Status)[:\s]*(.+?)(?:\n|$)", re.IGNORECASE)
    _FILE_NUMBER_RE = re.compile(r"(?:File Number|Filing Number)[:\s]*(\d+)", re.IGNORECASE)
    _FORMATION_DATE_RE = re.compile(r"(?:Formation Date|Date of Formation|Date Filed)[:\s]*(.+?)(?:\n|$)", re.IGNORECASE)
    _REG_AGENT_RE = re.compile(r"(?:Registered Agent|Agent Name)[:\s]*(.+?)(?:\n|$)", re.IGNORECASE)
    _REG_AGENT_ADDR_RE = re.compile(r"(?:Registered (?:Office )?Address)[:\s]*(.+?)(?:\n|$)", re.IGNORECASE)
    _JURISDICTION_RE = re.compile(r"(?:Jurisdiction|State of Formation)[:\s]*(.+?)(?:\n|$)", re.IGNORECASE)

    # Officer/partner patterns
    _OFFICER_SECTION_RE = re.compile(
        r"(?:Officers?|Directors?|Managers?|Partners?|Members?)\s*(?:and\s*\w+\s*)?[:\n]",
        re.IGNORECASE,
    )
    _PERSON_LINE_RE = re.compile(r"([A-Z][a-z]+(?:\s[A-Z]\.?)?\s(?:[A-Z][a-z]+\s?)+)")

    def parse_pdf(self, pdf_path: str) -> Optional[StateEntity]:
        """Parse a single Texas SOS PDF into a StateEntity."""
        text = _extract_text_from_pdf(pdf_path)
        if not text:
            logger.warning("No text extracted from %s", pdf_path)
            return None

        return self._parse_text(text, source_file=pdf_path)

    def parse_zip(self, zip_path: str) -> List[StateEntity]:
        """Parse all PDFs in a ZIP file from Texas SOS."""
        entities = []

        if not os.path.exists(zip_path):
            logger.error("ZIP file not found: %s", zip_path)
            return entities

        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(tmp)

                for root, dirs, files in os.walk(tmp):
                    for fname in sorted(files):
                        if fname.lower().endswith(".pdf"):
                            pdf_path = os.path.join(root, fname)
                            entity = self.parse_pdf(pdf_path)
                            if entity:
                                entities.append(entity)

        logger.info("Parsed %d entities from %s", len(entities), zip_path)
        return entities

    def _parse_text(self, text: str, source_file: str = "") -> Optional[StateEntity]:
        """Parse extracted PDF text into a StateEntity."""
        name = self._extract_field(self._ENTITY_NAME_RE, text)
        if not name:
            # Try to find any prominent entity name
            lines = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 5]
            name = lines[0] if lines else ""

        entity_type = self._extract_field(self._ENTITY_TYPE_RE, text) or ""
        status = self._extract_field(self._STATUS_RE, text) or ""
        formation_date = self._extract_field(self._FORMATION_DATE_RE, text) or ""
        reg_agent = self._extract_field(self._REG_AGENT_RE, text) or ""
        reg_agent_addr = self._extract_field(self._REG_AGENT_ADDR_RE, text) or ""
        jurisdiction = self._extract_field(self._JURISDICTION_RE, text) or ""

        # Extract officers/partners
        officers = self._extract_officers(text)

        return StateEntity(
            name=name,
            state="TX",
            entity_type=entity_type,
            status=status,
            formation_date=formation_date,
            registered_agent=reg_agent,
            registered_agent_address=reg_agent_addr,
            officers=officers,
            source_file=source_file,
        )

    def _extract_field(self, pattern: re.Pattern, text: str) -> Optional[str]:
        m = pattern.search(text)
        return m.group(1).strip() if m else None

    def _extract_officers(self, text: str) -> List[str]:
        """Extract officer/partner names from the document."""
        officers = []
        m = self._OFFICER_SECTION_RE.search(text)
        if m:
            section = text[m.end():m.end() + 2000]
            for pm in self._PERSON_LINE_RE.finditer(section):
                name = pm.group(1).strip()
                if len(name) > 4 and len(name) < 60:
                    officers.append(name)
        return officers
