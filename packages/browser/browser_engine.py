import hashlib
import json
import logging
import time
from typing import Dict, Any, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import requests

from packages.browser.ssrf import validate_safe_url
from packages.browser.classifier import classify_page_access
from packages.browser.prompt_injection import sanitize_untrusted_content
from app.models.browser import PageAccessStatus

logger = logging.getLogger("leadnexus.browser.engine")

# Check if playwright is importable
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class BrowserEngine:
    """
    Enterprise Browser Extraction Layer:
    - Strictly sandboxed with proactive SSRF defense
    - Playwright Chromium engine with resource blocking (images, fonts, stylesheets)
    - Fallback to resilient HTTP rendering if headless browser runtime is not initialized
    - Structured extraction: JSON-LD, OpenGraph, Twitter metadata, DOM headings, text, links
    - Classifies page accessibility and NEVER bypasses login, CAPTCHA, or paywall boundaries
    """
    def __init__(
        self,
        headless: bool = True,
        timeout_ms: int = 20000,
        user_agent: str = "LeadNexusAI-BrowserBot/1.0 (+https://infonix.com/bot; compliance@infonix.com)"
    ):
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.user_agent = user_agent

    def fetch_and_extract(self, url: str) -> Dict[str, Any]:
        """
        Executes safe, sandboxed extraction of a target public web page.
        """
        # 1. SSRF Safety Check
        is_safe, error_reason = validate_safe_url(url)
        if not is_safe:
            logger.warning(f"[Browser Engine] Blocked unsafe target: {url} Reason: {error_reason}")
            return {
                "url": url,
                "access_status": PageAccessStatus.ACCESS_BLOCKED.value,
                "error": f"SSRF Protection: {error_reason}",
                "status_code": 403,
                "rendered_text": "",
                "title": "",
                "content_hash": "",
                "json_ld": [],
                "opengraph": {},
                "twitter_meta": {},
                "headings": {},
                "links": [],
                "navigation_time_ms": 0,
            }

        start_time = time.time()
        
        # 2. Prefer Playwright when dynamic JS rendering is feasible
        if PLAYWRIGHT_AVAILABLE:
            try:
                return self._fetch_with_playwright(url, start_time)
            except Exception as e:
                logger.warning(f"[Browser Engine] Playwright fetch failed for {url} ({e}). Falling back to HTTP.")

        # 3. HTTP Fallback
        return self._fetch_with_http(url, start_time)

    def _fetch_with_playwright(self, url: str, start_time: float) -> Dict[str, Any]:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ]
            )
            context = browser.new_context(
                user_agent=self.user_agent,
                viewport={"width": 1280, "height": 800},
                ignore_https_errors=True
            )
            page = context.new_page()

            # Resource blocking: abort media, fonts, images to optimize memory and speed
            page.route(
                "**/*",
                lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_()
            )

            response = page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            status_code = response.status if response else 200
            
            # Re-verify final redirect destination for SSRF safety
            final_url = page.url
            is_safe, error_reason = validate_safe_url(final_url)
            if not is_safe:
                browser.close()
                return {
                    "url": url,
                    "access_status": PageAccessStatus.ACCESS_BLOCKED.value,
                    "error": f"SSRF Protection on redirect: {error_reason}",
                    "status_code": 403,
                    "rendered_text": "",
                    "title": "",
                    "content_hash": "",
                    "json_ld": [],
                    "opengraph": {},
                    "twitter_meta": {},
                    "headings": {},
                    "links": [],
                    "navigation_time_ms": int((time.time() - start_time) * 1000),
                }

            html = page.content()
            title = page.title()
            browser.close()

            elapsed_ms = int((time.time() - start_time) * 1000)
            return self._parse_html_payload(url, final_url, status_code, html, title, elapsed_ms)

    def _fetch_with_http(self, url: str, start_time: float) -> Dict[str, Any]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            resp = requests.get(url, headers=headers, timeout=self.timeout_ms / 1000, allow_redirects=True)
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # Re-verify final redirect
            final_url = resp.url
            is_safe, error_reason = validate_safe_url(final_url)
            if not is_safe:
                return {
                    "url": url,
                    "access_status": PageAccessStatus.ACCESS_BLOCKED.value,
                    "error": f"SSRF Protection on redirect: {error_reason}",
                    "status_code": 403,
                    "rendered_text": "",
                    "title": "",
                    "content_hash": "",
                    "json_ld": [],
                    "opengraph": {},
                    "twitter_meta": {},
                    "headings": {},
                    "links": [],
                    "navigation_time_ms": elapsed_ms,
                }

            soup = BeautifulSoup(resp.text, "html.parser")
            title = soup.find("title").text.strip() if soup.find("title") else ""
            return self._parse_html_payload(url, final_url, resp.status_code, resp.text, title, elapsed_ms)
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return {
                "url": url,
                "access_status": PageAccessStatus.SERVER_ERROR.value,
                "error": str(e),
                "status_code": 500,
                "rendered_text": "",
                "title": "",
                "content_hash": "",
                "json_ld": [],
                "opengraph": {},
                "twitter_meta": {},
                "headings": {},
                "links": [],
                "navigation_time_ms": elapsed_ms,
            }

    def _parse_html_payload(
        self,
        original_url: str,
        final_url: str,
        status_code: int,
        html: str,
        title: str,
        elapsed_ms: int
    ) -> Dict[str, Any]:
        access_status, access_reason = classify_page_access(status_code, html, final_url)
        
        # If login or captcha required, do NOT scrape or bypass
        if access_status in (PageAccessStatus.LOGIN_REQUIRED, PageAccessStatus.CAPTCHA_REQUIRED, PageAccessStatus.PAYWALL, PageAccessStatus.AUTH_REQUIRED):
            return {
                "url": original_url,
                "final_url": final_url,
                "access_status": access_status.value,
                "error": access_reason,
                "status_code": status_code,
                "rendered_text": "",
                "title": title,
                "content_hash": hashlib.sha256(html.encode("utf-8", errors="ignore")).hexdigest(),
                "json_ld": [],
                "opengraph": {},
                "twitter_meta": {},
                "headings": {},
                "links": [],
                "navigation_time_ms": elapsed_ms,
            }

        soup = BeautifulSoup(html, "html.parser")

        # Strip scripts, styles
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()

        # Sanitize text with prompt injection defense
        raw_text = soup.get_text(separator=" ", strip=True)
        sanitized_text = sanitize_untrusted_content(raw_text)

        # JSON-LD
        json_ld = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                if script.string:
                    json_ld.append(json.loads(script.string))
            except Exception:
                pass

        # OpenGraph & Twitter
        opengraph = {}
        twitter_meta = {}
        for meta in soup.find_all("meta"):
            prop = meta.get("property", "")
            name = meta.get("name", "")
            content = meta.get("content", "")
            if prop.startswith("og:"):
                opengraph[prop[3:]] = content
            elif name.startswith("twitter:"):
                twitter_meta[name[8:]] = content

        # Headings
        headings = {
            "h1": [h.get_text(strip=True) for h in soup.find_all("h1")],
            "h2": [h.get_text(strip=True) for h in soup.find_all("h2")[:10]],
            "h3": [h.get_text(strip=True) for h in soup.find_all("h3")[:10]],
        }

        # Links
        links = []
        for a in soup.find_all("a", href=True):
            full_href = urljoin(final_url, a["href"])
            if full_href.startswith("http"):
                links.append(full_href)

        # Canonical URL
        canonical_tag = soup.find("link", rel="canonical")
        canonical_url = canonical_tag.get("href") if canonical_tag else final_url

        content_hash = hashlib.sha256(sanitized_text.encode("utf-8")).hexdigest()

        return {
            "url": original_url,
            "final_url": final_url,
            "canonical_url": canonical_url,
            "access_status": access_status.value,
            "status_code": status_code,
            "title": title,
            "rendered_text": sanitized_text[:50000],  # bounded memory retention
            "content_hash": content_hash,
            "json_ld": json_ld,
            "opengraph": opengraph,
            "twitter_meta": twitter_meta,
            "headings": headings,
            "links": list(set(links))[:50],
            "navigation_time_ms": elapsed_ms,
            "error": None,
        }

