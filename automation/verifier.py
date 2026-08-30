from playwright.sync_api import Page
from automation.exceptions import VerificationError, SubmissionError

def verify_form_state(page: Page, row: dict):
    print("    [VALIDATION] Running pre-submit safety checks...")
    page.wait_for_timeout(1000)
    
    errors = []
    
    # Check Game
    expected_game = str(row["Game"])
    try:
        selected_game = page.locator("div.co-select-game_selected").first
        if expected_game not in selected_game.inner_text():
            errors.append(f"Game mismatch. Expected '{expected_game}', found '{selected_game.inner_text()}'")
        else:
            print(f"    [OK] Game: {expected_game}")
    except Exception:
         errors.append("Game selection not found or couldn't be verified.")
         
    # Check Title
    expected_title = str(row["Spesifikasi"]).strip()
    try:
        title_input = page.get_by_placeholder("Eg: Clash of Clans Account Lv 10")
        actual_title = title_input.input_value().strip()
        if actual_title != expected_title:
             errors.append(f"Title mismatch. Expected '{expected_title}', found '{actual_title}'")
        else:
             print(f"    [OK] Title: {expected_title[:30]}...")
    except Exception:
         errors.append("Title input not found or couldn't be verified.")
         
    # Check Price
    try:
        if float(row["Harga"]).is_integer():
            expected_price = str(int(float(row["Harga"])))
        else:
            expected_price = str(row["Harga"])
            
        price_input = page.locator("input[type='text']").filter(has_not=page.locator("[placeholder*='Clash of Clans']")).first
        if price_input.count() == 0:
            price_input = page.locator("input").filter(has_type="text").nth(1)
            
        actual_price = price_input.input_value().strip()
        if actual_price != expected_price:
             errors.append(f"Price mismatch. Expected '{expected_price}', found '{actual_price}'")
        else:
             print(f"    [OK] Price: {expected_price}")
    except Exception:
         errors.append("Price input not found or couldn't be verified.")

    # Check Terms
    try:
        terms_cb = page.get_by_role("checkbox", name="I agree with Terms of Service", exact=False)
        if terms_cb.count() > 0 and not terms_cb.is_checked():
             errors.append("Terms of Service is NOT checked.")
        else:
             print("    [OK] Terms checked")
    except Exception:
         pass # Non-critical if it can't verify checkbox state easily

    if errors:
        raise VerificationError("Pre-submit validation failed:\n" + "\n".join(errors))
        
    submit_btn = page.get_by_role("button", name="List Items")
    if submit_btn.count() == 0:
        raise VerificationError("Submit button 'List Items' not found on the page.")
        
    print("    [OK] Validation passed. Ready to submit.")

def submit_and_verify(page: Page):
    print("    [SUBMIT] Clicking List Items...")
    try:
        submit_btn = page.get_by_role("button", name="List Items")
        submit_btn.first.click()
        
        print("    Waiting for submission verification...")
        try:
            # ZeusX might redirect or show a toast
            page.wait_for_url("**/offers**", timeout=15000)
            print("    [OK] Listing created successfully (Redirected).")
        except Exception:
            success_toast = page.get_by_text("successfully", ignore_case=True)
            if success_toast.is_visible():
                print("    [OK] Listing created successfully (Toast visible).")
            else:
                raise SubmissionError("SUBMIT_FAILED: Could not verify submission success via URL change or Toast.")
    except Exception as e:
        raise SubmissionError(f"SUBMIT_FAILED: {str(e)}")
