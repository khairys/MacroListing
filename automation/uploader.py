from playwright.sync_api import Page, expect
from automation.exceptions import ImageUploadError

def upload_images(page: Page, image_paths: list[str]):
    for i, image_path in enumerate(image_paths):
        print(f"    Image {i+1}: Uploading {image_path}...")
        try:
            # ZeusX uses multiple input[type='file']. When one is used, a new one is often created or activated.
            # We want to find the first file input that does NOT have an adjacent image preview (meaning it's empty)
            # or the parent container doesn't have a preview.
            # Since the DOM has a specific structure: .image-upload_image-upload-box__Iv_LD > input[type='file']
            # We can find all file inputs and pick the first one that is visible and attached to an empty upload box.
            
            # Cari ulang input file yang ada
            file_inputs = page.locator("input[type='file']").all()
            if not file_inputs:
                raise ImageUploadError("IMAGE_UPLOADER_NOT_AVAILABLE: No file input element found in DOM.")
                
            active_input = None
            for fi in file_inputs:
                # Cek apakah input tersebut ada di dalam box upload yang masih kosong
                # Box yang sudah ada gambar biasanya memiliki <img> di dalamnya.
                # Box yang belum ada gambar biasanya memiliki svg icon (plus icon) dan tidak ada img
                parent_box = fi.locator("xpath=..")
                has_img = parent_box.locator("img").count() > 0
                if not has_img:
                    active_input = fi
                    break
                    
            if not active_input:
                raise ImageUploadError(f"IMAGE_UPLOADER_NOT_AVAILABLE: No active (empty) uploader slot found for image {i+1}.")
                
            # Hitung preview sebelum upload
            old_preview_count = page.locator("img[src*='blob:'], img[src*='base64'], .image-preview, .upload-preview img, img.preview").count()
            
            # Upload
            active_input.set_input_files(image_path)
            
            # Tunggu preview bertambah
            try:
                # Wait for the count to increase by 1
                page.wait_for_function(
                    f"document.querySelectorAll('img[src*=\"blob:\"]').length > {old_preview_count} || document.querySelectorAll('img[src*=\"base64\"]').length > {old_preview_count} || document.querySelectorAll('.image-preview').length > {old_preview_count}",
                    timeout=15000
                )
                print(f"    [OK] Image {i+1} uploaded (preview detected).")
            except Exception:
                print(f"    Image Warning: Preview thumbnail not detected for image {i+1}. Assuming upload triggered.")
                page.wait_for_timeout(2000) # Safe fallback delay if preview check fails
                
        except Exception as e:
            if isinstance(e, ImageUploadError):
                raise
            raise ImageUploadError(f"IMAGE_UPLOAD_FAILED for image {i+1}: {str(e)}")
