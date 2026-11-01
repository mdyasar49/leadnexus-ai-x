"""
LeadNexus AI X - Phase 42: Named Entity & Lead Extractor
Extracts B2B target entities (Companies, Persons, Emails, Phones, Executive Titles, Technologies, Financials)
from document chunks with context grounding and normalization.
"""

import re
from typing import Any, Dict, List, Optional


class ExtractedEntity:
    def __init__(
        self,
        entity_type: str,
        entity_value: str,
        normalized_value: str,
        confidence: float,
        context_snippet: str,
        page_number: int = 1,
        chunk_id: Optional[str] = None,
    ):
        self.entity_type = entity_type
        self.entity_value = entity_value
        self.normalized_value = normalized_value
        self.confidence = confidence
        self.context_snippet = context_snippet
        self.page_number = page_number
        self.chunk_id = chunk_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "entity_value": self.entity_value,
            "normalized_value": self.normalized_value,
            "confidence": self.confidence,
            "context_snippet": self.context_snippet,
            "page_number": self.page_number,
            "chunk_id": self.chunk_id,
        }


class EntityExtractor:
    """Detects and extracts structured B2B entities from text chunks."""

    # Regex patterns for canonical entity types
    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
    PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
    FINANCIAL_PATTERN = re.compile(r"(?:[\$€£]\s?\d+(?:\.\d+)?\s*(?:[KkMmBb]|million|billion|thousand)?|\b\d+(?:\.\d+)?\s*(?:million|billion|thousand)\s*(?:dollars|USD|EUR|GBP)?)\b")

    KNOWN_TECH = [
        "AWS", "GCP", "Azure", "Kubernetes", "Docker", "PostgreSQL", "Snowflake",
        "Databricks", "React", "TypeScript", "Python", "FastAPI", "Salesforce",
        "HubSpot", "Stripe", "Redis", "Kafka", "Elasticsearch", "GraphQL"
    ]

    EXECUTIVE_TITLES = [
        "CEO", "Chief Executive Officer", "CTO", "Chief Technology Officer",
        "CFO", "Chief Financial Officer", "COO", "Chief Operating Officer",
        "VP of Sales", "VP of Engineering", "Vice President", "Director of Sales",
        "Head of Growth", "Head of Engineering", "Managing Director", "Founder", "Co-Founder"
    ]

    COMPANY_SUFFIXES = [
        "Inc", "Inc.", "LLC", "Corp", "Corporation", "Ltd", "Ltd.",
        "Technologies", "Tech", "Systems", "Solutions", "Software", "Labs", "Group", "AI"
    ]

    @classmethod
    def extract_from_chunk(cls, text: str, page_number: int = 1, chunk_id: Optional[str] = None) -> List[ExtractedEntity]:
        entities: List[ExtractedEntity] = []

        # 1. Emails
        for match in cls.EMAIL_PATTERN.finditer(text):
            val = match.group(0)
            snippet = cls._get_snippet(text, match.start(), match.end())
            entities.append(
                ExtractedEntity(
                    entity_type="EMAIL",
                    entity_value=val,
                    normalized_value=val.lower(),
                    confidence=0.99,
                    context_snippet=snippet,
                    page_number=page_number,
                    chunk_id=chunk_id,
                )
            )

        # 2. Phones
        for match in cls.PHONE_PATTERN.finditer(text):
            val = match.group(0)
            cleaned = re.sub(r"[^\d+]", "", val)
            if len(cleaned) >= 10:
                snippet = cls._get_snippet(text, match.start(), match.end())
                entities.append(
                    ExtractedEntity(
                        entity_type="PHONE",
                        entity_value=val,
                        normalized_value=cleaned,
                        confidence=0.92,
                        context_snippet=snippet,
                        page_number=page_number,
                        chunk_id=chunk_id,
                    )
                )

        # 3. Financials
        for match in cls.FINANCIAL_PATTERN.finditer(text):
            val = match.group(0)
            snippet = cls._get_snippet(text, match.start(), match.end())
            entities.append(
                ExtractedEntity(
                    entity_type="FINANCIAL",
                    entity_value=val,
                    normalized_value=val.replace(" ", "").upper(),
                    confidence=0.90,
                    context_snippet=snippet,
                    page_number=page_number,
                    chunk_id=chunk_id,
                )
            )

        # 4. Technologies
        for tech in cls.KNOWN_TECH:
            pattern = rf"\b{re.escape(tech)}\b"
            for match in re.finditer(pattern, text, re.IGNORECASE):
                snippet = cls._get_snippet(text, match.start(), match.end())
                entities.append(
                    ExtractedEntity(
                        entity_type="TECHNOLOGY",
                        entity_value=match.group(0),
                        normalized_value=tech,
                        confidence=0.95,
                        context_snippet=snippet,
                        page_number=page_number,
                        chunk_id=chunk_id,
                    )
                )

        # 5. Executive Titles & Person Names
        for title in cls.EXECUTIVE_TITLES:
            pattern = rf"(?:([A-Z][a-z]+(?:\s[A-Z][a-z]+){{1,2}})[,\s]+(?:is\s+(?:the\s+)?)?)?{re.escape(title)}\b"
            for match in re.finditer(pattern, text, re.IGNORECASE):
                snippet = cls._get_snippet(text, match.start(), match.end())
                # Add title entity
                entities.append(
                    ExtractedEntity(
                        entity_type="TITLE",
                        entity_value=title,
                        normalized_value=title.upper(),
                        confidence=0.94,
                        context_snippet=snippet,
                        page_number=page_number,
                        chunk_id=chunk_id,
                    )
                )
                # If a name preceded the title
                if match.group(1):
                    person_name = match.group(1).strip()
                    tokens = person_name.split()
                    while tokens and tokens[0] in ["Contact", "Reach", "Meet", "Call", "Email", "Leader", "Key", "Attn", "Mr", "Ms", "Mrs", "Dr"]:
                        tokens = tokens[1:]
                    if tokens:
                        person_name = " ".join(tokens)
                        entities.append(
                            ExtractedEntity(
                                entity_type="PERSON",
                                entity_value=person_name,
                                normalized_value=person_name.title(),
                                confidence=0.88,
                                context_snippet=snippet,
                                page_number=page_number,
                                chunk_id=chunk_id,
                            )
                        )

        # 6. Company Names with Corporate Suffixes
        for suffix in cls.COMPANY_SUFFIXES:
            pattern = rf"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+)*\s+{re.escape(suffix)})\b"
            for match in re.finditer(pattern, text):
                comp_name = match.group(1).strip()
                snippet = cls._get_snippet(text, match.start(), match.end())
                entities.append(
                    ExtractedEntity(
                        entity_type="COMPANY",
                        entity_value=comp_name,
                        normalized_value=comp_name.strip("."),
                        confidence=0.91,
                        context_snippet=snippet,
                        page_number=page_number,
                        chunk_id=chunk_id,
                    )
                )

        # Deduplicate company entities (keep longest name if overlapping)
        company_entities = [e for e in entities if e.entity_type == "COMPANY"]
        if company_entities:
            company_entities.sort(key=lambda x: len(x.entity_value), reverse=True)
            kept_companies = []
            for c in company_entities:
                if not any(c.entity_value in other.entity_value and c.entity_value != other.entity_value for other in kept_companies):
                    kept_companies.append(c)
            entities = [e for e in entities if e.entity_type != "COMPANY"] + kept_companies

        return entities

    @staticmethod
    def _get_snippet(text: str, start: int, end: int, window: int = 50) -> str:
        s_start = max(0, start - window)
        s_end = min(len(text), end + window)
        snippet = text[s_start:s_end].replace("\n", " ").strip()
        prefix = "..." if s_start > 0 else ""
        suffix = "..." if s_end < len(text) else ""
        return f"{prefix}{snippet}{suffix}"
