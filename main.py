"""MacroListing — Main automation script.

Reads listing data from Excel, fills ZeusX forms, and uploads images.
Uses exit codes to communicate results to the scheduler/orchestrator.

Exit codes:
    0 = SUCCESS (all listings processed)
    1 = AUTOMATION_FAILURE (some listings failed due to form/bot errors)
    2 = SITE_UNAVAILABLE (ZeusX is down or unreachable)
    3 = AUTH_REQUIRED (login session expired)
    4 = SUBMISSION_UNKNOWN (at least one listing has unknown submit status)
    5 = INTERRUPTED
"""

import os
import sys
import datetime
import openpyxl

import config
from automation.validator import validate_dataset, resolve_images
from automation.browser import BrowserManager
from automation.site_health import check_site_health, raise_for_status, SiteStatus
from automation.form import (
    prepare_next_listing, select_category, select_game,
    select_server, select_optional_dropdown, fill_title, fill_price,
    ensure_multiple_quantity_disabled,
    select_delivery, fill_description, ensure_terms_checked
)
from automation.uploader import upload_images
from automation.verifier import verify_form_state, submit_and_verify
from automation.exceptions import (
    ValidationError, FormInteractionError, ImageUploadError,
    CaptchaDetectedError, VerificationError, SubmissionError,
    SubmissionUnknownError,
    SiteError, AuthenticationError
)
from automation.retry_policy import is_retryable_for_listing
from automation import state_manager


def setup_directories():
    os.makedirs(config.LOGS_DIR, exist_ok=True)
    os.makedirs(config.SCREENSHOTS_DIR, exist_ok=True)
    os.makedirs(os.path.join(config.LOGS_DIR, "errors"), exist_ok=True)
    os.makedirs(config.RUNTIME_DIR, exist_ok=True)


def log_result(msg: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] {msg}"
    print(formatted_msg)
    with open(os.path.join(config.LOGS_DIR, "automation.log"), "a", encoding="utf-8") as f:
        f.write(formatted_msg + "\n")


def read_excel() -> list[dict]:
    wb = openpyxl.load_workbook(config.EXCEL_FILE_PATH, data_only=True)
    sheet = wb.active
    headers = [str(cell.value) for cell in sheet[1]]
    data = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        # Skip completely empty rows
        if all(cell is None for cell in row):
            continue
        
        row_dict = {headers[i]: value for i, value in enumerate(row) if i < len(headers)}
        
        # Additional safety check: If 'No' column is empty, it's a ghost row. Skip it.
        if not row_dict.get("No") or str(row_dict.get("No")).strip() == "":
            continue
            
        data.append(row_dict)
    return data


def normalize_no(val):
    try:
        return str(int(float(val)))
    except (ValueError, TypeError):
        return str(val).strip()


def process_row(page, row: dict, attempt: int = 1):
    """Processes a single listing row.
    
    Returns:
        (success: bool, status: str)
        
    Raises:
        SiteError: If site becomes unavailable mid-listing. This is NOT caught
                   here — it propagates to the main loop for site-level recovery.
    """
    row_no = normalize_no(row["No"])
    game = str(row["Game"])
    server = str(row["Server"])
    harga = str(row["Harga"])
    spesifikasi = str(row["Spesifikasi"])
    gender = str(row.get("gender", ""))
    
    print("\n" + "="*50)
    print(f"LISTING {row_no}")
    print(f"Game:\n{game}")
    print(f"Server:\n{server}")
    print(f"Gender:\n{gender}")
    print(f"Price:\n{harga}")
    print(f"Title:\n{spesifikasi}")
    
    try:
        image_paths = resolve_images(row_no)
        print("Images:")
        print(f"{len(image_paths)} found")
        for i, img in enumerate(image_paths):
            print(f"Image {i+1}: {os.path.basename(img)}")
        
        prepare_next_listing(page)
        
        select_category(page)
        print("[OK] Category")
        
        select_game(page, game)
        print("[OK] Game")
        
        select_server(page, server)
        print("[OK] Server")
        
        select_optional_dropdown(page, "Player Gender", gender)
        if gender and gender.lower() != "none":
            print(f"[OK] Player Gender ({gender})")
        
        fill_title(page, spesifikasi)
        print("[OK] Title")
        
        fill_price(page, harga)
        print("[OK] Price")
        
        ensure_multiple_quantity_disabled(page)
        select_delivery(page)
        print("[OK] Delivery")
        
        fill_description(page)
        
        upload_images(page, image_paths)
        print("[OK] All images uploaded")
        
        ensure_terms_checked(page)
        print("[OK] Terms")
        
        verify_form_state(page, row)
        print("[OK] Validation")
        
        print("[SUBMIT]")
        submit_and_verify(page)
        print("[OK] Listing created")
        
        log_result(f"SUCCESS | No {row_no} | {game}")
        print("="*50)
        return True, "SUCCESS"
    
    # --- SITE ERRORS: Propagate immediately to main loop ---
    # Do NOT retry — the site is down, not the form logic.
    except SiteError:
        raise  # Let main() handle site-level recovery
    
    # --- SUBMISSION UNKNOWN: NEVER retry ---
    except SubmissionUnknownError as e:
        err_msg = str(e)
        print(f"\n[!] SUBMISSION_UNKNOWN: {err_msg}")
        _take_error_screenshot(page, row_no, "unknown")
        log_result(f"SUBMISSION_UNKNOWN | No {row_no} | {err_msg}")
        print("="*50)
        return False, "SUBMISSION_UNKNOWN"
    
    # --- AUTOMATION ERRORS: Retry if allowed ---
    except (FormInteractionError, ImageUploadError, VerificationError,
            SubmissionError, ValidationError, CaptchaDetectedError) as e:
        err_msg = str(e)
        print(f"\n[ERROR] {err_msg}")
        _take_error_screenshot(page, row_no, "error")
        
        if attempt < config.MAX_LISTING_RETRIES and is_retryable_for_listing(e):
            print(f"Retrying (Attempt {attempt + 1}/{config.MAX_LISTING_RETRIES})...")
            return process_row(page, row, attempt + 1)
        else:
            log_result(f"FAILED | No {row_no} | {err_msg}")
            print("="*50)
            return False, "FAILED"
            
    except Exception as e:
        err_msg = f"UNKNOWN_ERROR: {str(e)}"
        print(f"\n[FATAL ERROR] {err_msg}")
        _take_error_screenshot(page, row_no, "fatal")
        log_result(f"FAILED | No {row_no} | {err_msg}")
        print("="*50)
        return False, "FAILED"


def _take_error_screenshot(page, row_no: str, suffix: str):
    """Safely takes a screenshot for debugging. Never raises."""
    try:
        screenshot_path = os.path.join(
            config.LOGS_DIR, "errors", f"listing_{row_no}_{suffix}.png"
        )
        page.screenshot(path=screenshot_path)
        print(f"[DEBUG] Screenshot saved to {screenshot_path}")
    except Exception:
        pass


def main():
    setup_directories()
    
    print(f"Starting MacroListing in {config.MODE.upper()} mode...")
    print("Loading data...")
    dataset = read_excel()
    
    if config.MODE.lower() == "test":
        dataset = [r for r in dataset if normalize_no(r.get("No")) == str(config.TEST_ROW_NO)]
        print(f"TEST MODE active. Processing ONLY No {config.TEST_ROW_NO}.")
    
    if not dataset:
        print("No valid data to process.")
        return config.EXIT_SUCCESS
        
    print("\nStarting Pre-flight validation...")
    try:
        validate_dataset(dataset)
    except ValidationError:
        print("\nExiting due to validation failure. Please fix Excel or Images.")
        return config.EXIT_AUTOMATION_FAILURE
    
    # --- Browser connection ---
    bm = BrowserManager()
    try:
        page = bm.start()
    except SiteError as e:
        print(f"[SITE ERROR] Browser/connection failed: {e}")
        bm.stop()
        return config.EXIT_SITE_UNAVAILABLE
    except Exception as e:
        print(f"[FATAL] Browser setup failed: {e}")
        bm.stop()
        return config.EXIT_AUTOMATION_FAILURE
    
    # --- Site health check ---
    try:
        bm.ensure_ready(page)
    except AuthenticationError as e:
        print(f"[AUTH] {e}")
        bm.stop()
        return config.EXIT_AUTH_REQUIRED
    except SiteError as e:
        print(f"[SITE ERROR] {e}")
        bm.stop()
        return config.EXIT_SITE_UNAVAILABLE
    
    # --- State / Resume ---
    completed = state_manager.get_completed_listings()
    unknown = state_manager.get_unknown_listings()
    if completed:
        print(f"[RESUME] Skipping already-completed listings: {completed}")
    if unknown:
        print(f"[RESUME] Skipping submission-unknown listings (will NOT retry): {unknown}")
    
    # Filter out already-processed listings
    skip_nos = set(completed) | set(unknown)
    pending_dataset = [r for r in dataset if normalize_no(r.get("No")) not in skip_nos]
    
    if not pending_dataset:
        print("All listings already processed. Nothing to do.")
        bm.stop()
        return config.EXIT_SUCCESS
    
    # --- Process listings ---
    results = {"success": 0, "failed": 0, "unknown": 0, "failed_nos": []}
    exit_code = config.EXIT_SUCCESS
    
    for row in pending_dataset:
        row_no = normalize_no(row["No"])
        state_manager.mark_listing_started(row_no)
        
        try:
            success, status = process_row(page, row)
        except SiteError as e:
            # Site went down mid-batch. Pause and exit for recovery.
            print(f"\n[SITE ERROR] Site became unavailable during listing {row_no}: {e}")
            state_manager.mark_cycle_paused(str(e))
            log_result(f"SITE_ERROR | No {row_no} | {e}")
            exit_code = config.EXIT_SITE_UNAVAILABLE
            break
        
        if success:
            results["success"] += 1
            state_manager.mark_listing_completed(row_no)
        elif status == "SUBMISSION_UNKNOWN":
            results["unknown"] += 1
            state_manager.mark_listing_unknown(row_no)
            exit_code = config.EXIT_SUBMISSION_UNKNOWN
        else:
            results["failed"] += 1
            results["failed_nos"].append(row_no)
            state_manager.mark_listing_failed(row_no)
            if exit_code == config.EXIT_SUCCESS:
                exit_code = config.EXIT_AUTOMATION_FAILURE

    # Only mark completed if we didn't break out of the loop due to site error
    if exit_code not in (config.EXIT_SITE_UNAVAILABLE,):
        state_manager.mark_cycle_completed()
    
    bm.stop()
    
    print("\n==============================")
    print("AUTOMATION FINISHED")
    print("==============================")
    print(f"Total processed : {results['success'] + results['failed'] + results['unknown']}")
    print(f"Success         : {results['success']}")
    print(f"Failed          : {results['failed']}")
    print(f"Unknown         : {results['unknown']}")
    
    if results["failed_nos"]:
        print(f"Failed Rows: {', '.join(results['failed_nos'])}")
    
    print("\nCheck logs/automation.log for detailed history.")
    return exit_code


if __name__ == "__main__":
    try:
        code = main()
        sys.exit(code if code is not None else 0)
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Automation stopped by user.")
        sys.exit(config.EXIT_INTERRUPTED)
    except Exception as e:
        print(f"\n[FATAL] Unhandled error: {e}")
        sys.exit(config.EXIT_AUTOMATION_FAILURE)
