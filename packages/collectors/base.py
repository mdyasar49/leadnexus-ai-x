import time
import random
import logging
import urllib.robotparser
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional, Generator
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from packages.collectors.signal_extractor import RawSignal

logger = logging.getLogger("leadnexus.collectors.base")


class BaseCollector:
    """
    Enterprise Base Collector with:
    - Polite rate-limiting and jitter
    - Automatic exponential backoff
    - robots.txt compliance checking
    - Unlimited data collection & continuous pagination support
    """
    def __init__(
        self,
        name: str,
        default_delay: float = 1.0,
        timeout: int = 15,
        max_retries: int = 3,
        user_agent: str = "LeadNexusAI-ResearchBot/1.0 (+https://infonix.com/bot; compliance@infonix.com)"
    ):
        self.name = name
        self.default_delay = default_delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent
        self.robots_cache: Dict[str, urllib.robotparser.RobotFileParser] = {}

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })

        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "HEAD"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def is_allowed_by_robots(self, url: str) -> bool:
        """
        Validates whether target URL permits scraping according to robots.txt.
        """
        try:
            parsed = urlparse(url)
            domain = f"{parsed.scheme}://{parsed.netloc}"
            
            if domain not in self.robots_cache:
                rp = urllib.robotparser.RobotFileParser()
                robots_url = f"{domain}/robots.txt"
                try:
                    resp = requests.get(robots_url, headers={"User-Agent": self.user_agent}, timeout=5)
                    if resp.status_code == 200:
                        rp.parse(resp.text.splitlines())
                    else:
                        rp.allow_all = True
                except Exception:
                    rp.allow_all = True
                self.robots_cache[domain] = rp
            
            return self.robots_cache[domain].can_fetch(self.user_agent, url)
        except Exception as e:
            logger.debug(f"robots.txt check exception for {url}: {e}")
            return True

    def polite_wait(self, delay: Optional[float] = None) -> None:
        """
        Sleeps with a randomized jitter to prevent burst patterns.
        """
        base = delay if delay is not None else self.default_delay
        jitter = random.uniform(0.1, 0.4)
        time.sleep(base + jitter)

    def fetch_url(
        self,
        url: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        check_robots: bool = False
    ) -> Optional[requests.Response]:
        """
        Fetches an endpoint with error resilience, rate limit awareness, and timeouts.
        """
        if check_robots and not self.is_allowed_by_robots(url):
            logger.warning(f"[{self.name}] Skipped {url} due to robots.txt restriction.")
            return None

        self.polite_wait()
        try:
            merged_headers = dict(self.session.headers)
            if headers:
                merged_headers.update(headers)

            resp = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=merged_headers,
                timeout=self.timeout
            )
            return resp
        except requests.exceptions.RequestException as e:
            logger.error(f"[{self.name}] Request error for {url}: {e}")
            return None

    def collect(
        self,
        campaign_config: Dict[str, Any],
        limit: Optional[int] = None
    ) -> List[RawSignal]:
        """
        Collects signals up to `limit`. If `limit` is None, 0, or negative,
        operates in UNLIMITED mode, continuously paginating until sources are exhausted.
        """
        results = []
        is_unlimited = (limit is None or limit <= 0)
        
        for signal in self.collect_stream(campaign_config):
            results.append(signal)
            if not is_unlimited and len(results) >= limit:
                break
        return results

    def collect_stream(
        self,
        campaign_config: Dict[str, Any]
    ) -> Generator[RawSignal, None, None]:
        """
        Abstract generator for streaming unlimited signals from this collector source.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement collect_stream")

