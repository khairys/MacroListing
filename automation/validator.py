import os
import config

def validate_row_data(row: dict) -> tuple[bool, str]:
    """
    Validates a single row of data from Excel.
    Returns (is_valid, error_message).
    """
    required_fields = ["No", "Game", "Harga", "Server", "Spesifikasi"]
    
    for field in required_fields:
        if field not in row or row[field] is None or str(row[field]).strip() == "":
            return False, f"Missing or empty field: {field}"
            
    # Validate Image
    row_no = str(row["No"]).strip()
    image_name = f"{row_no}{config.IMAGE_EXTENSION}"
    image_path = os.path.join(config.IMAGES_DIR, image_name)
    
    if not os.path.exists(image_path):
        return False, f"Image not found: images/{image_name}"
        
    return True, ""
