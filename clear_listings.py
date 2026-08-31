import time
import re
from playwright.sync_api import TimeoutError

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from automation.browser import BrowserManager

def clear_all_listings():
    print("="*50)
    print("Starting Auto-Delete Listings process...")
    print("="*50)
    
    bm = BrowserManager()
    try:
        page = bm.start()
    except Exception as e:
        print(f"Browser setup failed: {e}")
        return
        
    try:
        print("Navigating to My Listing page...")
        page.goto("https://zeusx.com/my-listing")
        try:
            page.wait_for_load_state("domcontentloaded", timeout=10000)
        except TimeoutError:
            pass
        page.wait_for_timeout(3000)
        
        # Check if there are any listings by looking for checkboxes
        print("Checking for existing listings...")
        try:
            # Wait for at least one checkbox to appear
            first_checkbox = page.locator("div[class*='my-listing-table_checkbox']").first
            first_checkbox.wait_for(state="visible", timeout=10000)
            
            # Click the first checkbox to trigger the action badge
            print("Clicking the first listing to trigger the action badge...")
            first_checkbox.click(force=True)
            page.wait_for_timeout(1000)
        except TimeoutError:
            print("No listings found. The page is already clean!")
            return

        # 1. Click 'Select All'
        print("Clicking 'Select all'...")
        try:
            # The 'Select all (X)' checkbox appears in the bottom badge
            select_all_text = page.locator("div[class*='checkbox_label']").filter(has_text=re.compile(r"^Select all", re.IGNORECASE))
            if select_all_text.count() > 0:
                select_all_text.first.click(force=True)
            else:
                print("Could not find 'Select all' text. Attempting to click the main checkbox header.")
                page.locator("div[class*='checkbox_checkbox']").first.click(force=True)
        except Exception as e:
            print(f"Failed to click Select all: {e}")
            return
            
        page.wait_for_timeout(1000)
        
        # 2. Click 'Remove Listing' (or Delete icon)
        print("Clicking 'Remove Listing' action...")
        try:
            # We first try to find exact text
            remove_btn = page.get_by_text(re.compile(r"Remove Listing|Delete|Remove", re.IGNORECASE))
            if remove_btn.count() > 0 and remove_btn.first.is_visible():
                remove_btn.first.click(force=True)
            else:
                # Fallback to clicking the trash/remove icon in the select-multiple-badge
                print("Text button not found. Looking for SVG action icons...")
                actions = page.locator("div[class*='select-multiple-badge_action']")
                if actions.count() > 0:
                    for i in range(actions.count()):
                        text = actions.nth(i).inner_text().lower()
                        if "remove" in text or "delete" in text:
                            actions.nth(i).click(force=True)
                            break
                    else:
                        print("Warning: Clicking the last action icon, assuming it is Delete/Remove.")
                        actions.last.click(force=True)
                else:
                    print("ERROR: Could not find any Remove/Delete action buttons.")
                    return
        except Exception as e:
            print(f"Failed to click Remove Listing: {e}")
            return
            
        page.wait_for_timeout(1500)
        
        # 3. Handle Confirmation Modal
        print("Checking for Confirmation modal...")
        try:
            # Confirm button could be "Yes", "Confirm", "Remove", "Delete", "Ok", "Remove multiple"
            confirm_btn = page.locator("button").filter(has_text=re.compile(r"Yes|Confirm|Remove|Delete|Ok", re.IGNORECASE))
            if confirm_btn.count() > 0 and confirm_btn.first.is_visible():
                print(f"Found confirmation button: '{confirm_btn.first.inner_text()}'. Clicking it...")
                confirm_btn.first.click(force=True)
            else:
                print("No confirmation modal detected, or it auto-deleted.")
        except Exception as e:
            print(f"Failed during confirmation: {e}")
            
        # 4. Wait for success toast
        print("Waiting for success verification...")
        try:
            toast = page.locator("div[class*='toast_toast']").first
            toast.wait_for(state="visible", timeout=10000)
            print("SUCCESS! Listings have been removed.")
        except TimeoutError:
            print("Finished execution (No success toast detected, but process completed).")
            
        print("="*50)
        print("Clean up finished. You can now run main.py to upload new data.")
        print("="*50)

    finally:
        bm.stop()

if __name__ == "__main__":
    clear_all_listings()
