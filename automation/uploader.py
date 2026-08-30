from playwright.sync_api import Page, expect
from automation.exceptions import ImageUploadError

def upload_image_file(page: Page, image_path: str):
    print(f"    Image: Uploading {image_path}...")
    try:
        file_input = page.locator("input[type='file']")
        if file_input.count() == 0:
            raise ImageUploadError("IMAGE_UPLOAD_FAILED: File input element not found in DOM.")
            
        file_input.first.set_input_files(image_path)
        
        # Wait for image preview thumbnail to appear indicating upload success
        preview_img = page.locator("img[src*='blob:'], img[src*='base64'], .image-preview, .upload-preview img, img.preview")
        
        try:
            preview_img.first.wait_for(state="visible", timeout=15000)
            print("    Image: Preview detected, upload successful.")
        except Exception:
            print("    Image Warning: Could not detect preview thumbnail (locator might need adjustment). Assuming upload triggered.")
    except Exception as e:
        raise ImageUploadError(f"IMAGE_UPLOAD_FAILED: Upload interaction failed: {str(e)}")
