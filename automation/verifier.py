from playwright.sync_api import Page
from automation.exceptions import VerificationError, SubmissionError

def verify_form_state(page: Page, row: dict):
    print("    [VALIDATION] Running pre-submit safety checks...")
    page.wait_for_timeout(1000)
    
    errors = []
    
    # Check Game
    expected_game = str(row["Game"])
    try:
        selected_game = page.locator("div[class*='co-select-game_selected']").first
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
            
        price_container = page.locator("label").filter(has_text="Price").locator("..")
        if price_container.count() > 0:
            price_input = price_container.locator("input[type='text']")
        else:
            price_input = page.locator("input[type='text']").filter(has_not=page.locator("[placeholder*='Clash of Clans']")).first
            
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
        if terms_cb.count() > 0 and terms_cb.first.get_attribute("aria-checked") != "true":
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
            import re
            success_toast = page.get_by_text(re.compile("successfully", re.IGNORECASE))
            if success_toast.first.is_visible():
                print("    [OK] Listing created successfully (Toast visible).")
            else:
                from automation.exceptions import SubmissionUnknownError
                raise SubmissionUnknownError("SUBMISSION_UNKNOWN: Could not verify submission success. URL did not change and success toast not found.")
    except Exception as e:
        from automation.exceptions import SubmissionUnknownError
        if "SUBMISSION_UNKNOWN" in str(e):
            raise
        raise SubmissionError(f"SUBMIT_FAILED: {str(e)}")
