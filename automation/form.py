from playwright.sync_api import Page, expect
import config
from automation.exceptions import FormInteractionError

def prepare_next_listing(page: Page):
    """Resets the form state for the next listing."""
    page.goto(config.TARGET_URL, wait_until="domcontentloaded")
    
def select_category(page: Page):
    print("    Category: Selecting Account...")
    try:
        category_trigger = page.get_by_text("Select Category", exact=False).or_(page.locator("label:has-text('Category') ~ div"))
        category_trigger.click()
        page.get_by_role("option", name="Account").click()
    except Exception as e:
        raise FormInteractionError(f"Failed to select category: {e}")

def select_game(page: Page, game_name: str):
    print(f"    Game: Searching and selecting '{game_name}'...")
    try:
        game_trigger = page.get_by_placeholder("Search game", exact=False).or_(page.locator("label:has-text('Game') ~ div"))
        game_trigger.click()
        
        search_input = page.get_by_role("textbox", name="Search game", exact=False).or_(page.locator("input[placeholder*='Search']"))
        if search_input.is_visible():
            search_input.fill(game_name)
        
        game_option = page.get_by_role("option", name=game_name, exact=True)
        game_option.wait_for(state="visible", timeout=10000)
        game_option.click()
    except Exception as e:
        raise FormInteractionError(f"Failed to select game: {e}")

def select_server(page: Page, expected_server: str):
    print(f"    Server: Selecting '{expected_server}'...")
    try:
        server_container = page.locator("label:has-text('Server') ~ div")
        server_container.wait_for(state="visible", timeout=10000)
        server_container.click()
        
        server_option = page.get_by_role("option", name=expected_server, exact=True)
        server_option.wait_for(state="visible", timeout=5000)
        server_option.click()
    except Exception as e:
        raise FormInteractionError(f"Failed to select server: {e}")

def fill_title(page: Page, title: str):
    print(f"    Listing Title: {title[:30]}...")
    try:
        title_input = page.get_by_label("Listing Title", exact=False).or_(page.get_by_placeholder("Enter title", exact=False))
        title_input.fill(title)
    except Exception as e:
        raise FormInteractionError(f"Failed to fill listing title: {e}")

def fill_price(page: Page, price: str):
    print(f"    Price: {price}")
    try:
        norm_price = str(int(float(price)))
    except:
        norm_price = str(price)
        
    try:
        price_input = page.get_by_label("Price", exact=False).or_(page.locator("input[type='number']"))
        price_input.fill(norm_price)
    except Exception as e:
        raise FormInteractionError(f"Failed to fill price: {e}")

def select_quantity(page: Page):
    print("    Multiple Quantity: No")
    try:
        qty_no = page.get_by_label("Multiple Quantity", exact=False).or_(page.get_by_text("Multiple Quantity")).locator("..").get_by_text("No")
        if qty_no.is_visible():
            qty_no.click()
    except Exception as e:
        print(f"    Warning: Multiple Quantity selection failed (might not exist): {e}")

def select_delivery(page: Page):
    print("    Delivery Method: Coordinated")
    try:
        del_method = page.get_by_label("Delivery Method", exact=False).or_(page.get_by_text("Delivery Method")).locator("..").get_by_text("Coordinated")
        if del_method.is_visible():
            del_method.click()
            
        print("    Delivery Time: 0 Days, 1 Hour")
        days_input = page.get_by_placeholder("Days", exact=False).or_(page.locator("input[name*='day']"))
        if days_input.is_visible():
            days_input.fill("0")
            
        hours_input = page.get_by_placeholder("Hours", exact=False).or_(page.locator("input[name*='hour']"))
        if hours_input.is_visible():
            hours_input.fill("1")
    except Exception as e:
        raise FormInteractionError(f"Failed to set delivery details: {e}")

def fill_description(page: Page):
    print("    Description: Leaving empty")
    try:
        desc_input = page.get_by_label("Description", exact=False).or_(page.locator("textarea"))
        if desc_input.is_visible():
            desc_input.fill("")
    except Exception as e:
        print(f"    Warning: Description fill failed (might not exist): {e}")

def check_terms(page: Page):
    print("    Terms: Checking terms checkbox")
    try:
        terms_cb = page.get_by_role("checkbox", name="terms", exact=False).or_(page.locator("input[type='checkbox']").first)
        if terms_cb.is_visible() and not terms_cb.is_checked():
            terms_cb.check()
    except Exception as e:
        print(f"    Warning: Check terms failed (might not exist): {e}")
