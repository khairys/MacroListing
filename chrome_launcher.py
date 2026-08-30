from pathlib import Path
import subprocess
import shutil
import sys
import time


# ============================================================
# CONFIGURATION
# ============================================================

DEBUG_PORT = 9222

TARGET_URL = "https://zeusx.com/create-offer"

# Profile Chrome KHUSUS automation.
# JANGAN gunakan profile Chrome utama.
PROFILE_DIR = Path(__file__).resolve().parent / "chrome-debug-profile"


# ============================================================
# FIND CHROME
# ============================================================

def find_chrome():
    """
    Mencari Google Chrome pada lokasi instalasi Windows umum.
    """

    possible_paths = [
        Path(
            r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        ),
        Path(
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
        ),
        Path(
            Path.home()
        ) / r"AppData\Local\Google\Chrome\Application\chrome.exe",
    ]

    # Coba PATH terlebih dahulu.
    chrome_from_path = shutil.which("chrome")

    if chrome_from_path:
        return Path(chrome_from_path)

    for path in possible_paths:
        if path.exists():
            return path

    return None


# ============================================================
# CHECK DEBUG PORT
# ============================================================

def is_debug_port_available():
    """
    Memeriksa apakah Chrome remote debugging endpoint
    sudah tersedia.
    """

    import urllib.request

    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{DEBUG_PORT}/json/version",
            timeout=1
        ) as response:
            return response.status == 200

    except Exception:
        return False


# ============================================================
# LAUNCH CHROME
# ============================================================

def launch_chrome():
    chrome_path = find_chrome()

    if chrome_path is None:
        print()
        print("=" * 70)
        print("ERROR: Google Chrome tidak ditemukan.")
        print("=" * 70)
        print()
        print("Pastikan Google Chrome sudah terinstall.")
        print()
        sys.exit(1)

    PROFILE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    print("=" * 70)
    print("CHROME DEBUG LAUNCHER")
    print("=" * 70)
    print()
    print(f"Chrome : {chrome_path}")
    print(f"Profile: {PROFILE_DIR}")
    print(f"Port   : {DEBUG_PORT}")
    print()
    
    if is_debug_port_available():
        print(
            f"[INFO] Chrome dengan CDP port {DEBUG_PORT} "
            "sudah berjalan."
        )
        print()
        return

    command = [
        str(chrome_path),

        # Remote debugging.
        f"--remote-debugging-port={DEBUG_PORT}",

        # Profile khusus.
        f"--user-data-dir={PROFILE_DIR}",

        # Jangan restore tab lama.
        "--no-first-run",
        "--no-default-browser-check",

        # Buka ZeusX.
        TARGET_URL,
    ]

    print("[INFO] Starting Chrome...")
    print()

    try:
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )

    except Exception as e:
        print()
        print("[ERROR] Gagal menjalankan Chrome.")
        print(e)
        sys.exit(1)

    print("[INFO] Waiting for Chrome CDP endpoint...")

    for _ in range(20):
        if is_debug_port_available():
            print()
            print("[SUCCESS] Chrome CDP sudah aktif.")
            print()
            return

        time.sleep(0.5)

    print()
    print("=" * 70)
    print("ERROR: Chrome CDP tidak dapat diakses.")
    print("=" * 70)
    print()
    print(
        f"Pastikan port {DEBUG_PORT} tidak digunakan "
        "oleh aplikasi lain."
    )

    sys.exit(1)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    launch_chrome()

    print("=" * 70)
    print("CHROME SIAP")
    print("=" * 70)
    print()
    print("Sekarang lakukan secara manual:")
    print()
    print("1. Selesaikan Cloudflare jika muncul.")
    print("2. Login ke ZeusX.")
    print("3. Buka halaman Create Offer.")
    print("4. Pastikan form sudah benar-benar terlihat.")
    print()
    print("JANGAN tutup Chrome.")
    print()
    print("Kemudian jalankan:")
    print()
    print("    python dom_inspector_cdp.py")
    print()