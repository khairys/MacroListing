"""Site Health Check for ZeusX.

Dedicated module to determine whether ZeusX is accessible and ready for automation.
This module does NOT interact with forms — it only checks site readiness.

Returns a SiteStatus enum so the caller (scheduler, main, clear_listings) can
take the appropriate action based on the specific condition.
"""

from enum import Enum
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
import config
from automation.exceptions import (
    SiteUnavailableError, NetworkError, CloudflareChallengeError,
    AuthenticationError, PageNotReadyError
)


class SiteStatus(Enum):
    SITE_READY = "SITE_READY"
    SITE_UNAVAILABLE = "SITE_UNAVAILABLE"
    NETWORK_ERROR = "NETWORK_ERROR"
    CLOUDFLARE_CHALLENGE = "CLOUDFLARE_CHALLENGE"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    UNEXPECTED_PAGE = "UNEXPECTED_PAGE"


def check_site_health(page: Page, target_url: str = None) -> SiteStatus:
    """Navigates to target_url and checks if ZeusX is ready for use.
    
    Does NOT use input() — fully automated, no human interaction required.
    
    Args:
        page: Playwright Page object
        target_url: URL to check. Defaults to config.TARGET_URL
        
    Returns:
        SiteStatus enum value
    """
    if target_url is None:
        target_url = config.TARGET_URL
    
    print(f"[HEALTH] Checking ZeusX at {target_url}...")
    
    # 1. Try to navigate
    try:
        response = page.goto(target_url, wait_until="domcontentloaded",
                             timeout=config.NAVIGATION_TIMEOUT)
    except PlaywrightTimeout:
        print("[HEALTH] NETWORK_ERROR: Navigation timed out.")
        return SiteStatus.NETWORK_ERROR
    except Exception as e:
        error_msg = str(e).lower()
        if any(keyword in error_msg for keyword in ["net::err", "dns", "connection", "refused"]):
            print(f"[HEALTH] NETWORK_ERROR: {e}")
            return SiteStatus.NETWORK_ERROR
        print(f"[HEALTH] SITE_UNAVAILABLE: Navigation failed: {e}")
        return SiteStatus.SITE_UNAVAILABLE
    
    # 2. Check HTTP response status
    if response and response.status >= 500:
        print(f"[HEALTH] SITE_UNAVAILABLE: HTTP {response.status}")
        return SiteStatus.SITE_UNAVAILABLE
    
    # 3. Check for Cloudflare / security challenge
    if _is_cloudflare_challenge(page):
        print("[HEALTH] CLOUDFLARE_CHALLENGE: Security verification detected.")
        return SiteStatus.CLOUDFLARE_CHALLENGE
    
    # 4. Check for maintenance page
    if _is_maintenance_page(page):
        print("[HEALTH] SITE_UNAVAILABLE: Maintenance page detected.")
        return SiteStatus.SITE_UNAVAILABLE
    
    # 5. Check for login redirect / auth required
    if _is_auth_required(page, target_url):
        print("[HEALTH] AUTH_REQUIRED: Login page detected.")
        return SiteStatus.AUTH_REQUIRED
    
    # 6. Check URL is on expected domain
    if "zeusx.com" not in page.url:
        print(f"[HEALTH] UNEXPECTED_PAGE: URL is {page.url}, expected zeusx.com")
        return SiteStatus.UNEXPECTED_PAGE
    
    # 7. Check for error page indicators
    if _is_error_page(page):
        print("[HEALTH] SITE_UNAVAILABLE: Error page detected.")
        return SiteStatus.SITE_UNAVAILABLE
    
    print("[HEALTH] SITE_READY")
    return SiteStatus.SITE_READY


def raise_for_status(status: SiteStatus):
    """Converts a SiteStatus into the appropriate exception.
    
    Only raises for non-READY statuses. Call this when you need to
    interrupt the current flow because the site is not usable.
    """
    if status == SiteStatus.SITE_READY:
        return  # No error
    
    if status == SiteStatus.NETWORK_ERROR:
        raise NetworkError(f"ZeusX is not reachable (network error)")
    if status == SiteStatus.CLOUDFLARE_CHALLENGE:
        raise CloudflareChallengeError("Cloudflare security challenge is active")
    if status == SiteStatus.AUTH_REQUIRED:
        raise AuthenticationError("Login required — session may have expired")
    if status == SiteStatus.SITE_UNAVAILABLE:
        raise SiteUnavailableError("ZeusX is unavailable (down or maintenance)")
    if status == SiteStatus.UNEXPECTED_PAGE:
        raise PageNotReadyError("Page is not on the expected ZeusX domain")
    
    raise SiteUnavailableError(f"Unknown site status: {status}")


def quick_page_health_check(page: Page) -> SiteStatus:
    """Lightweight health check that does NOT navigate.
    
    Use this before critical operations (game select, image upload, submit)
    to make sure the page hasn't silently changed to Cloudflare/error/login.
    """
    if _is_cloudflare_challenge(page):
        return SiteStatus.CLOUDFLARE_CHALLENGE
    
    if "zeusx.com" not in page.url:
        return SiteStatus.UNEXPECTED_PAGE
    
    if _is_auth_required(page, None):
        return SiteStatus.AUTH_REQUIRED
    
    if _is_error_page(page):
        return SiteStatus.SITE_UNAVAILABLE
    
    return SiteStatus.SITE_READY


# === Private helpers ==========================================================

def _is_cloudflare_challenge(page: Page) -> bool:
    """Detects Cloudflare / security verification pages."""
    try:
        title = page.title().lower()
        if "just a moment" in title or "attention required" in title:
            return True
        
        cf_markers = page.locator(
            ".cf-turnstile, iframe[src*='cloudflare'], "
            "#challenge-running, #challenge-form, "
            "[class*='challenge'], #cf-please-wait"
        )
        if cf_markers.count() > 0:
            return True
        
        # Check for "Performing security verification" text
        body_text = page.locator("body").inner_text()[:500].lower()
        if "security" in body_text and "verification" in body_text:
            return True
        if "checking your browser" in body_text:
            return True
            
    except Exception:
        pass  # If we can't even check, don't assume Cloudflare
    
    return False


def _is_maintenance_page(page: Page) -> bool:
    """Detects maintenance/downtime pages."""
    try:
        body_text = page.locator("body").inner_text()[:500].lower()
        maintenance_indicators = [
            "maintenance", "under maintenance",
            "temporarily unavailable", "be right back",
            "scheduled downtime"
        ]
        return any(indicator in body_text for indicator in maintenance_indicators)
    except Exception:
        return False


def _is_auth_required(page: Page, target_url: str | None) -> bool:
    """Detects if the page is a login page or requires authentication."""
    try:
        # URL-based detection
        if "login" in page.url.lower() or "signin" in page.url.lower():
            return True
        
        # If we expected a specific page but got redirected to something else
        if target_url and "login" not in target_url.lower():
            login_buttons = page.get_by_role("link", name="Login", exact=False).or_(
                page.get_by_role("button", name="Login", exact=False)
            ).or_(
                page.get_by_role("link", name="Sign In", exact=False)
            )
            # Only consider it auth-required if login button is prominent AND
            # we're not on the expected page
            if login_buttons.count() > 0:
                # Check if we're on the expected page type
                if target_url and "create-offer" in target_url and "create-offer" not in page.url:
                    return True
                if target_url and "my-listing" in target_url and "my-listing" not in page.url:
                    return True
    except Exception:
        pass
    
    return False


def _is_error_page(page: Page) -> bool:
    """Detects generic error pages (500, 502, 503, 404, etc.)."""
    try:
        title = page.title().lower()
        error_titles = ["500", "502", "503", "504", "server error", 
                        "internal server error", "bad gateway", "service unavailable"]
        if any(err in title for err in error_titles):
            return True
        
        body_text = page.locator("body").inner_text()[:300].lower()
        error_phrases = [
            "internal server error", "bad gateway", 
            "service unavailable", "gateway timeout",
            "something went wrong", "application error"
        ]
        return any(phrase in body_text for phrase in error_phrases)
    except Exception:
        return False
