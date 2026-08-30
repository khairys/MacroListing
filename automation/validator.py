import os
import config
from automation.exceptions import ValidationError

def resolve_image(row_no: str) -> str:
    """Finds image file matching row_no with supported extensions."""
    found_images = []
    for ext in config.IMAGE_EXTENSIONS:
        img_name = f"{row_no}{ext}"
        img_path = os.path.join(config.IMAGES_DIR, img_name)
        if os.path.exists(img_path):
            found_images.append(img_path)
    
    if not found_images:
        raise ValidationError(f"Image not found for row {row_no}")
    if len(found_images) > 1:
        raise ValidationError(f"Multiple images found for row {row_no}: {found_images}")
        
    return found_images[0]

def validate_dataset(dataset: list[dict]):
    """Pre-flight validation for the entire dataset."""
    errors = []
    seen_nos = set()
    
    for idx, row in enumerate(dataset):
        row_idx = idx + 2 # Assuming row 1 is header
        raw_no = row.get("No", "")
        try:
            row_no = str(int(float(raw_no)))
        except:
            row_no = str(raw_no).strip()
        
        if not row_no or row_no == "None":
            errors.append(f"Row {row_idx}: 'No' is empty.")
            continue
            
        if row_no in seen_nos:
            errors.append(f"Row {row_idx}: Duplicate 'No' {row_no}.")
        seen_nos.add(row_no)
        
        game = str(row.get("Game", "")).strip()
        if not game or game == "None":
            errors.append(f"Row {row_idx}: 'Game' is empty.")
            
        harga = str(row.get("Harga", "")).strip()
        try:
            float(harga)
        except ValueError:
            errors.append(f"Row {row_idx}: 'Harga' {harga} is not numeric.")
            
        server = str(row.get("Server", "")).strip()
        if not server or server == "None":
            errors.append(f"Row {row_idx}: 'Server' is empty.")
            
        spesifikasi = str(row.get("Spesifikasi", "")).strip()
        if not spesifikasi or spesifikasi == "None":
            errors.append(f"Row {row_idx}: 'Spesifikasi' is empty.")
            
        # Image check
        try:
            resolve_image(row_no)
        except ValidationError as e:
            errors.append(f"Row {row_idx}: {str(e)}")
            
    if errors:
        print("PRE-FLIGHT FAILED:")
        for err in errors:
            print(f" - {err}")
        raise ValidationError("Dataset validation failed.")
    else:
        print(f"PRE-FLIGHT Validation: PASSED ({len(dataset)} rows)")
