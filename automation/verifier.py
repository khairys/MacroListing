from playwright.sync_api import Page
from automation.exceptions import VerificationError, SubmissionError

def verify_form_state(page: Page, row: dict):
    print("    Verifying form state before submission...")
    page.wait_for_timeout(1000) # Give framework time to render state
    
    # Extract body text for simple sanity checking
    body_text = page.locator("body").inner_text()
    
    title = str(row["Spesifikasi"]).strip()
    if title not in body_text:
         print("    Warning: Listing Title not found in page text. Verification might be incomplete.")
         
    submit_btn = page.get_by_role("button", name="List Items").or_(page.get_by_text("List Items", exact=True))
    if submit_btn.count() == 0:
        raise VerificationError("Submit button 'List Items' not found on the page.")
        
    print("    Form verified ✓")

def submit_and_verify(page: Page):
    print("    Submitting...")
    try:
        submit_btn = page.get_by_role("button", name="List Items").or_(page.get_by_text("List Items", exact=True))
        submit_btn.first.click()
        
        print("    Waiting for submission verification...")
        try:
            page.wait_for_url("**/offers**", timeout=15000)
            print("    Submission verified (Redirected) ✓")
        except Exception:
            success_toast = page.get_by_text("successfully", ignore_case=True)
            if success_toast.is_visible():
                print("    Submission verified (Toast visible) ✓")
            else:
                raise SubmissionError("Could not verify submission success via URL change or Toast.")
    except Exception as e:
        raise SubmissionError(f"Submission interaction failed: {str(e)}")
