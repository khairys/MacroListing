"""ZeusX Cycle Runner — Bounded Cycle Orchestrator.

Menjalankan sejumlah siklus otomasi tertentu (bukan loop tanpa henti),
kemudian berhenti secara bersih dengan laporan ringkasan akhir.

Alur per siklus:
    1. SITE HEALTH CHECK  (inline, via Playwright)
    2. CLEAR LISTINGS     (subprocess → clear_listings.py)
    3. VERIFY CLEAR       (check exit code)
    4. UPLOAD LISTINGS    (subprocess → main.py)
    5. VERIFY RESULT      (check exit code)
    6. SUMMARY CARD       (ringkasan progres siklus saat ini)
    7. COUNTDOWN & HOTKEY (jeda menuju siklus berikutnya dengan hotkey [R]/[S]/[Q])

Setelah semua siklus selesai, menampilkan GRAND SUMMARY dan keluar.
"""

import os
import sys
import time
import re
import argparse
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

# Log file path
RUNNER_LOG_FILE = os.path.join(config.LOGS_DIR, "cycle_runner.log")

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


def play_alert_beep(repeat: int = 1):
    """Plays audible alert beeps."""
    try:
        import winsound
        for _ in range(repeat):
            winsound.Beep(1200, 250)
            time.sleep(0.1)
    except Exception:
        for _ in range(repeat):
            sys.stdout.write('\a')
            sys.stdout.flush()
            time.sleep(0.1)


def log(message: str, color: str = ""):
    """Prints a formatted timestamped message to terminal and writes to cycle_runner.log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"{color}[{timestamp}] [CYCLE-RUNNER] {message}{C.RESET if color else ''}"
    
    sys.stdout.write(f"\r{formatted_msg}\n")
    sys.stdout.flush()
    
    try:
        os.makedirs(config.LOGS_DIR, exist_ok=True)
        with open(RUNNER_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [CYCLE-RUNNER] {strip_ansi(message)}\n")
    except Exception:
        pass


class RunnerStats:
    """Tracks metrics across all executed cycles."""
    total_target_cycles = 0
    completed_cycles = 0
    total_uploaded = 0
    cycle_history = []  # list of dicts: {cycle_num, duration_str, status, completed_count}
    start_time = None


def check_keyboard_hotkey() -> str | None:
    """Non-blocking keyboard polling for Windows CMD."""
    try:
        import msvcrt
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            if ch in (b'\x00', b'\xe0'):
                msvcrt.getch()
                return None
            return ch.decode('utf-8', errors='ignore').lower()
    except Exception:
        pass
    return None


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
    backoff_schedule = [60, 120, 300, 600]
    for attempt in range(1, config.MAX_SITE_RETRIES + 1):
        delay = backoff_schedule[min(attempt - 1, len(backoff_schedule) - 1)]
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


def parse_cycle_counts_from_log(start_dt: datetime, end_dt: datetime) -> dict:
    """Fallback: counts success/failed/unknown listings from automation.log within a time window."""
    auto_log_path = os.path.join(config.LOGS_DIR, "automation.log")
    counts = {"success": 0, "failed": 0, "unknown": 0}
    if not os.path.exists(auto_log_path):
        return counts
    try:
        pattern = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] (SUCCESS|FAILED|SUBMISSION_UNKNOWN) \| (.+)")
        with open(auto_log_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                m = pattern.match(line.strip())
                if m:
                    log_time = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                    if start_dt <= log_time <= end_dt:
                        status = m.group(2)
                        if status == "SUCCESS":
                            counts["success"] += 1
                        elif status == "FAILED":
                            counts["failed"] += 1
                        elif status == "SUBMISSION_UNKNOWN":
                            counts["unknown"] += 1
    except Exception:
        pass
    return counts


def execute_cycle(cycle_index: int, total_cycles: int, skip_clear: bool = False) -> bool:
    """Menjalankan satu siklus otomasi utuh: Health Check → Clear → Upload.
    
    Returns True jika siklus berhasil diproses, False jika terjadi kegagalan fatal.
    """
    cycle_start = datetime.now()
    log("=" * 66, C.CYAN)
    log(f"MEMULAI SIKLUS #{cycle_index} DARI {total_cycles}", C.BOLD + C.CYAN)
    log("=" * 66, C.CYAN)
    set_console_title(f"MacroListing - SIKLUS {cycle_index}/{total_cycles} SEDANG BERJALAN...")

    # === 1. HEALTH CHECK ===
    health_code = perform_site_health_check()
    if health_code == config.EXIT_AUTH_REQUIRED:
        log("[AUTH] Login ZeusX diperlukan. Siklus dihentikan.", C.RED)
        play_alert_beep(2)
        return False
    
    if health_code != config.EXIT_SUCCESS:
        log("[SITE DOWN] ZeusX tidak dapat diakses. Memulai pemulihan...", C.YELLOW)
        if not wait_for_site_recovery():
            log("Tidak dapat menjangkau ZeusX. Melewati siklus ini.", C.RED)
            return False

    # === 2. CLEAR LISTINGS ===
    clear_status_str = "SUKSES"
    if not skip_clear:
        log("[CYCLE] Tahap 1: Membersihkan listing lama di ZeusX...", C.CYAN)
        clear_code = run_script("clear_listings.py")
        if clear_code == config.EXIT_SITE_UNAVAILABLE:
            log("[SITE DOWN] Situs down saat pembersihan, mencoba pemulihan...", C.YELLOW)
            if wait_for_site_recovery():
                clear_code = run_script("clear_listings.py")
        
        if clear_code == config.EXIT_AUTH_REQUIRED:
            log("[AUTH] Sesi habis saat pembersihan.", C.RED)
            play_alert_beep(2)
            return False
            
        if clear_code != config.EXIT_SUCCESS:
            clear_status_str = f"GAGAL (Code: {clear_code})"
            log(f"[CLEANUP FAILED] Exit code {clear_code}. Upload dibatalkan demi keamanan data.", C.RED)
            return False
        log("[CLEANUP] Berhasil. Halaman listing bersih.", C.GREEN)
    else:
        clear_status_str = "DILEWATI (--no-clear)"
        log("[CYCLE] Tahap 1: Pembersihan dilewati sesuai permintaan.", C.DIM)

    # === 3. RESET STATE ===
    state_manager.clear_state()
    log("Menunggu 5 detik agar state server ZeusX stabil...", C.DIM)
    time.sleep(5)

    # === 4. UPLOAD LISTINGS ===
    log("[CYCLE] Tahap 2: Memulai upload listing baru dari Excel...", C.CYAN)
    upload_code = run_script("main.py")
    
    final_state = state_manager.load_state() or {}
    cycle_end = datetime.now()
    
    duration_sec = max(1, int((cycle_end - cycle_start).total_seconds()))
    m, s = divmod(duration_sec, 60)
    duration_str = f"{m}m {s:02d}s" if m > 0 else f"{s}s"

    completed = len(final_state.get("completed_listings", []))
    failed = len(final_state.get("failed_listings", []))
    unknown = len(final_state.get("unknown_listings", []))

    # Fallback 1: Jika summary dict tersedia di state_data
    if not completed and "summary" in final_state:
        completed = final_state["summary"].get("success", 0)
        failed = final_state["summary"].get("failed", 0)
        unknown = final_state["summary"].get("unknown", 0)

    # Fallback 2: Jika state kosong / 0, parse metrik dari logs/automation.log
    if completed == 0 and failed == 0 and unknown == 0:
        counts = parse_cycle_counts_from_log(cycle_start, cycle_end)
        completed = counts.get("success", 0)
        failed = counts.get("failed", 0)
        unknown = counts.get("unknown", 0)

    RunnerStats.completed_cycles += 1
    RunnerStats.total_uploaded += completed
    
    status_label = "SUKSES" if upload_code == config.EXIT_SUCCESS else f"KODE {upload_code}"
    RunnerStats.cycle_history.append({
        "cycle_num": cycle_index,
        "duration": duration_str,
        "status": status_label,
        "uploaded": completed
    })

    # Summary card per siklus
    up_status_color = C.GREEN if upload_code == config.EXIT_SUCCESS else C.YELLOW
    card = f"""
{C.CYAN}{C.BOLD}┌────────────────────────────────────────────────────────────────────────┐
│                   📊 SIKLUS #{cycle_index:02d} SELESAI ({cycle_index}/{total_cycles})                          │
├────────────────────────────────────────────────────────────────────────┤{C.RESET}
  {C.BOLD}Durasi Siklus{C.RESET}   : {duration_str}
  {C.BOLD}Status Cleanup{C.RESET}  : {C.GREEN if 'SUKSES' in clear_status_str else C.YELLOW}{clear_status_str}{C.RESET}
  {C.BOLD}Status Upload{C.RESET}   : {up_status_color}{status_label}{C.RESET}
  {C.BOLD}Hasil Upload{C.RESET}    : {C.GREEN}{completed} Sukses{C.RESET} | {C.RED}{failed} Gagal{C.RESET} | {C.YELLOW}{unknown} Unknown{C.RESET}
  {C.BOLD}Total Terupload{C.RESET} : {C.GREEN}{C.BOLD}{RunnerStats.total_uploaded} Listing{C.RESET} (Kumulatif keseluruhan siklus)
{C.CYAN}{C.BOLD}└────────────────────────────────────────────────────────────────────────┘{C.RESET}
"""
    print(card)
    try:
        with open(RUNNER_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(strip_ansi(card) + "\n")
    except Exception:
        pass

    return True


def wait_countdown_between_cycles(cycle_index: int, total_cycles: int, interval_seconds: int) -> bool:
    """Menghitung mundur jeda antar siklus dengan dukungan hotkey.
    
    Returns:
        True jika lanjut ke siklus berikutnya.
        False jika pengguna menekan [Q] untuk berhenti.
    """
    if interval_seconds <= 0:
        log("Tidak ada jeda waktu (interval = 0). Langsung lanjut ke siklus berikutnya...", C.DIM)
        return True

    target_time = datetime.now() + timedelta(seconds=interval_seconds)
    target_clock = target_time.strftime('%H:%M:%S')

    log(f"Menunggu jeda waktu {interval_seconds // 60} menit sebelum siklus #{cycle_index + 1}...", C.CYAN)
    log(f"Siklus berikutnya dijadwalkan pukul: {C.BOLD}{target_clock}{C.RESET}", C.YELLOW)

    while True:
        now = datetime.now()
        remaining = max(0, int((target_time - now).total_seconds()))

        if remaining <= 0:
            sys.stdout.write("\n")
            log(f"Jeda waktu selesai. Memulai siklus #{cycle_index + 1}...", C.GREEN)
            return True

        h = remaining // 3600
        m = (remaining % 3600) // 60
        s = remaining % 60
        countdown_str = f"{h:02d}:{m:02d}:{s:02d}"

        set_console_title(f"MacroListing - Sisa Waktu {countdown_str} menuju Siklus #{cycle_index + 1}/{total_cycles}")

        sys.stdout.write(
            f"\r  {C.YELLOW}⏳ [JEDA SIKLUS]{C.RESET} Sisa: {C.BOLD}{countdown_str}{C.RESET} | "
            f"Target: {C.CYAN}{target_clock}{C.RESET} | "
            f"Berikutnya: #{cycle_index + 1}/{total_cycles} | "
            f"{C.DIM}[R]un Now  [S]tatus  [Q]uit{C.RESET}   "
        )
        sys.stdout.flush()

        key = check_keyboard_hotkey()
        if key == 'r':
            sys.stdout.write("\n")
            log("[HOTKEY R] Melewati jeda waktu. Memulai siklus berikutnya sekarang!", C.GREEN)
            return True
        elif key == 's':
            sys.stdout.write("\n")
            print_status_peek()
        elif key == 'q':
            sys.stdout.write("\n")
            log("[HOTKEY Q] Pembatalan diterima. Berhenti pada siklus ini.", C.YELLOW)
            return False

        time.sleep(1)


def print_status_peek():
    """Prints a quick status overview when [S] is pressed."""
    st = state_manager.load_state() or {}
    completed = st.get("completed_listings", [])
    failed = st.get("failed_listings", [])
    unknown = st.get("unknown_listings", [])
    
    msg = f"""
{C.CYAN}--- STATUS AUDIT CEPAT ---
Siklus Selesai: {RunnerStats.completed_cycles} dari {RunnerStats.total_target_cycles}
Total Listing Sukses: {RunnerStats.total_uploaded}
Listing di State Terakhir:
  • Sukses  ({len(completed)}): {', '.join(completed[:10])}{' ...' if len(completed) > 10 else ''}
  • Gagal   ({len(failed)}): {', '.join(failed) if failed else 'None'}
  • Unknown ({len(unknown)}): {', '.join(unknown) if unknown else 'None'}
---------------------------{C.RESET}"""
    print(msg)


def print_grand_summary():
    """Mencetak laporan ringkasan menyeluruh setelah seluruh siklus selesai."""
    now = datetime.now()
    total_sec = max(1, int((now - RunnerStats.start_time).total_seconds())) if RunnerStats.start_time else 0
    th = total_sec // 3600
    tm = (total_sec % 3600) // 60
    ts = total_sec % 60
    total_duration_str = f"{th:02d}j {tm:02d}m {ts:02d}d" if th > 0 else f"{tm}m {ts:02d}d"

    history_lines = ""
    for item in RunnerStats.cycle_history:
        history_lines += f"  • Siklus #{item['cycle_num']:02d}: {item['uploaded']} Upload ({item['status']}) - Durasi: {item['duration']}\n"
    if not history_lines:
        history_lines = "  (Tidak ada siklus yang berhasil diselesaikan)\n"

    grand_banner = f"""
{C.GREEN}{C.BOLD}========================================================================
                      🎉 LAPORAN AKHIR (GRAND SUMMARY)
========================================================================{C.RESET}
  {C.BOLD}Target Siklus Dijalankan{C.RESET} : {RunnerStats.total_target_cycles} Siklus
  {C.BOLD}Siklus Berhasil Selesai{C.RESET}  : {C.GREEN}{C.BOLD}{RunnerStats.completed_cycles}{C.RESET} Siklus
  {C.BOLD}Total Listing Terupload{C.RESET}  : {C.GREEN}{C.BOLD}{RunnerStats.total_uploaded}{C.RESET} Listing
  {C.BOLD}Total Waktu Operasional{C.RESET}  : {C.CYAN}{total_duration_str}{C.RESET}

  {C.BOLD}Rincian Riwayat Siklus:{C.RESET}
{history_lines}
{C.GREEN}{C.BOLD}========================================================================{C.RESET}
"""
    print(grand_banner)
    try:
        with open(RUNNER_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(strip_ansi(grand_banner) + "\n")
    except Exception:
        pass
    
    play_alert_beep(3)


def parse_args():
    parser = argparse.ArgumentParser(
        description="ZeusX Cycle Runner — Menjalankan otomasi untuk N siklus tertentu."
    )
    parser.add_argument(
        "-n", "--cycles",
        type=int,
        default=None,
        help="Jumlah siklus yang ingin dijalankan (contoh: 3)"
    )
    parser.add_argument(
        "-i", "--interval",
        type=float,
        default=None,
        help="Jeda waktu antar siklus dalam satuan menit (contoh: 120 untuk 2 jam, atau 0 untuk tanpa jeda)"
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Lewati tahap penghapusan listing lama (hanya lakukan upload)"
    )
    return parser.parse_args()


def prompt_user_input() -> tuple[int, float]:
    """Menanyakan parameter secara interaktif jika tidak diberikan via argumen CLI."""
    print(f"{C.CYAN}{C.BOLD}")
    print("============================================================")
    print("   ZEUSX CYCLE RUNNER (EKSEKUSI TERBATAS BERHITUNG)        ")
    print("============================================================")
    print(f"{C.RESET}")
    print(f"  {C.DIM}Fitur ini menjalankan siklus sejumlah N kali lalu berhenti secara otomatis.{C.RESET}\n")

    # Prompt Jumlah Siklus
    while True:
        try:
            raw_cycles = input(f"{C.BOLD}Berapa kali siklus ingin dijalankan?{C.RESET} (contoh: 1, 3, 5): ").strip()
            if not raw_cycles:
                print(f"{C.YELLOW}Mohon masukkan angka jumlah siklus.{C.RESET}")
                continue
            cycles = int(raw_cycles)
            if cycles <= 0:
                print(f"{C.RED}Jumlah siklus harus lebih dari 0.{C.RESET}")
                continue
            break
        except ValueError:
            print(f"{C.RED}Input tidak valid. Harap masukkan angka bulat (integer).{C.RESET}")

    # Prompt Interval
    while True:
        try:
            raw_interval = input(
                f"{C.BOLD}Jeda antar siklus dalam menit?{C.RESET} [Tekan Enter untuk default 120 menit, atau ketik 0 untuk langsung]: "
            ).strip()
            if raw_interval == "":
                interval = 120.0
                break
            interval = float(raw_interval)
            if interval < 0:
                print(f"{C.RED}Jeda waktu tidak boleh bernilai negatif.{C.RESET}")
                continue
            break
        except ValueError:
            print(f"{C.RED}Input tidak valid. Harap masukkan angka.{C.RESET}")

    return cycles, interval


def main():
    args = parse_args()
    
    cycles = args.cycles
    interval_min = args.interval
    skip_clear = args.no_clear

    # Jika argumen tidak diisi via CLI, minta input dari pengguna
    if cycles is None or interval_min is None:
        p_cycles, p_interval = prompt_user_input()
        if cycles is None:
            cycles = p_cycles
        if interval_min is None:
            interval_min = p_interval

    interval_seconds = int(interval_min * 60)
    RunnerStats.total_target_cycles = cycles
    RunnerStats.start_time = datetime.now()

    print(rf"""{C.CYAN}{C.BOLD}
============================================================
  KONFIGURASI RUNNER
============================================================{C.RESET}
  • Target Siklus   : {C.GREEN}{C.BOLD}{cycles} Kali Putaran{C.RESET}
  • Jeda Antar Run  : {C.YELLOW}{interval_min} Menit ({interval_seconds} Detik){C.RESET}
  • Bersihkan Lama  : {C.RED if skip_clear else C.GREEN}{'TIDAK (Dilewati)' if skip_clear else 'YA (Otomatis)'}{C.RESET}
  • Tombol Hotkey   : {C.DIM}[R] Langsung Jalan | [S] Status | [Q] Keluar Lebih Awal{C.RESET}
============================================================
""")

    log(f"Memulai eksekusi sebanyak {cycles} siklus...", C.GREEN)

    for cycle_num in range(1, cycles + 1):
        try:
            success = execute_cycle(cycle_num, cycles, skip_clear=skip_clear)
            if not success:
                log(f"Siklus #{cycle_num} menghadapi kendala kritis.", C.YELLOW)

            # Jika ini bukan siklus terakhir, jalankan hitung mundur jeda waktu
            if cycle_num < cycles:
                continue_next = wait_countdown_between_cycles(cycle_num, cycles, interval_seconds)
                if not continue_next:
                    log("Pengguna meminta berhenti. Mengakhiri sisa siklus...", C.YELLOW)
                    break
        except KeyboardInterrupt:
            sys.stdout.write("\n")
            log(f"Proses dihentikan paksa oleh pengguna (Ctrl+C) pada siklus #{cycle_num}.", C.YELLOW)
            break
        except Exception as e:
            log(f"Terjadi kesalahan tak terduga pada siklus #{cycle_num}: {e}", C.RED)
            break

    # Tampilkan ringkasan akhir
    set_console_title("MacroListing - Semua Siklus Selesai")
    print_grand_summary()


if __name__ == "__main__":
    main()
