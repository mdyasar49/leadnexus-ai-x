import hashlib
import logging
from typing import Dict, Any, List, Optional
from packages.collectors.plugin import SourcePlugin
from packages.collectors.rss import RSSCollector
from packages.collectors.base import BaseCollector

logger = logging.getLogger("leadnexus.plugins.rss")


class RSSAtomPlugin(SourcePlugin):
    """
    Public RSS & Atom News Feed Intelligence Plugin:
    - Scrapes enterprise tech feeds, press releases, and tenders
    - Matches digital transformation, ERP upgrades, and partner announcements
    """
    def __init__(self):
        self.collector = RSSCollector()
        self.base = BaseCollector(name="rss_feeds", default_delay=0.5)

    @property
    def source_id(self) -> str:
        return "rss_feeds"

    @property
    def source_name(self) -> str:
        return "Public RSS & Atom News Feeds"

    @property
    def source_type(self) -> str:
        return "RSS"

    def discovery(self, campaign_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        raw_signals = self.collector.collect(campaign_config, limit=20)
        candidates = []
        for s in raw_signals:
            parsed = s.to_dict()
            candidates.append({
                "url": parsed["source_url"],
                "normalized_url": parsed["source_url"],
                "source": self.source_id,
                "title": parsed.get("raw_payload", {}).get("title", "Enterprise News Update"),
                "snippet": parsed["evidence_snippet"],
                "query": parsed["detected_keyword"],
                "source_rank": 1,
                "content_type": "application/rss+xml",
                "discovery_method": "RSS_INGEST",
                "preliminary_relevance": 0.78,
                "confidence": 0.8,
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
        return []

    def extract_signals(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [{
            "keyword": data.get("detected_keyword", "ERP"),
            "signal_type": "NEWS_FEED_SIGNAL",
            "source_url": data.get("source_url", ""),
            "evidence_snippet": data.get("evidence_snippet", ""),
            "confidence": 0.8,
        }]

    def extract_contacts(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []

    def extract_evidence(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        evidence_snippet = data.get("evidence_snippet", "")
        return [{
            "evidence_text": evidence_snippet,
            "evidence_hash": hashlib.sha256(evidence_snippet.encode("utf-8")).hexdigest(),
            "source_url": data.get("source_url", ""),
        }]

    def health_check(self) -> Dict[str, Any]:
        return {"status": "OPERATIONAL", "latency_ms": 100, "is_healthy": True}

    def rate_limit_policy(self) -> Dict[str, Any]:
        return {"requests_per_minute": 40, "max_concurrent": 3}

    def authentication_requirements(self) -> Dict[str, Any]:
        return {"auth_required": False, "credential_type": "NONE"}

    def robots_policy(self) -> Dict[str, Any]:
        return {"enforce_robots": True}

    def terms_policy(self) -> Dict[str, Any]:
        return {"compliance": "Public syndication feed terms"}

    def supported_regions(self) -> List[str]:
        return ["GLOBAL"]

    def supported_content_types(self) -> List[str]:
        return ["application/rss+xml", "application/atom+xml"]

