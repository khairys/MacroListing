import time
from playwright.sync_api import Page, expect
import config
from automation.exceptions import FormInteractionError

def prepare_next_listing(page: Page):
    """Resets the form state for the next listing."""
    if "create-offer" not in page.url:
        page.goto(config.TARGET_URL, wait_until="domcontentloaded")
    else:
        # If already on the page, we might just need to refresh to clear it
        # depending on if there's a "Create Another" button. Refresh is safest for now.
        page.reload(wait_until="domcontentloaded")
    
def select_category(page: Page):
    print("    Category: Selecting Account...")
    try:
        # Based on JSON: div with text Accounts\nGame accounts...
        category_btn = page.locator("div.co-select-category_sc-box__0qD2w").filter(has_text="Accounts")
        category_btn.wait_for(state="visible", timeout=10000)
        
        # Check if already active
        if "co-select-category_active" not in category_btn.get_attribute("class"):
            category_btn.click()
    except Exception as e:
        raise FormInteractionError(f"Failed to select category: {e}")

def select_game(page: Page, game_name: str):
    print(f"    Game: Searching and selecting '{game_name}'...")
    try:
        # Wait for game selection area to appear
        search_input = page.get_by_placeholder("Search", exact=False)
        if search_input.is_visible():
            search_input.fill(game_name)
            page.wait_for_timeout(1000) # Wait for debounce/search
            
        game_option = page.locator("div.co-select-game_game-item___jTq9").filter(has_text=game_name).first
        game_option.wait_for(state="visible", timeout=10000)
        
        if "co-select-game_selected" not in game_option.get_attribute("class"):
            game_option.click()
            
        page.wait_for_timeout(1000) # Wait for server list to update
    except Exception as e:
        raise FormInteractionError(f"Failed to select game: {e}")

def select_server(page: Page, expected_server: str):
    print(f"    Server: Selecting '{expected_server}'...")
    try:
        # Open dropdown if it exists
        dropdown_trigger = page.locator(".select-form_select-wrapper__wIt_A").or_(page.get_by_text("Please select one option"))
        if dropdown_trigger.count() > 0 and dropdown_trigger.first.is_visible():
            dropdown_trigger.first.click()
            page.wait_for_timeout(500)
            
        # Select radio
        server_option = page.get_by_role("radio", name=expected_server)
        if server_option.count() == 0:
            # Fallback if it's not a radio but a div
            server_option = page.locator("div").filter(has_text=expected_server).filter(has=page.locator("input[type='radio']"))
            
        if server_option.count() == 0:
             raise FormInteractionError(f"SERVER_NOT_FOUND: {expected_server}")
             
        server_option.first.click()
        page.wait_for_timeout(500)
    except Exception as e:
        raise FormInteractionError(f"INVALID_SERVER: Failed to select server '{expected_server}': {e}")

def fill_title(page: Page, title: str):
    print(f"    Listing Title: {title[:30]}...")
    try:
        title_input = page.get_by_placeholder("Eg: Clash of Clans Account Lv 10")
        title_input.wait_for(state="visible", timeout=5000)
        title_input.fill(title)
        
        # Verify
        if title_input.input_value() != title:
            raise FormInteractionError("TITLE_FILL_FAILED: Value mismatch after fill.")
    except Exception as e:
        raise FormInteractionError(f"Failed to fill listing title: {e}")

def fill_price(page: Page, price: str):
    print(f"    Price: {price}")
    try:
        if float(price).is_integer():
            norm_price = str(int(float(price)))
        else:
            norm_price = str(price)
    except:
        norm_price = str(price)
        
    try:
        # Price is likely the next text input after title
        price_input = page.locator("input[type='text']").filter(has_not=page.locator("[placeholder*='Clash of Clans']")).first
        
        # Alternative fallback: look for an input near a $ sign or Price text
        if price_input.count() == 0 or not price_input.is_visible():
            price_input = page.locator("input").filter(has_type="text").nth(1)

        price_input.fill(norm_price)
        
        # Wait and verify
        page.wait_for_timeout(500)
        actual = price_input.input_value()
        if actual != norm_price:
             print(f"    Warning: Price mismatch. Expected {norm_price}, got {actual}")
    except Exception as e:
        raise FormInteractionError(f"PRICE_FILL_FAILED: Failed to fill price: {e}")

def select_quantity(page: Page):
    print("    Multiple Quantity: No")
    try:
        qty_cb = page.get_by_role("checkbox", name="Multiple quantity?", exact=False)
        if qty_cb.count() > 0:
            if qty_cb.is_checked():
                qty_cb.uncheck()
    except Exception as e:
        print(f"    Warning: Multiple Quantity selection failed: {e}")

def select_delivery(page: Page):
    print("    Delivery Method: Coordinated")
    try:
        del_radio = page.get_by_role("radio", name="Coordinated", exact=False)
        if del_radio.count() > 0:
            if not del_radio.is_checked():
                del_radio.check()
    except Exception as e:
        raise FormInteractionError(f"Failed to set delivery method: {e}")

def fill_description(page: Page):
    print("    Description: Leaving default/empty")
    # Intentional no-op. CKEditor is complex and we shouldn't touch it if not needed.
    pass

def check_terms(page: Page):
    print("    Terms: Checking terms checkbox")
    try:
        terms_cb = page.get_by_role("checkbox", name="I agree with Terms of Service", exact=False)
        if terms_cb.count() > 0:
             if not terms_cb.is_checked():
                 terms_cb.check()
    except Exception as e:
        raise FormInteractionError(f"TERMS_CHECK_FAILED: {e}")
