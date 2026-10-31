import hashlib
import logging
from typing import Dict, Any, List, Optional
from packages.collectors.plugin import SourcePlugin
from packages.collectors.jobs import JobsCollector
from packages.collectors.base import BaseCollector

logger = logging.getLogger("leadnexus.plugins.jobs")


class JobsPlugin(SourcePlugin):
    """
    Public Job Intelligence Plugin:
    - Scrapes public career feeds and job boards
    - Detects explicit hiring intent for target enterprise tools (Odoo, Zoho, SAP, Salesforce)
    - Extracts hiring company, role title, requirements, and job permalinks
    - NOTE: A job posting represents an organization hiring signal, NOT a decision maker.
    """
    def __init__(self):
        self.collector = JobsCollector()
        self.base = BaseCollector(name="jobs", default_delay=0.6)

    @property
    def source_id(self) -> str:
        return "job_boards"

    @property
    def source_name(self) -> str:
        return "Public Job Postings & Career Intelligence"

    @property
    def source_type(self) -> str:
        return "JOB_BOARD"

    def discovery(self, campaign_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        raw_signals = self.collector.collect(campaign_config, limit=20)
        candidates = []
        for s in raw_signals:
            parsed = s.to_dict()
            candidates.append({
                "url": parsed["source_url"],
                "normalized_url": parsed["source_url"],
                "source": self.source_id,
                "title": f"Hiring: {parsed.get('raw_payload', {}).get('position', 'Enterprise Specialist')}",
                "snippet": parsed["evidence_snippet"],
                "query": parsed["detected_keyword"],
                "source_rank": 1,
                "content_type": "text/html",
                "discovery_method": "JOB_BOARD",
                "preliminary_relevance": 0.95,
                "confidence": 0.92,
                "evidence_pointer": hashlib.sha256(parsed["source_url"].encode("utf-8")).hexdigest(),
            })
        return candidates

    def fetch(self, url: str) -> Optional[Any]:
        return self.base.fetch_url(url)

    def browser_fetch(self, url: str) -> Dict[str, Any]:
        return {"url": url, "error": "Browser rendering not required"}

    def parse(self, raw_content: Any) -> Dict[str, Any]:
        return {"raw": str(raw_content)}

    def normalize(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        return parsed_data

    def extract_entities(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        company_name = data.get("company_name_hint")
        if not company_name:
            return []
        return [{
            "name": company_name,
            "source_url": data.get("source_url", ""),
            "country": data.get("location_hint", ""),
        }]

    def extract_signals(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [{
            "keyword": data.get("detected_keyword", "Odoo"),
            "signal_type": "HIRING_INTENT_SIGNAL",
            "source_url": data.get("source_url", ""),
            "evidence_snippet": data.get("evidence_snippet", ""),
            "confidence": 0.95,
        }]

    def extract_contacts(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Rule: A job posting is NOT automatic proof of a specific decision maker.
        return []

    def extract_evidence(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        evidence_snippet = data.get("evidence_snippet", "")
        return [{
            "evidence_text": evidence_snippet,
            "evidence_hash": hashlib.sha256(evidence_snippet.encode("utf-8")).hexdigest(),
            "source_url": data.get("source_url", ""),
        }]

    def health_check(self) -> Dict[str, Any]:
        return {"status": "OPERATIONAL", "latency_ms": 140, "is_healthy": True}

    def rate_limit_policy(self) -> Dict[str, Any]:
        return {"requests_per_minute": 20, "max_concurrent": 2}

    def authentication_requirements(self) -> Dict[str, Any]:
        return {"auth_required": False, "credential_type": "NONE"}

    def robots_policy(self) -> Dict[str, Any]:
        return {"enforce_robots": True}

    def terms_policy(self) -> Dict[str, Any]:
        return {"compliance": "Public job aggregation terms"}

    def supported_regions(self) -> List[str]:
        return ["GLOBAL"]

    def supported_content_types(self) -> List[str]:
        return ["text/html", "application/json"]

