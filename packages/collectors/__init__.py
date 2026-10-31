from packages.collectors.base import BaseCollector
from packages.collectors.signal_extractor import RawSignal, extract_evidence_snippet
from packages.collectors.github import GitHubCollector
from packages.collectors.website import WebsiteCollector
from packages.collectors.rss import RSSCollector
from packages.collectors.jobs import JobsCollector

__all__ = [
    "BaseCollector",
    "RawSignal",
    "extract_evidence_snippet",
    "GitHubCollector",
    "WebsiteCollector",
    "RSSCollector",
    "JobsCollector",
]

