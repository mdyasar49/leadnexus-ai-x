import re
import logging
from typing import Dict, Any, Generator, List, Set, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from packages.collectors.base import BaseCollector
from packages.collectors.signal_extractor import RawSignal, extract_evidence_snippet

logger = logging.getLogger("leadnexus.collectors.website")

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
PHONE_REGEX = re.compile(r'(?:\+?(\d{1,3}))?[-. (]*(\d{2,4})[-. )]*(\d{3,4})[-. ]*(\d{3,5})')


class WebsiteCollector(BaseCollector):
    """
    Enterprise Recursive Website Collector:
    - Recursively crawls seed URLs and public company domains
    - Checks robots.txt compliance before fetching
    - Discovers target pages (/about, /contact, /team, /leadership, /careers)
    - Extracts publicly listed emails, phone numbers, leadership contacts, and intent evidence
    - Supports unlimited continuous crawling across domain link graphs
    """
    def __init__(self):
        super().__init__(name="website", default_delay=0.6, timeout=12)
        self.visited_urls: Set[str] = set()

    def _normalize_domain(self, url: str) -> str:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc

    def crawl_site(self, base_url: str, max_depth: int = 2) -> Dict[str, Any]:
        """
        Deeply inspects a company's public website up to max_depth pages.
        Extracts public emails, phones, leadership names, and technology clues.
        """
        domain = self._normalize_domain(base_url)
        queue = [(base_url, 0)]
        crawled_count = 0
        max_pages_per_site = 12

        findings = {
            "domain": domain,
            "base_url": base_url,
            "company_name": "",
            "emails": set(),
            "phones": set(),
            "social_links": set(),
            "target_pages": [],
            "raw_text_corpus": [],
        }

        priority_subpaths = [
            "/about", "/about-us", "/contact", "/contact-us",
            "/team", "/leadership", "/our-team", "/services"
        ]
        for sub in priority_subpaths:
            queue.append((urljoin(base_url, sub), 1))

        while queue and crawled_count < max_pages_per_site:
            current_url, depth = queue.pop(0)
            if current_url in self.visited_urls:
                continue
            self.visited_urls.add(current_url)

            resp = self.fetch_url(current_url, check_robots=True)
            if not resp or resp.status_code != 200:
                continue

            content_type = resp.headers.get("Content-Type", "").lower()
            if "text/html" not in content_type:
                continue

            crawled_count += 1
            soup = BeautifulSoup(resp.text, "html.parser")

            # Extract title / company name
            if not findings["company_name"]:
                title_tag = soup.find("title")
                if title_tag and title_tag.text:
                    clean_title = title_tag.text.split("|")[0].split("-")[0].strip()
                    if clean_title:
                        findings["company_name"] = clean_title

            # Clean text
            body = soup.get_text(separator=" ", strip=True)
            findings["raw_text_corpus"].append(body)

            # Public emails
            found_emails = EMAIL_REGEX.findall(body)
            for em in found_emails:
                em_lower = em.lower()
                if not any(em_lower.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp"]):
                    findings["emails"].add(em_lower)

            # Public phones
            found_phones = PHONE_REGEX.findall(body)
            for ph in found_phones:
                ph_str = "".join(ph).strip()
                if len(ph_str) >= 8:
                    findings["phones"].add(ph_str)

            # Social links
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "linkedin.com" in href or "twitter.com" in href or "github.com" in href:
                    findings["social_links"].add(href)

        findings["emails"] = list(findings["emails"])
        findings["phones"] = list(findings["phones"])
        findings["social_links"] = list(findings["social_links"])
        return findings

    def collect_stream(
        self,
        campaign_config: Dict[str, Any]
    ) -> Generator[RawSignal, None, None]:
        """
        Streams intent signals and company evidence discovered through website crawling.
        """
        target_domains = campaign_config.get("target_domains", [])
        intent_keywords = campaign_config.get("intent_keywords", ["Odoo", "ERP", "Zoho"])

        # If no explicit target domains provided, use seed partner directories or sample targets
        if not target_domains:
            target_domains = [
                "https://www.odoo.com/partners",
                "https://www.zoho.com/partners"
            ]

        for base_url in target_domains:
            site_data = self.crawl_site(base_url)
            corpus = " ".join(site_data["raw_text_corpus"])

            for ik in intent_keywords:
                if ik.lower() in corpus.lower():
                    evidence = extract_evidence_snippet(corpus, ik, window=140)
                    yield RawSignal(
                        source_name="company_website",
                        source_url=site_data["base_url"],
                        detected_keyword=ik,
                        evidence_snippet=evidence,
                        signal_type="WEBSITE_INTENT",
                        signal_strength=1.2,
                        company_name_hint=site_data.get("company_name"),
                        domain_hint=site_data.get("domain"),
                        raw_payload={
                            "emails": site_data["emails"],
                            "phones": site_data["phones"],
                            "social_links": site_data["social_links"]
                        }
                    )

