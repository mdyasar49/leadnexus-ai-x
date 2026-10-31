import re
from typing import Dict, Any, Tuple
from bs4 import BeautifulSoup
from app.models.browser import PageAccessStatus


def classify_page_access(
    status_code: int,
    html: str,
    url: str
) -> Tuple[PageAccessStatus, str]:
    """
    Determines whether a page is public, login-restricted, paywalled, or blocked.
    Strictly complies with the rule: NEVER BYPASS authentication, paywalls, or CAPTCHAs.
    """
    if status_code == 404:
        return PageAccessStatus.NOT_FOUND, "HTTP 404 Not Found"
    
    if status_code in (500, 502, 503, 504):
        return PageAccessStatus.SERVER_ERROR, f"HTTP {status_code} Server Error"

    if status_code in (401, 407):
        return PageAccessStatus.AUTH_REQUIRED, f"HTTP {status_code} Unauthorized / Authentication Required"

    if status_code == 403:
        # Check if 403 is Cloudflare or access block
        lower_html = html.lower() if html else ""
        if "cloudflare" in lower_html or "access denied" in lower_html or "attention required" in lower_html:
            return PageAccessStatus.ACCESS_BLOCKED, "HTTP 403 Access Blocked / WAF Barrier"
        return PageAccessStatus.AUTH_REQUIRED, "HTTP 403 Forbidden / Authorization Required"

    if status_code == 429:
        return PageAccessStatus.ACCESS_BLOCKED, "HTTP 429 Rate Limit Exceeded / Automated Access Blocked"

    if not html:
        return PageAccessStatus.PUBLIC, "Empty content, assumed public"

    lower_html = html.lower()

    # 1. CAPTCHA detection
    captcha_signatures = [
        "g-recaptcha",
        "h-captcha",
        "cf-turnstile",
        "captcha-box",
        "recaptcha/api.js",
        "challenges.cloudflare.com/turnstile",
        "please verify you are a human",
        "security check to continue"
    ]
    if any(sig in lower_html for sig in captcha_signatures):
        return PageAccessStatus.CAPTCHA_REQUIRED, "Automated CAPTCHA verification required (Not Bypassed)"

    # 2. Login required detection
    soup = BeautifulSoup(html, "html.parser")
    password_fields = soup.find_all("input", {"type": "password"})
    if password_fields:
        # Check if page is predominantly a login portal
        login_indicators = ["sign in", "log in", "login", "authenticate", "enter your password"]
        title_text = (soup.find("title").text if soup.find("title") else "").lower()
        if any(ind in title_text for ind in login_indicators):
            return PageAccessStatus.LOGIN_REQUIRED, "Dedicated login page detected"

    # 3. Paywall detection
    paywall_signatures = [
        "subscribe to read",
        "to read the full article",
        "this content is for subscribers only",
        "join now to read",
        "already a subscriber? log in"
    ]
    if any(sig in lower_html for sig in paywall_signatures):
        return PageAccessStatus.PAYWALL, "Subscription paywall barrier detected"

    # 4. Check for dynamic JS framework footprints
    js_framework_signatures = ["id=\"__next\"", "id=\"root\"", "id=\"app\"", "ng-version", "_nuxt"]
    if any(sig in html for sig in js_framework_signatures) and len(soup.get_text(strip=True)) < 200:
        return PageAccessStatus.PUBLIC_DYNAMIC, "Public dynamic Single Page Application (SPA)"

    return PageAccessStatus.PUBLIC, "Publicly accessible page"

