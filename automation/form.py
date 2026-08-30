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
        search_input = page.get_by_placeholder("Search by game name", exact=False).or_(page.get_by_placeholder("Search game", exact=False))
        if search_input.count() > 0 and search_input.first.is_visible():
            search_input.first.fill(game_name)
            page.wait_for_timeout(1000)
            
        game_option = page.locator("div.co-select-game_game-item___jTq9").filter(has_text=game_name).first
        game_option.wait_for(state="visible", timeout=10000)
        
        if "co-select-game_selected" not in game_option.get_attribute("class"):
            game_option.click()
            
        page.wait_for_timeout(1000)
        
        # Verify
        selected_game = page.locator("div.co-select-game_selected").first
        if not selected_game.is_visible() or game_name not in selected_game.inner_text():
             raise FormInteractionError(f"GAME_SELECTION_FAILED: Game '{game_name}' was not selected successfully.")
    except Exception as e:
        raise FormInteractionError(f"GAME_SELECTION_FAILED: {e}")

def select_server(page: Page, expected_server: str):
    print(f"    Server: Selecting '{expected_server}'...")
    try:
        dropdown_trigger = page.get_by_text("Please select one option")
        if dropdown_trigger.count() > 0 and dropdown_trigger.first.is_visible():
            dropdown_trigger.first.click()
            page.wait_for_timeout(500)
            
        server_option = page.get_by_role("radio", name=expected_server)
        if server_option.count() == 0:
            raise FormInteractionError(f"SERVER_SELECTION_FAILED: '{expected_server}' option not found.")
             
        server_option.first.click()
        page.wait_for_timeout(500)
        
        # Verify state
        if server_option.first.get_attribute("aria-checked") != "true":
             raise FormInteractionError(f"SERVER_VERIFICATION_FAILED: '{expected_server}' is not active after click.")
    except Exception as e:
        raise FormInteractionError(f"SERVER_SELECTION_FAILED: {e}")

def fill_title(page: Page, title: str):
    print(f"    Listing Title: {title[:30]}...")
    try:
        title_input = page.get_by_placeholder("Eg: Clash of Clans Account Lv 10")
        title_input.wait_for(state="visible", timeout=5000)
        title_input.fill(title)
        
        if title_input.input_value() != title:
            raise FormInteractionError("TITLE_VERIFICATION_FAILED: Value mismatch after fill.")
    except Exception as e:
        raise FormInteractionError(f"TITLE_VERIFICATION_FAILED: {e}")

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
        price_container = page.locator("label").filter(has_text="Price").locator("..")
        if price_container.count() > 0:
            price_input = price_container.locator("input[type='text']")
        else:
            price_input = page.locator("input[type='text']").filter(has_not=page.locator("[placeholder*='Clash of Clans']")).first

        price_input.fill(norm_price)
        page.wait_for_timeout(500)
        
        actual = price_input.input_value()
        if actual != norm_price:
             raise FormInteractionError(f"PRICE_VERIFICATION_FAILED. Expected {norm_price}, got {actual}")
    except Exception as e:
        raise FormInteractionError(f"PRICE_VERIFICATION_FAILED: {e}")

def ensure_multiple_quantity_disabled(page: Page):
    print("    Multiple Quantity: Ensuring disabled")
    try:
        qty_cb = page.get_by_role("checkbox", name="Multiple quantity?", exact=False)
        if qty_cb.count() > 0:
            if qty_cb.first.get_attribute("aria-checked") == "true":
                qty_box = qty_cb.first.locator(".checkbox_checkbox-box__2fLhD")
                if qty_box.count() > 0:
                     qty_box.first.click()
                else:
                     qty_cb.first.click(position={"x": 5, "y": 5})
                
                page.wait_for_timeout(500)
                if qty_cb.first.get_attribute("aria-checked") == "true":
                     raise FormInteractionError("Failed to uncheck multiple quantity.")
    except Exception as e:
        print(f"    Warning: Multiple Quantity interaction failed: {e}")

def select_delivery(page: Page):
    print("    Delivery Method: Ensuring Coordinated")
    try:
        del_radio = page.get_by_role("radio", name="Coordinated", exact=False)
        if del_radio.count() > 0:
            if del_radio.first.get_attribute("aria-checked") != "true":
                del_radio.first.click()
                page.wait_for_timeout(500)
                if del_radio.first.get_attribute("aria-checked") != "true":
                     raise FormInteractionError("DELIVERY_METHOD_VERIFICATION_FAILED")
                     
        days_label = page.get_by_text("Days", exact=True)
        if days_label.count() > 0:
             days_input = days_label.locator("xpath=preceding-sibling::input").first
             if days_input.is_visible() and days_input.input_value() != "0":
                  days_input.fill("0")
                  
        hours_label = page.get_by_text("Hours", exact=True)
        if hours_label.count() > 0:
             hours_input = hours_label.locator("xpath=preceding-sibling::input").first
             if hours_input.is_visible() and hours_input.input_value() != "1":
                  hours_input.fill("1")
    except Exception as e:
        raise FormInteractionError(f"Failed to set delivery method: {e}")

def fill_description(page: Page):
    print("    Description: Leaving default/empty")
    pass

def ensure_terms_checked(page: Page):
    print("    Terms: Ensuring terms checkbox is checked")
    try:
        terms_cb = page.get_by_role("checkbox", name="I agree with Terms of Service", exact=False)
        if terms_cb.count() == 0:
             raise FormInteractionError("TERMS_CHECKBOX_NOT_FOUND")
             
        if terms_cb.first.get_attribute("aria-checked") != "true":
             visual_box = terms_cb.first.locator(".checkbox_checkbox-box__2fLhD")
             if visual_box.count() > 0:
                  visual_box.first.click()
             else:
                  terms_cb.first.click(position={"x": 5, "y": 5})
                  
             page.wait_for_timeout(500)
             
        if terms_cb.first.get_attribute("aria-checked") != "true":
             raise FormInteractionError("TERMS_CHECK_FAILED: aria-checked is still false after click.")
             
        if "create-offer" not in page.url:
             raise FormInteractionError("TERMS_LINK_CLICK_DETECTED: URL changed to Terms of Service.")
             
    except FormInteractionError:
        raise
    except Exception as e:
        raise FormInteractionError(f"TERMS_CHECKBOX_INTERACTION_FAILED: {e}")
