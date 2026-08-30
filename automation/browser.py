import os
from playwright.sync_api import sync_playwright, BrowserContext, Page
import config

class BrowserManager:
    def __init__(self):
        self.playwright = None
        self.context = None

    def start(self) -> Page:
        self.playwright = sync_playwright().start()
        
        # Use persistent context to keep login sessions in browser-profile folder
        os.makedirs(config.BROWSER_PROFILE_PATH, exist_ok=True)
        
        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=config.BROWSER_PROFILE_PATH,
            headless=config.HEADLESS,
            viewport={"width": 1280, "height": 720}
        )
        
        # If no pages exist in the context, create one
        if len(self.context.pages) > 0:
            page = self.context.pages[0]
        else:
            page = self.context.new_page()
            
        return page

    def stop(self):
        if self.context:
            self.context.close()
        if self.playwright:
            self.playwright.stop()
