import os
from playwright.sync_api import sync_playwright, Page, expect
import logs.dom.wuwa.config
from automation.exceptions import CaptchaDetectedError, LoginRequiredError

class BrowserManager:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None

    def start(self) -> Page:
        print(f"Connecting to Chrome via CDP at {config.CDP_URL}...")
        self.playwright = sync_playwright().start()
        
        try:
            self.browser = self.playwright.chromium.connect_over_cdp(config.CDP_URL)
        except Exception as e:
            raise ConnectionError(f"Failed to connect to CDP at {config.CDP_URL}. Ensure chrome_launcher.py is running. Error: {e}")
            
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

    def check_cloudflare_or_login(self, page: Page):
        """Checks if stuck on Cloudflare or requires login, and pauses if so."""
        print(f"Checking access to {config.TARGET_URL}...")
        page.goto(config.TARGET_URL, wait_until="domcontentloaded")
        
        cf_markers = page.locator(".cf-turnstile, iframe[src*='cloudflare'], #challenge-running")
        if cf_markers.count() > 0 or "just a moment" in page.title().lower():
            print("\n[!] CLOUDFLARE_REQUIRED: Cloudflare challenge detected.")
            print("Please solve the challenge manually in the Chrome window.")
            input("Press ENTER here after the page fully loads ZeusX...")
            page.goto(config.TARGET_URL, wait_until="domcontentloaded")
            
        login_indicators = page.get_by_role("link", name="Login", exact=False).or_(page.get_by_role("button", name="Login", exact=False))
        if login_indicators.count() > 0 or "login" in page.url.lower():
            print("\n[!] AUTH_REQUIRED: You are not logged in to ZeusX.")
            print("Please login manually in the Chrome window.")
            input("Press ENTER here after you have successfully logged in...")
            page.goto(config.TARGET_URL, wait_until="domcontentloaded")
            
        if "create-offer" not in page.url:
            print("\n[!] PAGE_NOT_READY: Failed to reach Create Offer page.")
            print("Please navigate to Create Offer manually.")
            input("Press ENTER here when ready...")
            
    def ensure_login(self, page: Page):
        """Ensures the page is ready for automation."""
        self.check_cloudflare_or_login(page)
        print("Page is ready. Starting automation...")

    def stop(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
