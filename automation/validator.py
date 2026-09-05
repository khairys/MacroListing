import os
import glob
import config
from automation.exceptions import ValidationError


def resolve_images(game_or_no: str, row_no: str = None, image_folder: str = None) -> list[str]:
    """Finds image files matching game and row_no.
    
    Supports:
    1. Multi-image: {NO}-1.ext, {NO}-2.ext ... or {NO}_1.ext, {NO}_2.ext ...
    2. Single-image: {NO}.ext
    
    Args:
        game_or_no: Either game_code (e.g. 'HSR', 'CZN') or row_no if called with 1 arg.
        row_no: Row number string (e.g. '1', '10').
        image_folder: Optional explicit subfolder name (e.g. 'hsr', 'czn', 'wuwa').
    """
    if row_no is None:
        # Legacy single-argument fallback: resolve_images(row_no)
        target_no = str(game_or_no).strip()
        search_dirs = [config.IMAGES_DIR]
        # Also include subdirectories
        if os.path.exists(config.IMAGES_DIR):
            for entry in os.listdir(config.IMAGES_DIR):
                full_p = os.path.join(config.IMAGES_DIR, entry)
                if os.path.isdir(full_p):
                    search_dirs.append(full_p)
        game_code = "UNKNOWN"
    else:
        game_code = str(game_or_no).strip().upper()
        target_no = str(row_no).strip()
        
        # Determine target folder
        folder_name = image_folder
        if not folder_name:
            reg_entry = config.GAME_REGISTRY.get(game_code)
            if reg_entry:
                folder_name = reg_entry.get("image_folder", game_code.lower())
            else:
                folder_name = game_code.lower()
                
        primary_dir = os.path.join(config.IMAGES_DIR, folder_name)
        search_dirs = [primary_dir, config.IMAGES_DIR]

    found_images = []

    for s_dir in search_dirs:
        if not os.path.exists(s_dir):
            continue

        # Priority 1: Multi-image ({no}-1.ext, {no}-2.ext OR {no}_1.ext, {no}_2.ext)
        multi_images = []
        index = 1
        while True:
            found_at_idx = False
            # Check hyphen separator ({no}-{idx}) then underscore ({no}_{idx})
            for sep in ["-", "_"]:
                for ext in config.IMAGE_EXTENSIONS:
                    img_name = f"{target_no}{sep}{index}{ext}"
                    img_path = os.path.join(s_dir, img_name)
                    if os.path.exists(img_path):
                        multi_images.append(img_path)
                        found_at_idx = True
                        break
                if found_at_idx:
                    break

            if not found_at_idx:
                break
            index += 1

        if multi_images:
            found_images = multi_images
            break

        # Priority 2: Single image ({no}.ext)
        single_images = []
        for ext in config.IMAGE_EXTENSIONS:
            img_name = f"{target_no}{ext}"
            img_path = os.path.join(s_dir, img_name)
            if os.path.exists(img_path):
                single_images.append(img_path)
                break

        if single_images:
            found_images = single_images
            break

    if not found_images:
        folder_hint = folder_name if 'folder_name' in locals() else 'images/'
        raise ValidationError(
            f"IMAGE_NOT_FOUND: No images found for {game_code} #{target_no} in images/{folder_hint}/ "
            f"(checked {target_no}-1.[jpg/png/webp] and {target_no}.[jpg/png/webp])"
        )

    return found_images


def validate_dataset(dataset: list[dict]):
    """Pre-flight validation for the normalized dataset."""
    errors = []
    seen_ids = set()

    for idx, row in enumerate(dataset):
        row_id = row.get("id", f"row_{idx+2}")
        row_idx = row.get("row_index", idx + 2)

        # 1. Unique ID check
        if row_id in seen_ids:
            errors.append(f"Row {row_idx}: Duplicate ID '{row_id}'.")
        seen_ids.add(row_id)

        # 2. Game check
        game = str(row.get("game", "")).strip()
        if not game or game.lower() == "none" or game.lower() == "unknown":
            errors.append(f"Row {row_idx} ({row_id}): 'Game' is missing or unknown.")

        # 3. Price check
        harga = str(row.get("harga", "")).strip()
        try:
            val = float(harga)
            if val <= 0:
                errors.append(f"Row {row_idx} ({row_id}): 'Harga' {harga} must be positive.")
        except ValueError:
            errors.append(f"Row {row_idx} ({row_id}): 'Harga' '{harga}' is not a valid number.")

        # 4. Server check
        server = str(row.get("server", "")).strip()
        if not server or server.lower() == "none":
            errors.append(f"Row {row_idx} ({row_id}): 'Server' could not be resolved from Spesifikasi.")

        # 5. Spesifikasi / Title check
        spesifikasi = str(row.get("spesifikasi", "")).strip()
        if not spesifikasi or spesifikasi.lower() == "none":
            errors.append(f"Row {row_idx} ({row_id}): 'Spesifikasi' is empty.")

        # 6. Image check
        game_code = row.get("game_code", "")
        no = row.get("no", "")
        image_folder = row.get("image_folder")
        try:
            images = resolve_images(game_code, no, image_folder)
            row["image_paths"] = images  # Cache resolved images
        except ValidationError as e:
            errors.append(f"Row {row_idx} ({row_id}): {str(e)}")

    if errors:
        print("PRE-FLIGHT FAILED:")
        for err in errors:
            print(f" - {err}")
        raise ValidationError("Dataset validation failed.")
    else:
        print(f"PRE-FLIGHT Validation: PASSED ({len(dataset)} listings verified)")
