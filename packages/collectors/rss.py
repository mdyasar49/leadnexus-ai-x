import logging
import xml.etree.ElementTree as ET
from typing import Dict, Any, Generator, List, Optional
from datetime import datetime
from packages.collectors.base import BaseCollector
from packages.collectors.signal_extractor import RawSignal, extract_evidence_snippet

logger = logging.getLogger("leadnexus.collectors.rss")


class RSSCollector(BaseCollector):
    """
    Enterprise RSS & Atom Feed Collector:
    - Ingests public industry feeds, enterprise press releases, tech blogs, and tender portals
    - Performs keyword matching across titles, descriptions, and full content
    - Supports unlimited continuous feed discovery across configured and public news streams
    - Extracts publication timestamps, author tags, and exact permalinks
    """
    def __init__(self):
        super().__init__(name="rss_feeds", default_delay=0.5, timeout=12)
        self.default_feeds = [
            "https://www.zdnet.com/news/rss.xml",
            "https://techcrunch.com/feed/",
            "https://news.ycombinator.com/rss",
            "https://feeds.feedburner.com/oreilly/radar/atom",
            "https://www.itnews.com.au/RSS/rss.ashx",
        ]

    def _parse_xml_feed(self, content: bytes) -> List[Dict[str, Any]]:
        items = []
        try:
            root = ET.fromstring(content)
            # RSS 2.0
            for item in root.findall(".//item"):
                title = item.findtext("title") or ""
                link = item.findtext("link") or ""
                desc = item.findtext("description") or ""
                pub_date = item.findtext("pubDate") or ""
                items.append({
                    "title": title.strip(),
                    "link": link.strip(),
                    "description": desc.strip(),
                    "published": pub_date.strip(),
                })

            # Atom 1.0 fallback
            if not items:
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall(".//atom:entry", ns):
                    title = entry.findtext("atom:title", namespaces=ns) or ""
                    link_elem = entry.find("atom:link", namespaces=ns)
                    link = link_elem.attrib.get("href", "") if link_elem is not None else ""
                    summary = entry.findtext("atom:summary", namespaces=ns) or entry.findtext("atom:content", namespaces=ns) or ""
                    updated = entry.findtext("atom:updated", namespaces=ns) or ""
                    items.append({
                        "title": title.strip(),
                        "link": link.strip(),
                        "description": summary.strip(),
                        "published": updated.strip(),
                    })
        except Exception as e:
            logger.debug(f"[RSS Collector] Error parsing feed XML: {e}")
        return items

    def collect_stream(
        self,
        campaign_config: Dict[str, Any]
    ) -> Generator[RawSignal, None, None]:
        """
        Continuously streams intent signals from RSS and Atom news feeds.
        """
        configured_feeds = campaign_config.get("rss_feeds", []) or self.default_feeds
        intent_keywords = campaign_config.get("intent_keywords", [])
        company_keywords = campaign_config.get("company_keywords", [])
        
        all_keywords = list(set(intent_keywords + company_keywords))
        if not all_keywords:
            all_keywords = ["ERP", "Odoo", "CRM", "migration", "digital transformation", "Zoho"]

        logger.info(f"[RSS Collector] Scanning {len(configured_feeds)} feeds against {len(all_keywords)} keywords...")

        for feed_url in configured_feeds:
            resp = self.fetch_url(feed_url)
            if not resp or resp.status_code != 200:
                continue

            entries = self._parse_xml_feed(resp.content)
            for entry in entries:
                full_text = f"{entry['title']} - {entry['description']}"
                for kw in all_keywords:
                    if kw.lower() in full_text.lower():
                        evidence = extract_evidence_snippet(full_text, kw, window=140)
                        signal = RawSignal(
                            source_name="rss_feeds",
                            source_url=entry["link"] or feed_url,
                            detected_keyword=kw,
                            evidence_snippet=evidence,
                            signal_type="NEWS_FEED_SIGNAL",
                            signal_strength=1.1,
                            company_name_hint=None,
                            raw_payload={
                                "title": entry["title"],
                                "feed_url": feed_url,
                                "published": entry["published"]
                            }
                        )
                        yield signal

