"""Browser Manager for MacroListing.

Handles CDP connection to Chrome and page lifecycle.
Does NOT use input() — fully automated, suitable for scheduler use.
"""

import os
from playwright.sync_api import sync_playwright, Page
import config
from automation.exceptions import (
    SiteUnavailableError, NetworkError, CloudflareChallengeError,
    AuthenticationError, PageNotReadyError
)
from automation.site_health import check_site_health, raise_for_status, SiteStatus


class BrowserManager:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None

    def start(self) -> Page:
        """Connects to Chrome via CDP and returns the active ZeusX page.
        
        Raises:
            NetworkError: If CDP connection fails (Chrome not running)
        """
        print(f"Connecting to Chrome via CDP at {config.CDP_URL}...")
        self.playwright = sync_playwright().start()
        
        try:
            self.browser = self.playwright.chromium.connect_over_cdp(config.CDP_URL)
        except Exception as e:
            self.stop()
            raise NetworkError(
                f"Failed to connect to Chrome CDP at {config.CDP_URL}. "
                f"Ensure chrome_launcher.py is running. Error: {e}"
            )
            
        if not self.browser.contexts:
            self.stop()
            raise NetworkError("No browser contexts found. Chrome may not be ready.")
        
        self.context = self.browser.contexts[0]
        
        target_page = None
        for page in self.context.pages:
            if "zeusx.com" in page.url:
                target_page = page
                break
                
        if not target_page:
            print("ZeusX tab not found. Creating a new tab...")
            target_page = self.context.new_page()
            
        return target_page

    def ensure_ready(self, page: Page, target_url: str = None):
        """Validates that the page is on ZeusX and ready for automation.
        
        Unlike the old check_cloudflare_or_login(), this does NOT use input().
        It raises the appropriate exception so the caller can decide what to do.
        
        Raises:
            SiteUnavailableError: ZeusX is down
            NetworkError: Network issues
            CloudflareChallengeError: Cloudflare blocking
            AuthenticationError: Login required
            PageNotReadyError: Page in unexpected state
        """
        url = target_url or config.TARGET_URL
        status = check_site_health(page, url)
        
        if status != SiteStatus.SITE_READY:
            raise_for_status(status)
        
        print("Page is ready. Starting automation...")

    def stop(self):
        """Safely disconnects from the browser."""
        try:
            if self.browser:
                self.browser.close()
        except Exception:
            pass
        try:
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass
