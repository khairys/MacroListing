import time
from playwright.sync_api import Page
import config

def wait_for_user_login(page: Page):
    """
    Checks if user is logged in, and if not, waits for manual login.
    """
    # TODO: Inspect actual ZeusX DOM to determine login state accurately.
    # Placeholder logic: waiting for a specific element that only appears when logged in.
    print("    [MOCK] Please ensure you are logged in. Waiting if necessary...")
    pass

def fill_listing_form(page: Page, row_data: dict):
    """
    Fills the ZeusX Create Offer form using the provided row data.
    """
    # Navigate to target URL
    print(f"    Navigating to: {config.TARGET_URL}")
    page.goto(config.TARGET_URL)
    
    # Check login state (Implementation pending actual DOM)
    wait_for_user_login(page)
    
    game = str(row_data["Game"]).strip()
    server = str(row_data["Server"]).strip()
    harga = str(row_data["Harga"]).strip()
    spesifikasi = str(row_data["Spesifikasi"]).strip()
    
    # 1. Category
    # TODO: Inspect actual ZeusX DOM and replace locator.
    print("    [MOCK] Selecting Category: Account")
    # page.get_by_text("Category").click()
    # page.get_by_text("Account").click()
    
    # 2. Game
    # TODO: Inspect actual ZeusX DOM and replace locator.
    print(f"    [MOCK] Selecting game: {game}")
    
    # 3. Server
    # TODO: Inspect actual ZeusX DOM and replace locator.
    print(f"    [MOCK] Selecting server: {server}")
    
    # 4. Listing Title (Spesifikasi)
    # TODO: Inspect actual ZeusX DOM and replace locator.
    print(f"    [MOCK] Filling Listing Title: {spesifikasi}")
    
    # 5. Price
    # TODO: Inspect actual ZeusX DOM and replace locator.
    print(f"    [MOCK] Filling Price: {harga}")
    
    # 6. Multiple Quantity -> No
    # TODO: Inspect actual ZeusX DOM and replace locator.
    print("    [MOCK] Selecting Multiple Quantity: No")
    
    # 7. Delivery Method -> Coordinated
    # TODO: Inspect actual ZeusX DOM and replace locator.
    print("    [MOCK] Selecting Delivery Method: Coordinated")
    
    # 8. Delivery Time -> Days = 0, Hours = 1
    # TODO: Inspect actual ZeusX DOM and replace locator.
    print("    [MOCK] Filling Delivery Time: Days=0, Hours=1")
    
    # 9. Description -> Empty
    # TODO: Inspect actual ZeusX DOM and replace locator.
    print("    [MOCK] Ensuring Description is empty")
    
    # 10. Check Terms & Privacy
    # TODO: Inspect actual ZeusX DOM and replace locator.
    print("    [MOCK] Checking Terms & Privacy checkbox if available")
    
def submit_form(page: Page):
    """
    Submits the form if DRY_RUN is False.
    """
    if config.DRY_RUN:
        print("    [DRY RUN] Skipping 'List Items' submission.")
    else:
        # TODO: Inspect actual ZeusX DOM and replace locator.
        # page.get_by_role("button", name="List Items").click()
        print("    [SUBMIT] Clicking 'List Items'")
