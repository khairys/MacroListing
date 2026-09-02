"""MacroListing — Clear/Delete all existing listings.

Navigates to My Listing page, selects all, and removes them.
Uses exit codes to communicate results to the scheduler.

Exit codes:
    0 = SUCCESS (listings cleared, or page was already empty)
    1 = FAILED (automation error during cleanup)
    2 = SITE_UNAVAILABLE (ZeusX is down)
    3 = AUTH_REQUIRED (login needed)
"""

import sys
import os
import re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.sync_api import TimeoutError as PlaywrightTimeout

import config
from automation.browser import BrowserManager
from automation.site_health import check_site_health, SiteStatus
from automation.exceptions import (
    SiteError, SiteUnavailableError, AuthenticationError,
    NetworkError, CloudflareChallengeError, PageNotReadyError
)


def clear_all_listings() -> int:
    """Clears all listings from ZeusX My Listing page.
    
    Returns:
        Exit code (0=success, 1=failed, 2=site unavailable, 3=auth required)
    """
    print("="*50)
    print("Starting Auto-Delete Listings process...")
    print("="*50)
    
    bm = BrowserManager()
    try:
        page = bm.start()
    except NetworkError as e:
        print(f"[SITE ERROR] Browser connection failed: {e}")
        return config.EXIT_SITE_UNAVAILABLE
    except Exception as e:
        print(f"[FATAL] Browser setup failed: {e}")
        return config.EXIT_AUTOMATION_FAILURE
        
    try:
        # --- Site health check BEFORE doing anything ---
        print("Navigating to My Listing page...")
        status = check_site_health(page, "https://zeusx.com/my-listing")
        
        if status == SiteStatus.AUTH_REQUIRED:
            print("[AUTH] Login required. Cannot clear listings.")
            return config.EXIT_AUTH_REQUIRED
        elif status == SiteStatus.CLOUDFLARE_CHALLENGE:
            print("[CLOUDFLARE] Security challenge active. Cannot clear listings.")
            return config.EXIT_SITE_UNAVAILABLE
        elif status != SiteStatus.SITE_READY:
            print(f"[SITE ERROR] ZeusX not ready: {status.value}")
            return config.EXIT_SITE_UNAVAILABLE
        
        # --- Page is healthy. Now check for listings ---
        print("Checking for existing listings...")
        
        # We need to distinguish "no listings exist" from "page didn't load"
        # First verify we are actually on my-listing page
        if "my-listing" not in page.url:
            print("[SITE ERROR] Not on My Listing page after navigation.")
            return config.EXIT_SITE_UNAVAILABLE
        
        try:
            first_checkbox = page.locator("div[class*='my-listing-table_checkbox']").first
            first_checkbox.wait_for(state="visible", timeout=config.ELEMENT_TIMEOUT)
        except PlaywrightTimeout:
            # Page loaded fine (health check passed), but no checkboxes → truly empty
            # Double-check by looking for any listing content
            listing_rows = page.locator("div[class*='my-listing-table_row']")
            if listing_rows.count() == 0:
                print("No listings found. The page is already clean!")
                return config.EXIT_SUCCESS
            else:
                # Rows exist but no checkboxes? Something weird.
                print("[WARNING] Listing rows detected but no checkboxes. Page may be loading slowly.")
                page.wait_for_timeout(3000)
                try:
                    first_checkbox = page.locator("div[class*='my-listing-table_checkbox']").first
                    first_checkbox.wait_for(state="visible", timeout=5000)
                except PlaywrightTimeout:
                    print("[ERROR] Checkboxes still not visible. Cannot proceed.")
                    return config.EXIT_AUTOMATION_FAILURE

        # 1. Click first listing checkbox to trigger the action badge
        print("Clicking the first listing to trigger the action badge...")
        first_checkbox.click(force=True)
        page.wait_for_timeout(1000)

        # 2. Click 'Select All'
        print("Clicking 'Select all'...")
        try:
            select_all_text = page.locator("div[class*='checkbox_label']").filter(
                has_text=re.compile(r"^Select all", re.IGNORECASE)
            )
            if select_all_text.count() > 0:
                select_all_text.first.click(force=True)
            else:
                print("Could not find 'Select all' text.")
                return config.EXIT_AUTOMATION_FAILURE
        except Exception as e:
            print(f"Failed to click Select all: {e}")
            return config.EXIT_AUTOMATION_FAILURE
            
        page.wait_for_timeout(1000)
        
        # 3. Click 'Remove Listing' action
        print("Clicking 'Remove Listing' action...")
        try:
            remove_btn = page.get_by_text(re.compile(r"Remove Listing|Delete|Remove", re.IGNORECASE))
            if remove_btn.count() > 0 and remove_btn.first.is_visible():
                remove_btn.first.click(force=True)
            else:
                # Fallback to SVG action icons in the badge
                print("Text button not found. Looking for SVG action icons...")
                actions = page.locator("div[class*='select-multiple-badge_action']")
                if actions.count() > 0:
                    clicked = False
                    for i in range(actions.count()):
                        text = actions.nth(i).inner_text().lower()
                        if "remove" in text or "delete" in text:
                            actions.nth(i).click(force=True)
                            clicked = True
                            break
                    if not clicked:
                        print("Warning: Clicking the last action icon.")
                        actions.last.click(force=True)
                else:
                    print("ERROR: Could not find any Remove/Delete action buttons.")
                    return config.EXIT_AUTOMATION_FAILURE
        except Exception as e:
            print(f"Failed to click Remove Listing: {e}")
            return config.EXIT_AUTOMATION_FAILURE
            
        page.wait_for_timeout(1500)
        
        # 4. Handle Confirmation Modal
        print("Checking for Confirmation modal...")
        try:
            confirm_btn = page.locator("button").filter(
                has_text=re.compile(r"Yes|Confirm|Remove|Delete|Ok", re.IGNORECASE)
            )
            if confirm_btn.count() > 0 and confirm_btn.first.is_visible():
                btn_text = confirm_btn.first.inner_text()
                print(f"Found confirmation button: '{btn_text}'. Clicking it...")
                confirm_btn.first.click(force=True)
            else:
                print("No confirmation modal detected.")
        except Exception as e:
            print(f"Failed during confirmation: {e}")
            
        # 5. Wait for success verification
        print("Waiting for success verification...")
        try:
            toast = page.locator("div[class*='toast_toast']").first
            toast.wait_for(state="visible", timeout=10000)
            print("SUCCESS! Listings have been removed.")
        except PlaywrightTimeout:
            print("Warning: No success toast detected, but process completed.")
            
        print("="*50)
        print("Clean up finished. You can now run main.py to upload new data.")
        print("="*50)
        return config.EXIT_SUCCESS

    except SiteError as e:
        print(f"[SITE ERROR] {e}")
        if isinstance(e, AuthenticationError):
            return config.EXIT_AUTH_REQUIRED
        return config.EXIT_SITE_UNAVAILABLE
    except Exception as e:
        print(f"[FATAL] Unexpected error: {e}")
        return config.EXIT_AUTOMATION_FAILURE
    finally:
        bm.stop()


if __name__ == "__main__":
    try:
        code = clear_all_listings()
        sys.exit(code if code is not None else 0)
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Cleanup stopped by user.")
        sys.exit(config.EXIT_INTERRUPTED)
