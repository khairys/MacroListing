import os
import datetime
from openpyxl import load_workbook

import config
from automation.browser import BrowserManager
from automation.validator import validate_row_data
from automation.form import fill_listing_form, submit_form
from automation.uploader import upload_image

def setup_directories():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.IMAGES_DIR, exist_ok=True)
    os.makedirs(config.LOGS_DIR, exist_ok=True)
    os.makedirs(config.SCREENSHOTS_DIR, exist_ok=True)
    os.makedirs(config.BROWSER_PROFILE_PATH, exist_ok=True)

def log_result(message: str):
    """Logs to terminal and file."""
    print(message)
    log_file = os.path.join(config.LOGS_DIR, "automation.log")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")

def read_excel_data() -> list[dict]:
    if not os.path.exists(config.EXCEL_FILE_PATH):
        print(f"Error: Excel file not found at {config.EXCEL_FILE_PATH}")
        return []
        
    wb = load_workbook(config.EXCEL_FILE_PATH, data_only=True)
    sheet = wb.active
    
    headers = [cell.value for cell in sheet[1]]
    
    data = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if all(cell is None for cell in row):
            continue
            
        row_dict = {headers[i]: value for i, value in enumerate(row) if i < len(headers)}
        data.append(row_dict)
        
    return data

def main():
    setup_directories()
    
    print("Reading data from Excel...")
    all_data = read_excel_data()
    
    if not all_data:
        print("No data found or Excel file missing. Exiting.")
        return

    # Filter data if TEST_SINGLE_ROW is True
    if config.TEST_SINGLE_ROW:
        print(f"Development Mode: TEST_SINGLE_ROW is True. Testing No: {config.TEST_ROW_NO}")
        all_data = [row for row in all_data if str(row.get("No")) == str(config.TEST_ROW_NO)]
        if not all_data:
            print(f"Error: Row with No '{config.TEST_ROW_NO}' not found in Excel.")
            return

    total_rows = len(all_data)
    print(f"Found {total_rows} rows to process.")
    
    success_count = 0
    failed_count = 0
    
    browser_manager = BrowserManager()
    page = browser_manager.start()

    try:
        for index, row in enumerate(all_data, start=1):
            row_no = row.get("No", "Unknown")
            game_name = row.get("Game", "Unknown")
            print(f"\nProcessing {index}/{total_rows} - No: {row_no}")
            
            # 1. Validation
            is_valid, error_msg = validate_row_data(row)
            if not is_valid:
                log_result(f"FAILED | No {row_no} | {error_msg}")
                failed_count += 1
                continue
                
            # 2. Process
            try:
                fill_listing_form(page, row)
                upload_image(page, str(row_no))
                submit_form(page)
                
                log_result(f"SUCCESS | No {row_no} | {game_name}")
                success_count += 1
                
                # Logic to reset/prepare for next listing goes here if needed.
                
            except Exception as e:
                screenshot_name = f"error_no_{row_no}.png"
                screenshot_path = os.path.join(config.SCREENSHOTS_DIR, screenshot_name)
                page.screenshot(path=screenshot_path)
                
                log_result(f"FAILED | No {row_no} | Error: {str(e)} | Screenshot: {screenshot_name}")
                failed_count += 1
                
    finally:
        browser_manager.stop()

    print("\n========================")
    print("AUTOMATION FINISHED")
    print(f"Total   : {total_rows}")
    print(f"Success : {success_count}")
    print(f"Failed  : {failed_count}")

if __name__ == "__main__":
    main()
