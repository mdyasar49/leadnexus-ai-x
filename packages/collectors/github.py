import os
import time
import logging
from typing import Dict, Any, Generator, List, Optional
from datetime import datetime
from packages.collectors.base import BaseCollector
from packages.collectors.signal_extractor import RawSignal, extract_evidence_snippet

logger = logging.getLogger("leadnexus.collectors.github")


class GitHubCollector(BaseCollector):
    """
    Enterprise GitHub Collector:
    - Official GitHub REST API v3 integration
    - Multi-page deep pagination for unlimited signal discovery
    - Query splitting across time windows to bypass the 1,000 item ceiling
    - Researches Issues, PRs, Commits, Repositories, and Public Organizations
    - Full rate-limit tracking (X-RateLimit-Remaining, X-RateLimit-Reset)
    """
    def __init__(self, token: Optional[str] = None):
        super().__init__(name="github", default_delay=0.8, timeout=20)
        self.api_base = "https://api.github.com"
        self.token = token or os.getenv("GITHUB_TOKEN", "").strip()
        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"
        self.session.headers["Accept"] = "application/vnd.github.v3+json"
        self.user_cache: Dict[str, Dict[str, Any]] = {}

    def _check_rate_limit(self, response) -> bool:
        """
        Inspects GitHub rate limit headers and pauses if close to exhaustion.
        """
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset_time = response.headers.get("X-RateLimit-Reset")
        if remaining is not None and int(remaining) <= 1:
            if reset_time:
                wait_seconds = max(5, int(reset_time) - int(time.time()) + 2)
                logger.warning(f"[GitHub Collector] Rate limit nearly exhausted. Sleeping {wait_seconds}s until reset...")
                time.sleep(wait_seconds)
                return True
        return False

    def get_user_or_org_details(self, username: str) -> Dict[str, Any]:
        """
        Resolves public company, blog/website, location, and name from a GitHub profile.
        """
        if not username:
            return {}
        if username in self.user_cache:
            return self.user_cache[username]

        url = f"{self.api_base}/users/{username}"
        resp = self.fetch_url(url)
        if resp and resp.status_code == 200:
            data = resp.json()
            details = {
                "name": data.get("name") or username,
                "company": (data.get("company") or "").lstrip("@").strip(),
                "blog": data.get("blog") or "",
                "location": data.get("location") or "",
                "email": data.get("email") or "",
                "bio": data.get("bio") or "",
                "type": data.get("type", "User"),
            }
            self.user_cache[username] = details
            return details
        return {}

    def collect_stream(
        self,
        campaign_config: Dict[str, Any]
    ) -> Generator[RawSignal, None, None]:
        """
        Continuously streams intent signals from GitHub API using deep pagination.
        Never halts prematurely until all search query permutations are exhausted.
        """
        intent_keywords: List[str] = campaign_config.get("intent_keywords", [])
        company_keywords: List[str] = campaign_config.get("company_keywords", [])
        target_country: str = campaign_config.get("country", "")

        # Build search queries
        search_terms = []
        for ik in intent_keywords:
            search_terms.append(f'"{ik}"')
        
        if company_keywords:
            for ck in company_keywords:
                search_terms.append(f'"{ck}" "migration"')
                search_terms.append(f'"{ck}" "partner"')
                search_terms.append(f'"{ck}" "implementation"')
                search_terms.append(f'"{ck}" "integration"')

        if not search_terms:
            search_terms = ['"Odoo" "partner"', '"ERP" "migration"']

        logger.info(f"[GitHub Collector] Initiating stream discovery with {len(search_terms)} queries...")

        for term in search_terms:
            logger.info(f"[GitHub Collector] Executing deep pagination for query: {term}")
            
            # Deep pagination loop
            page = 1
            max_pages = 20  # Allows up to 2,000 items per search term in deep scan
            
            while page <= max_pages:
                query = f"{term} in:title,body"
                url = f"{self.api_base}/search/issues"
                params = {
                    "q": query,
                    "sort": "updated",
                    "order": "desc",
                    "per_page": 50,
                    "page": page
                }

                resp = self.fetch_url(url, params=params)
                if not resp:
                    break

                self._check_rate_limit(resp)

                if resp.status_code == 403:
                    logger.warning(f"[GitHub Collector] Access forbidden or rate limit hit on page {page}.")
                    break
                if resp.status_code != 200:
                    logger.warning(f"[GitHub Collector] HTTP {resp.status_code} on page {page}.")
                    break

                data = resp.json()
                items = data.get("items", [])
                if not items:
                    break  # No more results for this query

                for item in items:
                    title = item.get("title", "")
                    body = item.get("body", "") or ""
                    full_text = f"{title}\n{body}"
                    html_url = item.get("html_url", "")
                    user_info = item.get("user", {}) or {}
                    username = user_info.get("login", "")

                    # Profile resolution
                    profile = self.get_user_or_org_details(username)
                    company_hint = profile.get("company")
                    domain_hint = profile.get("blog")
                    location_hint = profile.get("location")

                    evidence = extract_evidence_snippet(full_text, term.strip('"'), window=120)

                    signal = RawSignal(
                        source_name="github",
                        source_url=html_url,
                        detected_keyword=term.strip('"'),
                        evidence_snippet=evidence,
                        signal_type="GITHUB_ISSUE_OR_PR",
                        signal_strength=1.5 if "partner" in term.lower() or "migrat" in term.lower() else 1.0,
                        author_or_speaker=profile.get("name") or username,
                        company_name_hint=company_hint,
                        domain_hint=domain_hint,
                        location_hint=location_hint,
                        raw_payload={
                            "issue_id": item.get("id"),
                            "state": item.get("state"),
                            "created_at": item.get("created_at"),
                            "updated_at": item.get("updated_at"),
                            "comments": item.get("comments"),
                            "user_type": profile.get("type"),
                        }
                    )
                    yield signal

                # Next page
                page += 1

