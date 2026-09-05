"""ZeusX Auto-Orchestrator — Self-Healing Scheduler v2.5.

Lifecycle per cycle:
    1. SITE HEALTH CHECK  (inline, via Playwright)
    2. CLEAR LISTINGS     (subprocess → clear_listings.py)
    3. VERIFY CLEAR       (check exit code)
    4. UPLOAD LISTINGS    (subprocess → main.py)
    5. VERIFY RESULT      (check exit code)
    6. SUMMARY DASHBOARD  (visual metrics card)
    7. COUNTDOWN & HOTKEY (live terminal countdown, console title, [R]/[S]/[Q] keys)

Exit code mapping from child scripts:
    0 = SUCCESS
    1 = AUTOMATION_FAILURE
    2 = SITE_UNAVAILABLE
    3 = AUTH_REQUIRED
    4 = SUBMISSION_UNKNOWN
    5 = INTERRUPTED
"""

import os
import sys
import time
import re
import subprocess
from datetime import datetime, timedelta

# Enable ANSI escape sequence processing and UTF-8 output on Windows CMD
if sys.platform == "win32":
    os.system('')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from automation import state_manager

# --- Schedule configuration (Base 2 Hours ± 10 Minutes Jitter: 1h 50m to 2h 10m) ---
BASE_INTERVAL_HOURS = 2
JITTER_MINUTES = 10

MIN_INTERVAL_MINUTES = (BASE_INTERVAL_HOURS * 60) - JITTER_MINUTES  # 110 minutes (1h 50m)
MAX_INTERVAL_MINUTES = (BASE_INTERVAL_HOURS * 60) + JITTER_MINUTES  # 130 minutes (2h 10m)
MIN_INTERVAL_SECONDS = MIN_INTERVAL_MINUTES * 60
MAX_INTERVAL_SECONDS = MAX_INTERVAL_MINUTES * 60

# Retry policy (progressive backoff in seconds)
_BACKOFF_SCHEDULE = [60, 120, 300, 600, 900]

# Log file path
SCHEDULER_LOG_FILE = os.path.join(config.LOGS_DIR, "scheduler.log")


# --- ANSI Color Palette ---
class C:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


_ANSI_REGEX = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def strip_ansi(text: str) -> str:
    """Removes ANSI color escape codes for clean file writing."""
    return _ANSI_REGEX.sub('', text)


def set_console_title(title: str):
    """Updates the Windows CMD title bar dynamically."""
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW(title)
    except Exception:
        pass


def play_alert_beep():
    """Plays an audible alert if available."""
    try:
        import winsound
        winsound.Beep(1200, 250)
    except Exception:
        sys.stdout.write('\a')
        sys.stdout.flush()


def log(message: str, color: str = ""):
    """Prints a formatted timestamped message to terminal and writes to scheduler.log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"{color}[{timestamp}] [SCHEDULER] {message}{C.RESET if color else ''}"
    
    # Print to console (clear carriage return if needed)
    sys.stdout.write(f"\r{formatted_msg}\n")
    sys.stdout.flush()
    
    # Write plain text to scheduler.log
    try:
        os.makedirs(config.LOGS_DIR, exist_ok=True)
        with open(SCHEDULER_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [SCHEDULER] {strip_ansi(message)}\n")
    except Exception:
        pass


# --- Metrics & State Tracking ---
class SchedulerMetrics:
    cycle_count = 0
    daily_uploaded = 0
    last_cycle_status = "READY"
    last_cycle_duration = "0s"
    last_cycle_counts = {"success": 0, "failed": 0, "unknown": 0}
    next_run_dt = None


def print_cycle_summary_card(start_dt: datetime, end_dt: datetime, clear_status: str, upload_code: int, state_data: dict):
    """Prints a beautiful formatted dashboard card summarizing the completed cycle."""
    SchedulerMetrics.cycle_count += 1
    duration_sec = max(1, int((end_dt - start_dt).total_seconds()))
    m, s = divmod(duration_sec, 60)
    duration_str = f"{m}m {s:02d}s" if m > 0 else f"{s}s"
    SchedulerMetrics.last_cycle_duration = duration_str

    completed = len(state_data.get("completed_listings", [])) if state_data else 0
    failed = len(state_data.get("failed_listings", [])) if state_data else 0
    unknown = len(state_data.get("unknown_listings", [])) if state_data else 0
    SchedulerMetrics.daily_uploaded += completed
    SchedulerMetrics.last_cycle_counts = {"success": completed, "failed": failed, "unknown": unknown}

    if upload_code == config.EXIT_SUCCESS:
        up_text = f"{C.GREEN}SUKSES ({completed} listing diupload){C.RESET}"
        SchedulerMetrics.last_cycle_status = "SUCCESS"
    elif upload_code == config.EXIT_SUBMISSION_UNKNOWN:
        up_text = f"{C.YELLOW}UNKNOWN DETECTED ({unknown} status abu-abu){C.RESET}"
        SchedulerMetrics.last_cycle_status = "UNKNOWN"
    elif upload_code == config.EXIT_AUTH_REQUIRED:
        up_text = f"{C.RED}AUTH REQUIRED (Login Expired){C.RESET}"
        SchedulerMetrics.last_cycle_status = "AUTH_EXPIRED"
    elif upload_code == config.EXIT_SITE_UNAVAILABLE:
        up_text = f"{C.RED}SITE DOWN / UNREACHABLE{C.RESET}"
        SchedulerMetrics.last_cycle_status = "SITE_DOWN"
    else:
        up_text = f"{C.RED}GAGAL (Exit code: {upload_code}){C.RESET}"
        SchedulerMetrics.last_cycle_status = "FAILED"

    card = f"""
{C.CYAN}{C.BOLD}┌────────────────────────────────────────────────────────────────────────┐
│                        📊 SIKLUS #{SchedulerMetrics.cycle_count:02d} SUMMARY                        │
├────────────────────────────────────────────────────────────────────────┤{C.RESET}
  {C.BOLD}Waktu Mulai{C.RESET}     : {start_dt.strftime('%Y-%m-%d %H:%M:%S')}
  {C.BOLD}Waktu Selesai{C.RESET}   : {end_dt.strftime('%Y-%m-%d %H:%M:%S')} ({C.CYAN}Durasi: {duration_str}{C.RESET})
  {C.BOLD}Status Cleanup{C.RESET}  : {C.GREEN if 'SUKSES' in clear_status else C.YELLOW}{clear_status}{C.RESET}
  {C.BOLD}Status Upload{C.RESET}   : {up_text}
  {C.BOLD}Detail Listing{C.RESET}  : {C.GREEN}{completed} Sukses{C.RESET} | {C.RED}{failed} Gagal{C.RESET} | {C.YELLOW}{unknown} Unknown{C.RESET}
  {C.BOLD}Total Terupload{C.RESET} : {C.GREEN}{C.BOLD}{SchedulerMetrics.daily_uploaded} Listing{C.RESET} (Kumulatif Sesi Ini)
{C.CYAN}{C.BOLD}└────────────────────────────────────────────────────────────────────────┘{C.RESET}
"""
    print(card)
    try:
        with open(SCHEDULER_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(strip_ansi(card) + "\n")
    except Exception:
        pass


def check_cdp_heartbeat() -> bool:
    """Quick non-invasive check to verify Chrome remote debugging port is alive."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"{config.CDP_URL}/json/version", timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def check_keyboard_hotkey() -> str | None:
    """Non-blocking keyboard polling for Windows CMD."""
    try:
        import msvcrt
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            # Handle Windows special multi-byte keys (e.g. arrow keys)
            if ch in (b'\x00', b'\xe0'):
                msvcrt.getch()
                return None
            return ch.decode('utf-8', errors='ignore').lower()
    except Exception:
        pass
    return None


def get_backoff_delay(attempt: int) -> int:
    """Returns delay in seconds for a given retry attempt (1-indexed)."""
    idx = min(attempt - 1, len(_BACKOFF_SCHEDULE) - 1)
    return min(_BACKOFF_SCHEDULE[idx], config.RETRY_MAX_DELAY)


def run_script(script_name: str) -> int:
    """Runs a Python script as subprocess and returns its exit code."""
    log(f"Menjalankan sub-skrip {C.BOLD}{script_name}{C.RESET}...", C.CYAN)
    try:
        result = subprocess.run(
            [sys.executable, script_name],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=False
        )
        exit_code = result.returncode
        log(f"Sub-skrip {script_name} selesai (Exit code: {exit_code}).", C.GREEN if exit_code == 0 else C.YELLOW)
        return exit_code
    except Exception as e:
        log(f"FATAL: Gagal menjalankan {script_name}: {e}", C.RED)
        return 1


def perform_site_health_check() -> int:
    """Performs a quick site health check using Playwright directly."""
    log("[HEALTH] Memeriksa status kesehatan ZeusX...", C.CYAN)
    try:
        from playwright.sync_api import sync_playwright
        from automation.site_health import check_site_health, SiteStatus
        
        pw = sync_playwright().start()
        try:
            browser = pw.chromium.connect_over_cdp(config.CDP_URL)
        except Exception as e:
            log(f"[HEALTH] Tidak dapat terhubung ke Chrome CDP ({config.CDP_URL}): {e}", C.RED)
            pw.stop()
            return config.EXIT_SITE_UNAVAILABLE
        
        context = browser.contexts[0] if browser.contexts else None
        if not context:
            log("[HEALTH] Tidak ada browser context yang ditemukan.", C.RED)
            browser.close()
            pw.stop()
            return config.EXIT_SITE_UNAVAILABLE
        
        page = None
        for p in context.pages:
            if "zeusx.com" in p.url:
                page = p
                break
        if not page:
            page = context.new_page()
        
        status = check_site_health(page, config.TARGET_URL)
        
        browser.close()
        pw.stop()
        
        if status == SiteStatus.SITE_READY:
            log("[HEALTH] ZeusX SIAP (Online & Terverifikasi).", C.GREEN)
            return config.EXIT_SUCCESS
        elif status == SiteStatus.AUTH_REQUIRED:
            log("[HEALTH] LOGIN DIPERLUKAN! Sesi ZeusX Anda telah habis.", C.RED)
            return config.EXIT_AUTH_REQUIRED
        else:
            log(f"[HEALTH] ZeusX tidak dapat diakses (Status: {status.value}).", C.YELLOW)
            return config.EXIT_SITE_UNAVAILABLE
            
    except Exception as e:
        log(f"[HEALTH] Pengecekan kesehatan gagal: {e}", C.RED)
        return config.EXIT_SITE_UNAVAILABLE


def wait_for_site_recovery() -> bool:
    """Waits for ZeusX to become available again using progressive backoff."""
    for attempt in range(1, config.MAX_SITE_RETRIES + 1):
        delay = get_backoff_delay(attempt)
        log(f"[RECOVERY] Percobaan {attempt}/{config.MAX_SITE_RETRIES}: "
            f"Menunggu {delay}s sebelum mencoba kembali...", C.YELLOW)
        time.sleep(delay)
        
        health_code = perform_site_health_check()
        
        if health_code == config.EXIT_SUCCESS:
            log("[RECOVERY] ZeusX kembali online!", C.GREEN)
            return True
        elif health_code == config.EXIT_AUTH_REQUIRED:
            log("[RECOVERY] Auth required — harap login manual di jendela Chrome.", C.RED)
            play_alert_beep()
            return False
        else:
            log(f"[RECOVERY] ZeusX masih belum dapat diakses (code {health_code}).", C.YELLOW)
    
    log(f"[RECOVERY] Batas maksimal percobaan ({config.MAX_SITE_RETRIES}) habis. Melewati siklus ini.", C.RED)
    return False


def job():
    """Executes one full automation cycle: health → clear → upload."""
    cycle_start = datetime.now()
    log("=" * 66, C.CYAN)
    log(f"MEMULAI SIKLUS OTOMASI (Basis: {BASE_INTERVAL_HOURS} Jam ± {JITTER_MINUTES} Menit)", C.BOLD + C.CYAN)
    log("=" * 66, C.CYAN)
    set_console_title(f"MacroListing - SIKLUS #{SchedulerMetrics.cycle_count + 1} SEDANG BERJALAN...")

    # === PHASE 1: SITE HEALTH CHECK ===
    health_code = perform_site_health_check()
    
    if health_code == config.EXIT_AUTH_REQUIRED:
        log("[AUTH] Login ZeusX diperlukan. Melewati siklus ini.", C.RED)
        log("Harap login secara manual di jendela Chrome yang aktif.", C.YELLOW)
        play_alert_beep()
        SchedulerMetrics.last_cycle_status = "AUTH_EXPIRED"
        set_console_title("MacroListing [PERINGATAN] - Login ZeusX Diperlukan!")
        return
    
    if health_code != config.EXIT_SUCCESS:
        log("[SITE DOWN] ZeusX tidak dapat diakses. Memulai loop pemulihan...", C.YELLOW)
        recovered = wait_for_site_recovery()
        if not recovered:
            log("Tidak dapat menjangkau ZeusX. Melewati seluruh siklus ini.", C.RED)
            SchedulerMetrics.last_cycle_status = "SITE_DOWN"
            return
    
    # === PHASE 2: CLEAR LISTINGS ===
    log("[CYCLE] Tahap 1: Membersihkan listing lama di ZeusX...", C.CYAN)
    clear_code = run_script("clear_listings.py")
    clear_status_str = "SUKSES"
    
    if clear_code == config.EXIT_SITE_UNAVAILABLE:
        log("[SITE DOWN] Situs tidak dapat diakses selama pembersihan.", C.YELLOW)
        recovered = wait_for_site_recovery()
        if not recovered:
            log("Tidak dapat melanjutkan. Melewati siklus ini.", C.RED)
            return
        log("[RETRY] Mengulang pembersihan setelah pemulihan...", C.CYAN)
        clear_code = run_script("clear_listings.py")
    
    if clear_code == config.EXIT_AUTH_REQUIRED:
        log("[AUTH] Sesi login habis saat pembersihan. Siklus dihentikan.", C.RED)
        play_alert_beep()
        return
    
    if clear_code != config.EXIT_SUCCESS:
        clear_status_str = f"GAGAL (Code: {clear_code})"
        log(f"[CLEANUP FAILED] Exit code {clear_code}. Membatalkan upload untuk mencegah duplikasi listing.", C.RED)
        return
    
    log("[CLEANUP] Berhasil. Halaman listing bersih dan terverifikasi.", C.GREEN)
    
    # === PHASE 3: RESET STATE & PREPARE UPLOAD ===
    state_manager.clear_state()
    log("Menunggu 5 detik agar state server ZeusX stabil...", C.DIM)
    time.sleep(5)
    
    # === PHASE 4: UPLOAD LISTINGS ===
    log("[CYCLE] Tahap 2: Memulai upload listing baru dari Excel...", C.CYAN)
    upload_code = run_script("main.py")
    
    # Muat data state terbaru untuk ringkasan
    final_state = state_manager.load_state() or {}
    cycle_end = datetime.now()
    
    # Tampilkan dashboard summary card
    print_cycle_summary_card(
        start_dt=cycle_start,
        end_dt=cycle_end,
        clear_status=clear_status_str,
        upload_code=upload_code,
        state_data=final_state
    )


def print_status_peek():
    """Prints a quick status overview when [S] is pressed."""
    st = state_manager.load_state() or {}
    completed = st.get("completed_listings", [])
    failed = st.get("failed_listings", [])
    unknown = st.get("unknown_listings", [])
    
    msg = f"""
{C.CYAN}--- STATUS AUDIT CEPAT ---
Total Siklus Selesai: {SchedulerMetrics.cycle_count}
Total Listing Sukses Hari Ini: {SchedulerMetrics.daily_uploaded}
Siklus Terakhir: {SchedulerMetrics.last_cycle_status} (Durasi: {SchedulerMetrics.last_cycle_duration})
Listing Terproses di State Terakhir:
  • Sukses  ({len(completed)}): {', '.join(completed[:10])}{' ...' if len(completed) > 10 else ''}
  • Gagal   ({len(failed)}): {', '.join(failed) if failed else 'None'}
  • Unknown ({len(unknown)}): {', '.join(unknown) if unknown else 'None'}
---------------------------{C.RESET}"""
    print(msg)


if __name__ == "__main__":
    print(rf"""{C.CYAN}{C.BOLD}
============================================================
  ZEUSX AUTO-ORCHESTRATOR v2.5
  Self-Healing & Live-Monitored Scheduler
============================================================{C.RESET}
  {C.DIM}Fitur Tombol Hotkey Aktif:{C.RESET}
  • Tekan {C.BOLD}[R]{C.RESET} : {C.GREEN}Run Now{C.RESET} (Jalankan siklus sekarang juga)
  • Tekan {C.BOLD}[S]{C.RESET} : {C.CYAN}Status{C.RESET} (Lihat audit listing dan akun terakhir)
  • Tekan {C.BOLD}[Q]{C.RESET} : {C.RED}Quit{C.RESET} (Keluar secara aman)
""")

    # Run once immediately upon starting
    log("Memulai siklus pertama secara langsung...", C.GREEN)
    job()
    
    # Schedule recurring runs with randomized jitter (1h 50m to 2h 10m)
    import schedule
    scheduled_job = schedule.every(MIN_INTERVAL_SECONDS).to(MAX_INTERVAL_SECONDS).seconds.do(job)
    
    SchedulerMetrics.next_run_dt = scheduled_job.next_run
    next_time_str = scheduled_job.next_run.strftime('%Y-%m-%d %H:%M:%S') if scheduled_job.next_run else "Segera"
    
    log("Scheduler otomatis telah AKTIF.", C.GREEN)
    log(f"Jeda acak antar siklus: {MIN_INTERVAL_MINUTES} - {MAX_INTERVAL_MINUTES} menit (1h 50m s.d. 2h 10m).", C.CYAN)
    log(f"Siklus berikutnya dijadwalkan pada: {C.BOLD}{next_time_str}{C.RESET}", C.YELLOW)

    last_heartbeat_time = time.time()
    last_known_next_run = scheduled_job.next_run

    # Infinite loop with live 1-second countdown & non-blocking hotkey listener
    while True:
        try:
            # 1. Jalankan job jika timer sudah tercapai
            schedule.run_pending()

            # 2. Update waktu target jika schedule mereschedule interval baru
            if scheduled_job.next_run != last_known_next_run:
                last_known_next_run = scheduled_job.next_run
                SchedulerMetrics.next_run_dt = scheduled_job.next_run
                if scheduled_job.next_run:
                    log(f"Siklus berikutnya diperbarui ke: {C.BOLD}{scheduled_job.next_run.strftime('%Y-%m-%d %H:%M:%S')}{C.RESET}", C.YELLOW)

            # 3. Hitung sisa waktu
            now = datetime.now()
            target = scheduled_job.next_run or (now + timedelta(seconds=60))
            remaining_seconds = max(0, int((target - now).total_seconds()))
            
            rem_h = remaining_seconds // 3600
            rem_m = (remaining_seconds % 3600) // 60
            rem_s = remaining_seconds % 60
            countdown_str = f"{rem_h:02d}:{rem_m:02d}:{rem_s:02d}"

            # 4. Update Windows Console Title
            target_clock = target.strftime('%H:%M:%S')
            set_console_title(
                f"MacroListing [Siklus #{SchedulerMetrics.cycle_count}] - Next in {countdown_str} ({target_clock}) | Status: {SchedulerMetrics.last_cycle_status}"
            )

            # 5. Render live in-place countdown line di CMD
            sys.stdout.write(
                f"\r  {C.YELLOW}⏳ [MENUNGGU]{C.RESET} Sisa: {C.BOLD}{countdown_str}{C.RESET} | "
                f"Target: {C.CYAN}{target_clock}{C.RESET} | "
                f"Siklus: #{SchedulerMetrics.cycle_count + 1} | "
                f"{C.DIM}[R]un Now  [S]tatus  [Q]uit{C.RESET}   "
            )
            sys.stdout.flush()

            # 6. Idle Heartbeat (cek port Chrome CDP setiap 15 menit)
            if time.time() - last_heartbeat_time >= 900:  # 15 minutes
                last_heartbeat_time = time.time()
                if not check_cdp_heartbeat():
                    sys.stdout.write("\n")
                    log("[HEARTBEAT PERINGATAN] Port CDP Chrome (9222) tidak merespons! Pastikan chrome_launcher.py tetap berjalan.", C.RED)
                    play_alert_beep()

            # 7. Tangkap Hotkey Keyboard (Non-blocking)
            key = check_keyboard_hotkey()
            if key == 'r':
                sys.stdout.write("\n")
                log("[HOTKEY R] Memaksa eksekusi siklus sekarang juga...", C.GREEN)
                job()
                # Reschedule interval berikutnya
                schedule.clear()
                scheduled_job = schedule.every(MIN_INTERVAL_SECONDS).to(MAX_INTERVAL_SECONDS).seconds.do(job)
                last_known_next_run = scheduled_job.next_run
            elif key == 's':
                sys.stdout.write("\n")
                print_status_peek()
            elif key == 'q':
                sys.stdout.write("\n")
                log("[HOTKEY Q] Perintah keluar diterima. Menghentikan scheduler...", C.YELLOW)
                set_console_title("MacroListing - Dihentikan")
                break

            time.sleep(1)

        except KeyboardInterrupt:
            sys.stdout.write("\n")
            log("Scheduler dihentikan oleh pengguna (Ctrl+C).", C.YELLOW)
            set_console_title("MacroListing - Dihentikan")
            break
