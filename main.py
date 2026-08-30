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

def log_result(message: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] {message}"
    print(formatted_msg)
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
    
    print(f"\nProcessing No {row_no} (Attempt {attempt}/{config.MAX_RETRIES})")
    
    try:
        image_path = resolve_image(row_no)
        prepare_next_listing(page)
        
        select_category(page)
        select_game(page, game)
        select_server(page, server)
        fill_title(page, spesifikasi)
        fill_price(page, harga)
        select_quantity(page)
        select_delivery(page)
        fill_description(page)
        
        upload_image_file(page, image_path)
        check_terms(page)
        verify_form_state(page, row)
        
        if config.DRY_RUN:
            print("    DRY RUN - SUBMIT SKIPPED")
            screenshot_path = os.path.join(config.SCREENSHOTS_DIR, f"dryrun_no_{row_no}.png")
            page.screenshot(path=screenshot_path)
            log_result(f"DRY_RUN_COMPLETE | No {row_no} | Form verified")
            return True, "DRY_RUN_COMPLETE"
        else:
            submit_and_verify(page)
            log_result(f"SUCCESS | No {row_no} | {game}")
            return True, "SUCCESS"
            
    except CaptchaDetectedError as e:
        print(str(e))
        print("Waiting for captcha resolution... (Press Enter in console when done)")
        input() 
        print("    Retrying after CAPTCHA...")
        return process_row(page, row, attempt)
        
    except (FormInteractionError, ImageUploadError, VerificationError, SubmissionError) as e:
        screenshot_path = os.path.join(config.SCREENSHOTS_DIR, f"error_no_{row_no}.png")
        page.screenshot(path=screenshot_path)
        err_msg = f"Error: {type(e).__name__} - {str(e)}"
        print(f"    {err_msg}")
        
        if attempt < config.MAX_RETRIES:
            print(f"    Retrying...")
            return process_row(page, row, attempt + 1)
        else:
            log_result(f"FAILED | No {row_no} | {err_msg}")
            return False, "FAILED"
            
    except Exception as e:
        screenshot_path = os.path.join(config.SCREENSHOTS_DIR, f"fatal_no_{row_no}.png")
        try:
            page.screenshot(path=screenshot_path)
        except:
            pass
        err_msg = f"Unexpected Error: {str(e)}"
        print(f"    {err_msg}")
        log_result(f"FAILED | No {row_no} | {err_msg}")
        return False, "FAILED"

def normalize_no(val):
    try:
        return str(int(float(val)))
    except:
        return str(val).strip()

def main():
    setup_directories()
    
    print("Loading data...")
    dataset = read_excel()
    
    if config.TEST_SINGLE_ROW:
        dataset = [r for r in dataset if normalize_no(r.get("No")) == str(config.TEST_ROW_NO)]
        print(f"TEST_SINGLE_ROW active. Filtering to No {config.TEST_ROW_NO}.")
    
    if not dataset:
        print("No valid data to process.")
        return
        
    print("\nStarting Pre-flight validation...")
    try:
        validate_dataset(dataset)
    except ValidationError:
        print("\nExiting due to validation failure.")
        return
        
    bm = BrowserManager()
    page = bm.start()
    
    try:
        bm.ensure_login(page)
    except Exception as e:
        print(f"Login setup failed: {e}")
        bm.stop()
        return

    results = {"success": 0, "failed": 0, "dry_run": 0, "failed_nos": []}
    
    for row in dataset:
        success, status = process_row(page, row)
        if status == "SUCCESS":
            results["success"] += 1
        elif status == "DRY_RUN_COMPLETE":
            results["dry_run"] += 1
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
    print(f"Dry Run         : {results['dry_run']}")
    
    if results["failed_nos"]:
        print(f"Failed Rows: {', '.join(results['failed_nos'])}")

if __name__ == "__main__":
    main()
