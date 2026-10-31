from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse


class SourceSelectionEngine:
    """
    Adaptive source selection engine ranking research sources based on
    expected information value (EV), historical yield, cost, latency,
    source diversity, and anti-syndication filtering.
    """

    KNOWN_SYNDICATION_DOMAINS: Set[str] = {
        "prlog.org",
        "openpr.com",
        "einpresswire.com",
        "prnewswire.com",
        "businesswire.com",
        "globenewswire.com",
        "prweb.com",
        "newsfilecorp.com",
        "marketersmedia.com",
    }

    HIGH_AUTHORITY_SOURCES: Dict[str, float] = {
        "github.com": 0.95,
        "odoo.com": 0.98,
        "apps.odoo.com": 0.98,
        "linkedin.com": 0.90,
        "sec.gov": 0.99,
        "asic.gov.au": 0.99,
        "companieshouse.gov.uk": 0.99,
    }

    @classmethod
    def calculate_expected_information_value(
        cls,
        relevance_score: float,
        historical_yield_rate: float,
        estimated_cost_usd: float,
        estimated_latency_sec: float,
        is_syndicated: bool = False,
    ) -> float:
        """
        Calculates expected information value:
        EV = (relevance * yield * freshness_penalty) / (cost + 0.1 * latency)
        """
        syndication_discount = 0.4 if is_syndicated else 1.0
        numerator = max(0.01, relevance_score) * max(0.01, historical_yield_rate) * syndication_discount
        denominator = max(0.01, estimated_cost_usd + (0.05 * estimated_latency_sec))
        return round(numerator / denominator, 4)

    @classmethod
    def extract_apex_domain(cls, url_or_domain: str) -> str:
        """Extracts apex domain (e.g. example.com) from URL or subdomain."""
        if not url_or_domain:
            return ""
        if "://" not in url_or_domain:
            url_or_domain = "https://" + url_or_domain
        parsed = urlparse(url_or_domain)
        host = (parsed.hostname or "").lower()

        parts = host.split(".")
        if len(parts) >= 2:
            # Handle common 2-level ccTLDs like .com.au, .co.uk
            if len(parts) >= 3 and parts[-2] in ("com", "co", "org", "gov", "net", "edu"):
                return ".".join(parts[-3:])
            return ".".join(parts[-2:])
        return host

    @classmethod
    def is_syndicated_source(cls, url: str) -> bool:
        """Determines if a source domain is a known press-release syndicator."""
        apex = cls.extract_apex_domain(url)
        return apex in cls.KNOWN_SYNDICATION_DOMAINS

    @classmethod
    def rank_sources_for_task(
        cls,
        task_type: str,
        candidate_sources: List[Dict[str, Any]],
        healthy_domains: Optional[Set[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Ranks candidate sources for a specific research task type, prioritizing
        high-yield, cost-effective, and independent authoritative domains.
        """
        scored_sources = []

        for src in candidate_sources:
            url = src.get("url") or src.get("source_url") or ""
            domain = src.get("domain") or cls.extract_apex_domain(url)

            # Check health
            if healthy_domains is not None and domain not in healthy_domains:
                continue

            relevance = src.get("relevance", 0.5)
            yield_rate = src.get("historical_yield_rate", 0.7)
            cost = src.get("cost_usd", 0.001)
            latency = src.get("latency_sec", 1.0)
            is_syndicated = cls.is_syndicated_source(url or domain)

            # Task affinity boosts
            if task_type == "ODOO_VERIFICATION" and ("github" in domain or "odoo" in domain):
                relevance = min(1.0, relevance + 0.3)
            elif task_type == "INTENT_DISCOVERY" and ("jobs" in domain or "careers" in domain or "linkedin" in domain):
                relevance = min(1.0, relevance + 0.3)
            elif task_type == "CONTACT_VERIFICATION" and ("dns" in domain or "mail" in domain):
                relevance = min(1.0, relevance + 0.3)

            ev = cls.calculate_expected_information_value(
                relevance_score=relevance,
                historical_yield_rate=yield_rate,
                estimated_cost_usd=cost,
                estimated_latency_sec=latency,
                is_syndicated=is_syndicated,
            )

            scored = dict(src)
            scored["expected_value"] = ev
            scored["is_syndicated"] = is_syndicated
            scored["apex_domain"] = domain
            scored_sources.append(scored)

        scored_sources.sort(key=lambda s: s["expected_value"], reverse=True)
        return scored_sources

    @classmethod
    def evaluate_source_diversity(cls, source_urls: List[str]) -> Dict[str, Any]:
        """
        Evaluates source diversity across a collection of URLs.
        Ensures at least 2 independent apex domains are present for corroboration.
        """
        domains = set()
        syndicated_count = 0

        for u in source_urls:
            apex = cls.extract_apex_domain(u)
            if apex:
                domains.add(apex)
                if cls.is_syndicated_source(u):
                    syndicated_count += 1

        unique_domain_count = len(domains)
        is_corroborated = unique_domain_count >= 2
        diversity_score = min(1.0, round(unique_domain_count / 3.0, 2))

        return {
            "unique_domain_count": unique_domain_count,
            "unique_domains": list(domains),
            "syndicated_source_count": syndicated_count,
            "is_corroborated": is_corroborated,
            "diversity_score": diversity_score,
        }

