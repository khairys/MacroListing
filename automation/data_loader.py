"""Data Loader for MacroListing.

Reads and normalizes account data from Excel (prioritizing data/List Akun.xlsx).
Handles raw human data input:
- Filters rows strictly by presence of 'Spesifikasi'
- Handles forward-fill for 'Game' column when consecutive rows omit it
- Smart parser for 'No' and 'Harga' (handles '1.20', '1200.0', Excel auto-datetime '2026-10-04')
- Extracts 'Server' from 'Spesifikasi' (e.g. 'Asia | ...' -> 'Asia')
- Applies default gender ('Male' for WUWA, None for others)
- Generates unique listing IDs (e.g. 'HSR_1', 'CZN_1', 'WUWA_1')
"""

import os
import re
import datetime
import openpyxl
import config


def parse_no_and_price(no_val, harga_val) -> tuple[str, str]:
    """Extracts (no, price) from raw No and Harga values.
    
    Examples:
        - ('1.0', '1.20') -> ('1', '20')
        - ('1.0', 1200.0) -> ('1', '200')
        - ('4.0', datetime(2026, 10, 4)) -> ('4', '10')  # Excel date conversion
        - (None, 10200.0) -> ('10', '200')
        - (None, '11.80') -> ('11', '80')
    """
    no = None
    harga = None

    # Step 1: Preliminary No from no_val
    if no_val is not None:
        try:
            no = str(int(float(no_val)))
        except (ValueError, TypeError):
            s = str(no_val).strip()
            if s and s.lower() != "none":
                no = s

    # Step 2: Extract from Harga based on type
    if isinstance(harga_val, (datetime.datetime, datetime.date)):
        # Excel auto-converted e.g. 4.10 or 20.10 to a date
        # Day corresponds to No, Month corresponds to Price
        no = str(harga_val.day)
        harga = str(harga_val.month)
    elif isinstance(harga_val, (int, float)):
        val_int = int(harga_val)
        val_str = str(val_int)
        
        # If no is known and val_str starts with it (e.g. no='1' and val_str='1200')
        if no and val_str.startswith(no) and len(val_str) > len(no):
            harga = val_str[len(no):]
        else:
            # If no is not known, or doesn't match prefix, infer from digits
            # Try 2-digit then 1-digit prefix
            inferred = False
            for prefix_len in [2, 1]:
                if len(val_str) > prefix_len:
                    cand_no = val_str[:prefix_len]
                    cand_harga = val_str[prefix_len:]
                    if cand_harga and cand_harga != "0":
                        no = cand_no
                        harga = cand_harga
                        inferred = True
                        break
            if not inferred:
                harga = val_str
    elif isinstance(harga_val, str):
        s = harga_val.strip()
        if "." in s:
            parts = s.split(".")
            cand_no = parts[0].strip()
            cand_harga = parts[1].strip()
            if cand_no:
                no = cand_no
            if cand_harga:
                harga = cand_harga
            else:
                harga = cand_no
        else:
            harga = s
    elif harga_val is not None:
        harga = str(harga_val).strip()

    # Fallback / sanitize price
    if harga:
        # Remove any non-numeric characters except decimal point if any
        clean_harga = re.sub(r"[^\d.]", "", str(harga)).strip()
        try:
            # Normalize to integer string if whole number
            f = float(clean_harga)
            harga = str(int(f)) if f.is_integer() else str(f)
        except ValueError:
            harga = clean_harga

    no = str(no).strip() if no is not None else ""
    harga = str(harga).strip() if harga is not None else ""
    return no, harga


def extract_server(spesifikasi: str) -> str:
    """Extracts the server name from the beginning of 'Spesifikasi'.
    
    Examples:
        - 'Asia | 61 Character...' -> 'Asia'
        - 'Global | 15 SSR...'     -> 'Global'
        - 'SEA | Qingxiao...'      -> 'SEA'
    """
    if not spesifikasi:
        return ""
    
    # Check for pipe separator
    if "|" in spesifikasi:
        candidate = spesifikasi.split("|")[0].strip()
        if candidate:
            return candidate
            
    # Fallback to common regex
    m = re.match(r"^(Asia|Global|SEA|Europe|America|North America|NA)\b", spesifikasi, re.IGNORECASE)
    if m:
        return m.group(1)
        
    return ""


def get_game_info(raw_game: str) -> tuple[str, dict]:
    """Resolves raw game string/code to (game_code, registry_entry)."""
    clean_game = str(raw_game).strip().upper() if raw_game else ""
    
    # Direct match in GAME_REGISTRY
    if clean_game in config.GAME_REGISTRY:
        return clean_game, config.GAME_REGISTRY[clean_game]
        
    # Alias / name matching
    for code, info in config.GAME_REGISTRY.items():
        if clean_game == info["zeus_name"].upper():
            return code, info
        if clean_game == info["image_folder"].upper():
            return code, info
        if code in clean_game:
            return code, info

    # Default fallback
    return clean_game, {
        "zeus_name": raw_game,
        "image_folder": clean_game.lower(),
        "default_gender": None
    }


def load_and_normalize_dataset(file_path: str = None) -> list[dict]:
    """Loads and normalizes account data from Excel.
    
    Only processes rows with a non-empty 'Spesifikasi'.
    Returns a list of standardized listing dictionaries.
    """
    target_path = file_path or config.EXCEL_FILE_PATH
    if not os.path.exists(target_path):
        raise FileNotFoundError(f"Excel file not found at: {target_path}")

    wb = openpyxl.load_workbook(target_path, data_only=True)
    sheet = wb.active
    
    # Map header names to column indexes (0-indexed)
    header_row = [str(cell.value).strip().lower() if cell.value is not None else "" for cell in sheet[1]]
    
    def find_col_idx(*names) -> int:
        for name in names:
            for idx, h in enumerate(header_row):
                if h == name.lower() or name.lower() in h:
                    return idx
        return -1

    idx_no = find_col_idx("no")
    idx_game = find_col_idx("game")
    idx_harga = find_col_idx("harga", "price")
    idx_spec = find_col_idx("spesifikasi", "spec", "specification", "title")
    idx_server = find_col_idx("server")
    idx_gender = find_col_idx("gender")
    idx_email = find_col_idx("email", "email / login", "login")

    dataset = []
    last_game_code = None

    for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
        # 1. Check Spesifikasi: strictly required
        raw_spec = row[idx_spec] if idx_spec != -1 and idx_spec < len(row) else None
        if raw_spec is None or str(raw_spec).strip() == "":
            continue  # Skip rows without specification
            
        spesifikasi = str(raw_spec).strip()

        # 2. Resolve Game with Forward-Fill
        raw_game = row[idx_game] if idx_game != -1 and idx_game < len(row) else None
        if raw_game is not None and str(raw_game).strip() != "":
            game_code, game_info = get_game_info(str(raw_game))
            last_game_code = game_code
        elif last_game_code:
            game_code, game_info = get_game_info(last_game_code)
        else:
            game_code, game_info = "UNKNOWN", {"zeus_name": "Unknown", "image_folder": "unknown", "default_gender": None}

        # 3. Parse No and Harga
        raw_no = row[idx_no] if idx_no != -1 and idx_no < len(row) else None
        raw_harga = row[idx_harga] if idx_harga != -1 and idx_harga < len(row) else None
        no, harga = parse_no_and_price(raw_no, raw_harga)

        # 4. Resolve Server
        server = ""
        if idx_server != -1 and idx_server < len(row) and row[idx_server]:
            server = str(row[idx_server]).strip()
        if not server:
            server = extract_server(spesifikasi)

        # 5. Resolve Gender
        # For WUWA, always default to "Male" as explicitly required
        gender = ""
        if game_info.get("default_gender"):
            gender = game_info["default_gender"]
        elif idx_gender != -1 and idx_gender < len(row) and row[idx_gender]:
            gender = str(row[idx_gender]).strip()

        # 6. Email / Login (metadata)
        email = ""
        if idx_email != -1 and idx_email < len(row) and row[idx_email]:
            email = str(row[idx_email]).strip()

        # Unique ID for tracking (prevents collision between HSR #1, CZN #1, WUWA #1)
        listing_id = f"{game_code}_{no}" if no else f"{game_code}_row{row_idx}"

        dataset.append({
            "id": listing_id,
            "row_index": row_idx,
            "no": no,
            "No": no,
            "game_code": game_code,
            "game": game_info["zeus_name"],
            "Game": game_info["zeus_name"],
            "image_folder": game_info["image_folder"],
            "harga": harga,
            "Harga": harga,
            "server": server,
            "Server": server,
            "spesifikasi": spesifikasi,
            "Spesifikasi": spesifikasi,
            "gender": gender,
            "email": email,
        })

    return dataset
