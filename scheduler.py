"""ZeusX Auto-Orchestrator — Self-Healing Scheduler.

Lifecycle per cycle:
    1. SITE HEALTH CHECK  (inline, via Playwright)
    2. CLEAR LISTINGS     (subprocess → clear_listings.py)
    3. VERIFY CLEAR       (check exit code)
    4. UPLOAD LISTINGS    (subprocess → main.py)
    5. VERIFY RESULT      (check exit code)
    6. CYCLE COMPLETE / RECOVERY

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
import subprocess
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from automation import state_manager

# Schedule configuration (Base 2 Hours ± 10 Minutes Jitter: 1h 50m to 2h 10m)
BASE_INTERVAL_HOURS = 2
JITTER_MINUTES = 10

MIN_INTERVAL_MINUTES = (BASE_INTERVAL_HOURS * 60) - JITTER_MINUTES  # 110 minutes (1h 50m)
MAX_INTERVAL_MINUTES = (BASE_INTERVAL_HOURS * 60) + JITTER_MINUTES  # 130 minutes (2h 10m)
MIN_INTERVAL_SECONDS = MIN_INTERVAL_MINUTES * 60
MAX_INTERVAL_SECONDS = MAX_INTERVAL_MINUTES * 60

# Retry policy (progressive backoff in seconds)
_BACKOFF_SCHEDULE = [60, 120, 300, 600, 900]


def log(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [SCHEDULER] {message}")


def get_backoff_delay(attempt: int) -> int:
    """Returns delay in seconds for a given retry attempt (1-indexed)."""
    idx = min(attempt - 1, len(_BACKOFF_SCHEDULE) - 1)
    return min(_BACKOFF_SCHEDULE[idx], config.RETRY_MAX_DELAY)


def run_script(script_name: str) -> int:
    """Runs a Python script as subprocess and returns its exit code.
    
    This is blocking: the scheduler waits until the script finishes.
    """
    log(f"Starting {script_name}...")
    try:
        result = subprocess.run(
            [sys.executable, script_name],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=False
        )
        exit_code = result.returncode
        log(f"Finished {script_name} with exit code {exit_code}.")
        return exit_code
    except Exception as e:
        log(f"FATAL: Could not run {script_name}: {e}")
        return 1  # Treat as automation failure


def perform_site_health_check() -> int:
    """Performs a quick site health check using Playwright directly.
    
    Returns the appropriate exit code:
        0 = site is ready
        2 = site unavailable
        3 = auth required
    """
    log("[HEALTH] Performing site health check...")
    try:
        from playwright.sync_api import sync_playwright
        from automation.site_health import check_site_health, SiteStatus
        
        pw = sync_playwright().start()
        try:
            browser = pw.chromium.connect_over_cdp(config.CDP_URL)
        except Exception as e:
            log(f"[HEALTH] Cannot connect to Chrome CDP: {e}")
            pw.stop()
            return config.EXIT_SITE_UNAVAILABLE
        
        context = browser.contexts[0] if browser.contexts else None
        if not context:
            log("[HEALTH] No browser context found.")
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
            return config.EXIT_SUCCESS
        elif status == SiteStatus.AUTH_REQUIRED:
            return config.EXIT_AUTH_REQUIRED
        else:
            return config.EXIT_SITE_UNAVAILABLE
            
    except Exception as e:
        log(f"[HEALTH] Health check failed: {e}")
        return config.EXIT_SITE_UNAVAILABLE


def wait_for_site_recovery() -> bool:
    """Waits for ZeusX to become available again using progressive backoff.
    
    Returns True if site recovered, False if max retries exhausted.
    """
    for attempt in range(1, config.MAX_SITE_RETRIES + 1):
        delay = get_backoff_delay(attempt)
        log(f"[RECOVERY] Attempt {attempt}/{config.MAX_SITE_RETRIES}: "
            f"Waiting {delay}s before retry...")
        time.sleep(delay)
        
        health_code = perform_site_health_check()
        
        if health_code == config.EXIT_SUCCESS:
            log("[RECOVERY] Site is back online!")
            return True
        elif health_code == config.EXIT_AUTH_REQUIRED:
            log("[RECOVERY] Auth required — cannot auto-recover. "
                "Please login manually in Chrome.")
            return False
        else:
            log(f"[RECOVERY] Site still unavailable (code {health_code}).")
    
    log(f"[RECOVERY] Max retries ({config.MAX_SITE_RETRIES}) exhausted. "
        "Giving up for this cycle.")
    return False


def job():
    """Executes one full automation cycle: health → clear → upload."""
    log("=" * 60)
    log(f"Initiating Scheduled Automation Cycle (Base: {BASE_INTERVAL_HOURS}h ± {JITTER_MINUTES}m)")
    log("=" * 60)
    
    # === PHASE 1: SITE HEALTH CHECK ===
    health_code = perform_site_health_check()
    
    if health_code == config.EXIT_AUTH_REQUIRED:
        log("[AUTH] Login required. Skipping this cycle.")
        log("Please login to ZeusX manually in the Chrome window.")
        log("=" * 60)
        return
    
    if health_code != config.EXIT_SUCCESS:
        log("[SITE DOWN] ZeusX is not available. Starting recovery loop...")
        recovered = wait_for_site_recovery()
        if not recovered:
            log("Could not reach ZeusX. Skipping this cycle entirely.")
            log("=" * 60)
            return
    
    # === PHASE 2: CLEAR LISTINGS ===
    log("[CYCLE] Starting cleanup phase...")
    clear_code = run_script("clear_listings.py")
    
    if clear_code == config.EXIT_SITE_UNAVAILABLE:
        log("[SITE DOWN] Site became unavailable during cleanup.")
        recovered = wait_for_site_recovery()
        if not recovered:
            log("Cannot proceed. Skipping this cycle.")
            log("=" * 60)
            return
        # Retry clear after recovery
        log("[RETRY] Retrying cleanup after recovery...")
        clear_code = run_script("clear_listings.py")
    
    if clear_code == config.EXIT_AUTH_REQUIRED:
        log("[AUTH] Login required during cleanup. Skipping this cycle.")
        log("=" * 60)
        return
    
    if clear_code != config.EXIT_SUCCESS:
        log(f"[CLEANUP FAILED] Exit code {clear_code}. "
            "Halting upload to prevent duplicate listings.")
        log("=" * 60)
        return
    
    log("[CLEANUP] Success. Verified.")
    
    # === PHASE 3: RESET STATE & PREPARE UPLOAD ===
    state_manager.clear_state()
    
    # Wait for ZeusX to settle after deletion
    log("Waiting 5 seconds before starting Upload phase...")
    time.sleep(5)
    
    # === PHASE 4: UPLOAD LISTINGS ===
    log("[CYCLE] Starting upload phase...")
    upload_code = run_script("main.py")
    
    if upload_code == config.EXIT_SUCCESS:
        log("[UPLOAD] All listings uploaded successfully!")
    elif upload_code == config.EXIT_SITE_UNAVAILABLE:
        log("[SITE DOWN] Site went down during upload.")
        log("Partial uploads will be cleaned up in the next cycle.")
        log("Completed listings are tracked in state file for reference.")
    elif upload_code == config.EXIT_AUTH_REQUIRED:
        log("[AUTH] Login expired during upload.")
        log("Please login to ZeusX manually before next cycle.")
    elif upload_code == config.EXIT_SUBMISSION_UNKNOWN:
        log("[WARNING] At least one submission has unknown status.")
        log("Check logs/automation.log for details.")
        log("These listings will NOT be auto-retried to prevent duplicates.")
    elif upload_code == config.EXIT_AUTOMATION_FAILURE:
        log("[UPLOAD] Some listings failed due to automation errors.")
        log("Failed listings are logged. Next cycle will start fresh.")
    else:
        log(f"[UPLOAD] Finished with exit code {upload_code}.")
    
    log("=" * 60)
    log("Cycle complete.")
    log("=" * 60)


if __name__ == "__main__":
    print(r"""
============================================================
  ZEUSX AUTO-ORCHESTRATOR v2.0
  Self-Healing & Auto-Scheduling Bot
============================================================
""")
    
    # Run once immediately upon starting
    log("Triggering the first run immediately...")
    job()
    
    # Schedule recurring runs with randomized jitter (1h 50m to 2h 10m)
    import schedule
    scheduled_job = schedule.every(MIN_INTERVAL_SECONDS).to(MAX_INTERVAL_SECONDS).seconds.do(job)
    
    log(f"Scheduler is now ACTIVE.")
    log(f"Cycle interval: {MIN_INTERVAL_MINUTES} to {MAX_INTERVAL_MINUTES} minutes (1h 50m to 2h 10m, randomized).")
    if scheduled_job.next_run:
        log(f"Next cycle scheduled at: {scheduled_job.next_run.strftime('%Y-%m-%d %H:%M:%S')}")
    log("You can minimize this terminal. Press CTRL+C to stop.")
    
    last_logged_next_run = scheduled_job.next_run

    # Infinite loop
    while True:
        try:
            schedule.run_pending()
            
            # Log next run time whenever schedule recalculates a new run time
            if scheduled_job.next_run != last_logged_next_run and scheduled_job.next_run is not None:
                remaining_mins = max(0.0, (scheduled_job.next_run - datetime.now()).total_seconds() / 60)
                log(f"Next cycle scheduled at: {scheduled_job.next_run.strftime('%Y-%m-%d %H:%M:%S')} (in {remaining_mins:.1f} minutes)")
                last_logged_next_run = scheduled_job.next_run
                
            time.sleep(10)
        except KeyboardInterrupt:
            log("Scheduler stopped by user.")
            break
