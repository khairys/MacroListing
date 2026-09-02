import time
from playwright.sync_api import Page, expect
import config
from automation.exceptions import FormInteractionError, SiteError
from automation.site_health import quick_page_health_check, raise_for_status, SiteStatus


def page_health_guard(page: Page):
    """Checks that the page is still healthy before a critical form operation.
    
    Raises SiteError (not FormInteractionError) if the page has silently
    changed to Cloudflare, error page, login page, etc.
    """
    status = quick_page_health_check(page)
    if status != SiteStatus.SITE_READY:
        raise_for_status(status)


def prepare_next_listing(page: Page):
    """Resets the form state for the next listing."""
    page_health_guard(page)
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
    page_health_guard(page)
    try:
        search_input = page.get_by_placeholder("Search by game name", exact=False).or_(page.get_by_placeholder("Search game", exact=False))
        if search_input.count() > 0 and search_input.first.is_visible():
            search_input.first.fill(game_name)
            page.wait_for_timeout(1000)
            
        import re
        game_options = page.locator("div.co-select-game_game-item___jTq9").filter(has_text=re.compile(f"^{re.escape(game_name)}$", re.IGNORECASE))
        try:
            game_options.first.wait_for(state="visible", timeout=10000)
        except Exception:
            pass # fallback to error checking below
        
        count = game_options.count()
        if count == 0:
            raise FormInteractionError(f"GAME_NOT_FOUND: Could not find exact match for '{game_name}'")
        elif count > 1:
            raise FormInteractionError(f"GAME_AMBIGUOUS: Found {count} exact matches for '{game_name}'")
            
        game_option = game_options.first
        
        if "co-select-game_selected" not in game_option.get_attribute("class"):
            game_option.click()
            
        page.wait_for_timeout(1000)
        
        # Verify
        selected_game = page.locator("div[class*='co-select-game_selected']").first
        if not selected_game.is_visible() or game_name.lower() != selected_game.inner_text().strip().lower():
             raise FormInteractionError(f"GAME_SELECTION_FAILED: Game '{game_name}' was not selected successfully.")
    except Exception as e:
        if isinstance(e, FormInteractionError):
            raise
        raise FormInteractionError(f"GAME_SELECTION_FAILED: {e}")

def select_server(page: Page, expected_server: str):
    print(f"    Server: Selecting '{expected_server}'...")
    try:
        # Find the label exactly matching "Server" to get its container
        import re
        label = page.locator("div[class*='label']").filter(has_text=re.compile(r"^Server$")).first
        if label.count() == 0:
            label = page.locator("div").filter(has_text=re.compile(r"^Server$")).first
            
        server_container = label.locator("..")
        
        # Check if already selected
        wrapper = server_container.locator("div[class*='select-wrapper']").first
        if wrapper.count() > 0:
            if expected_server in wrapper.inner_text():
                return
            wrapper.click()
            page.wait_for_timeout(500)
        else:
            # Fallback if wrapper not found, click the text directly
            fallback_trigger = server_container.get_by_text("Please select one option")
            if fallback_trigger.count() > 0 and fallback_trigger.first.is_visible():
                fallback_trigger.first.click()
                page.wait_for_timeout(500)
            
        server_option = page.get_by_role("radio", name=expected_server, exact=True)
        try:
            server_option.first.wait_for(state="visible", timeout=5000)
        except Exception:
            raise FormInteractionError(f"SERVER_SELECTION_FAILED: '{expected_server}' option not visible after click.")
             
        server_option.first.click()
        page.wait_for_timeout(1000)
        
        # Verify state
        if server_container.count() > 0 and server_container.is_visible():
            wrapper = server_container.locator(".select-form_select-wrapper__wIt_A").first
            if wrapper.count() > 0 and expected_server not in wrapper.inner_text():
                 raise FormInteractionError(f"SERVER_VERIFICATION_FAILED: '{expected_server}' is not active after click.")
    except Exception as e:
        raise FormInteractionError(f"SERVER_SELECTION_FAILED: {e}")

def select_optional_dropdown(page: Page, label_name: str, option_value: str):
    if not option_value or option_value.lower() == "none" or str(option_value).strip() == "":
        return # Skip if no value provided
        
    print(f"    {label_name}: Selecting '{option_value}'...")
    try:
        import re
        label = page.locator("div[class*='label']").filter(has_text=re.compile(f"^{re.escape(label_name)}$")).first
        if label.count() == 0:
            label = page.locator("div").filter(has_text=re.compile(f"^{re.escape(label_name)}$")).first
            
        if label.count() == 0:
            print(f"    Warning: Dropdown label '{label_name}' not found. Skipping.")
            return
            
        container = label.locator("..")
        wrapper = container.locator("div[class*='select-wrapper']").first
        
        if wrapper.count() > 0:
            if option_value in wrapper.inner_text():
                return
            wrapper.click()
            page.wait_for_timeout(500)
        else:
            fallback_trigger = container.get_by_text("Please select one option")
            if fallback_trigger.count() > 0 and fallback_trigger.first.is_visible():
                fallback_trigger.first.click()
                page.wait_for_timeout(500)
                
        option_elem = page.get_by_role("radio", name=option_value, exact=True)
        try:
            option_elem.first.wait_for(state="visible", timeout=5000)
        except Exception:
            raise FormInteractionError(f"DROPDOWN_SELECTION_FAILED: '{option_value}' option not visible after click for {label_name}.")
             
        option_elem.first.click()
        page.wait_for_timeout(1000)
        
    except Exception as e:
        raise FormInteractionError(f"DROPDOWN_SELECTION_FAILED ({label_name}): {e}")

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
             days_input = days_label.locator("xpath=following-sibling::div//input").first
             if days_input.is_visible() and days_input.input_value() != "0":
                  days_input.fill("0")
                  
        hours_label = page.get_by_text("Hours", exact=True)
        if hours_label.count() > 0:
             hours_input = hours_label.locator("xpath=following-sibling::div//input").first
             if hours_input.is_visible() and hours_input.input_value() != "1":
                  hours_input.fill("1")
    except Exception as e:
        raise FormInteractionError(f"Failed to set delivery method: {e}")

def fill_description(page: Page):
    print("    Description: Leaving default/empty")
    pass

def ensure_terms_checked(page: Page):
    print("    Terms: Ensuring terms checkbox is checked")
    page_health_guard(page)
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
