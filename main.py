import os
import datetime
import openpyxl

import config
from automation.validator import validate_dataset, resolve_image
from automation.browser import BrowserManager
from automation.form import (
    prepare_next_listing, select_category, select_game,
    select_server, fill_title, fill_price, select_quantity,
    select_delivery, fill_description, check_terms
)
from automation.uploader import upload_image_file
from automation.verifier import verify_form_state, submit_and_verify
from automation.exceptions import (
    ValidationError, FormInteractionError, ImageUploadError,
    CaptchaDetectedError, VerificationError, SubmissionError
)

def setup_directories():
    os.makedirs(config.LOGS_DIR, exist_ok=True)
    os.makedirs(config.SCREENSHOTS_DIR, exist_ok=True)
    os.makedirs(os.path.join(config.LOGS_DIR, "errors"), exist_ok=True)

def log_result(message: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] {message}"
    with open(os.path.join(config.LOGS_DIR, "automation.log"), "a", encoding="utf-8") as f:
        f.write(formatted_msg + "\n")

def read_excel() -> list[dict]:
    wb = openpyxl.load_workbook(config.EXCEL_FILE_PATH, data_only=True)
    sheet = wb.active
    headers = [str(cell.value) for cell in sheet[1]]
    data = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if all(cell is None for cell in row):
            continue
        row_dict = {headers[i]: value for i, value in enumerate(row) if i < len(headers)}
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
    
    print("\n" + "="*50)
    print(f"LISTING {row_no}")
    print(f"Game:\n{game}")
    print(f"Server:\n{server}")
    print(f"Price:\n{harga}")
    print(f"Title:\n{spesifikasi}")
    
    try:
        image_path = resolve_image(row_no)
        print(f"Image:\n{os.path.basename(image_path)}")
        
        prepare_next_listing(page)
        
        select_category(page)
        print("[OK] Category")
        
        select_game(page, game)
        print("[OK] Game")
        
        select_server(page, server)
        print("[OK] Server")
        
        fill_title(page, spesifikasi)
        print("[OK] Title")
        
        fill_price(page, harga)
        print("[OK] Price")
        
        select_quantity(page)
        select_delivery(page)
        print("[OK] Delivery")
        
        fill_description(page)
        
        upload_image_file(page, image_path)
        print("[OK] Image")
        
        check_terms(page)
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
        
    except (FormInteractionError, ImageUploadError, VerificationError, SubmissionError, ValidationError) as e:
        err_msg = str(e)
        print(f"\n[ERROR] {err_msg}")
        
        if not isinstance(e, ValidationError):
            screenshot_path = os.path.join(config.LOGS_DIR, "errors", f"listing_{row_no}_error.png")
            try:
                page.screenshot(path=screenshot_path)
                print(f"[DEBUG] Screenshot saved to {screenshot_path}")
            except:
                pass
        
        if attempt < config.MAX_RETRIES and not isinstance(e, ValidationError):
            print(f"Retrying (Attempt {attempt + 1}/{config.MAX_RETRIES})...")
            return process_row(page, row, attempt + 1)
        else:
            log_result(f"FAILED | No {row_no} | {err_msg}")
            print("="*50)
            return False, "FAILED"
            
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
