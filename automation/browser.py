import os
from playwright.sync_api import sync_playwright, Page, expect
import config
from automation.exceptions import CaptchaDetectedError, LoginRequiredError

class BrowserManager:
    def __init__(self):
        self.playwright = None
        self.context = None

    def start(self) -> Page:
        self.playwright = sync_playwright().start()
        os.makedirs(config.BROWSER_PROFILE_PATH, exist_ok=True)
        
        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=config.BROWSER_PROFILE_PATH,
            headless=config.HEADLESS,
            viewport={"width": 1280, "height": 720},
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        if len(self.context.pages) > 0:
            page = self.context.pages[0]
        else:
            page = self.context.new_page()
            
        return page

    def check_captcha(self, page: Page):
        """Checks if a CAPTCHA iframe or element is visible."""
        if page.locator("iframe[src*='recaptcha'], iframe[src*='hcaptcha'], .cf-turnstile").count() > 0:
            raise CaptchaDetectedError("CAPTCHA DETECTED - PLEASE COMPLETE IT MANUALLY")

    def ensure_login(self, page: Page):
        """Navigates to the target URL and checks for login state."""
        print(f"Navigating to {config.TARGET_URL}...")
        page.goto(config.TARGET_URL, wait_until="domcontentloaded")
        
        login_indicators = page.get_by_role("link", name="Login", exact=False).or_(page.get_by_role("button", name="Login", exact=False))
        
        if login_indicators.count() > 0 or "login" in page.url.lower():
            print("WAITING FOR MANUAL LOGIN. Please login in the browser window...")
            page.wait_for_url("**/create-offer**", timeout=0) # wait infinitely
            print("LOGIN DETECTED.")
        else:
            print("LOGIN DETECTED.")
            
        self.check_captcha(page)

    def stop(self):
        if self.context:
            self.context.close()
        if self.playwright:
            self.playwright.stop()
