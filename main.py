import os
import datetime
import openpyxl

import config
from automation.validator import validate_dataset, resolve_images
from automation.browser import BrowserManager
from automation.form import (
    prepare_next_listing, select_category, select_game,
    select_server, select_optional_dropdown, fill_title, fill_price, ensure_multiple_quantity_disabled,
    select_delivery, fill_description, ensure_terms_checked
)
from automation.uploader import upload_images
from automation.verifier import verify_form_state, submit_and_verify
from automation.exceptions import (
    ValidationError, FormInteractionError, ImageUploadError,
    CaptchaDetectedError, VerificationError, SubmissionError,
    SubmissionUnknownError
)

def setup_directories():
    os.makedirs(config.LOGS_DIR, exist_ok=True)
    os.makedirs(config.SCREENSHOTS_DIR, exist_ok=True)
    os.makedirs(os.path.join(config.LOGS_DIR, "errors"), exist_ok=True)

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

def process_row(page, row: dict, attempt: int = 1):
    def normalize_no(val):
        try: return str(int(float(val)))
        except: return str(val).strip()
        
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
            
    except CaptchaDetectedError as e:
        print("\n[!] CAPTCHA DETECTED")
        print("Please solve it manually on the browser.")
        input("Press Enter here when ready to retry...")
        return process_row(page, row, attempt)
        
    except (FormInteractionError, ImageUploadError, VerificationError, SubmissionError, ValidationError, SubmissionUnknownError) as e:
        err_msg = str(e)
        print(f"\n[ERROR] {err_msg}")
        
        if not isinstance(e, ValidationError):
            screenshot_path = os.path.join(config.LOGS_DIR, "errors", f"listing_{row_no}_error.png")
            try:
                page.screenshot(path=screenshot_path)
                print(f"[DEBUG] Screenshot saved to {screenshot_path}")
            except:
                pass
                
        # Do not retry on Validation Errors or if submission state is unknown to prevent duplicates
        prevent_retry = isinstance(e, (ValidationError, SubmissionUnknownError))
        
        if attempt < config.MAX_RETRIES and not prevent_retry:
            print(f"Retrying (Attempt {attempt + 1}/{config.MAX_RETRIES})...")
            return process_row(page, row, attempt + 1)
        else:
            status = "SUBMISSION_UNKNOWN" if isinstance(e, SubmissionUnknownError) else "FAILED"
            log_result(f"{status} | No {row_no} | {err_msg}")
            print("="*50)
            return False, status
            
    except Exception as e:
        err_msg = f"UNKNOWN_ERROR: {str(e)}"
        print(f"\n[FATAL ERROR] {err_msg}")
        screenshot_path = os.path.join(config.LOGS_DIR, "errors", f"listing_{row_no}_fatal.png")
        try:
            page.screenshot(path=screenshot_path)
        except:
            pass
        log_result(f"FAILED | No {row_no} | {err_msg}")
        print("="*50)
        return False, "FAILED"

def normalize_no(val):
    try:
        return str(int(float(val)))
    except:
        return str(val).strip()

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
        return
        
    print("\nStarting Pre-flight validation...")
    try:
        validate_dataset(dataset)
    except ValidationError:
        print("\nExiting due to validation failure. Please fix Excel or Images.")
        return
        
    bm = BrowserManager()
    try:
        page = bm.start()
        bm.ensure_login(page)
    except Exception as e:
        print(f"Browser/Login setup failed: {e}")
        bm.stop()
        return

    results = {"success": 0, "failed": 0, "failed_nos": []}
    
    for row in dataset:
        success, status = process_row(page, row)
        if success:
            results["success"] += 1
        else:
            results["failed"] += 1
            results["failed_nos"].append(str(row["No"]))

    bm.stop()
    
    print("\n==============================")
    print("AUTOMATION FINISHED")
    print("==============================")
    print(f"Total processed : {len(dataset)}")
    print(f"Success         : {results['success']}")
    print(f"Failed          : {results['failed']}")
    
    if results["failed_nos"]:
        print(f"Failed Rows: {', '.join(results['failed_nos'])}")
    
    print("\nCheck logs/automation.log for detailed history.")

if __name__ == "__main__":
    main()
