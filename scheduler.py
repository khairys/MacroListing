import os
import sys
import time
import schedule
import subprocess
from datetime import datetime

# Configure your schedule here
INTERVAL_HOURS = 3

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [SCHEDULER] {message}")

def run_script(script_name):
    """Runs a Python script as a subprocess and waits for it to complete."""
    log(f"Starting {script_name}...")
    try:
        # Using subprocess.run ensures the script is blocking and we wait for its completion.
        # It also isolates the Playwright contexts, preventing memory leaks over long periods.
        result = subprocess.run(
            [sys.executable, script_name],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=False,
            check=True
        )
        log(f"Successfully finished {script_name}.")
        return True
    except subprocess.CalledProcessError as e:
        log(f"ERROR: {script_name} crashed or returned an error code ({e.returncode}).")
        return False
    except Exception as e:
        log(f"FATAL ERROR while trying to run {script_name}: {str(e)}")
        return False

def job():
    log("=" * 60)
    log(f"Initiating Scheduled Automation Cycle (Interval: {INTERVAL_HOURS} Hours)")
    log("=" * 60)
    
    # 1. CLEANUP PHASE
    # We must wait for this to finish completely before uploading.
    cleanup_success = run_script("clear_listings.py")
    
    if not cleanup_success:
        log("Cleanup phase failed! Halting the upload phase to prevent duplicate listings.")
        log("Will retry everything in the next scheduled cycle.")
        log("=" * 60)
        return
        
    # Wait a few seconds for safety before starting the upload
    log("Cleanup verified. Waiting 5 seconds before starting Upload phase...")
    time.sleep(5)
    
    # 2. UPLOAD PHASE
    upload_success = run_script("main.py")
    
    if not upload_success:
        log("Upload phase failed mid-way!")
        log("Don't worry, the next cycle will automatically clean up the partial uploads.")
    else:
        log("Automation cycle completed flawlessly!")
        
    log("=" * 60)
    log(f"Going to sleep. Next cycle in {INTERVAL_HOURS} hours...")
    log("=" * 60)

if __name__ == "__main__":
    print(r"""
============================================================
  ZEUSX AUTO-ORCHESTRATOR 
  Self-Healing & Auto-Scheduling Bot
============================================================
""")
    
    # Run once immediately upon starting
    log("Triggering the first run immediately...")
    job()
    
    # Schedule the recurring job
    schedule.every(INTERVAL_HOURS).hours.do(job)
    
    log(f"Scheduler is now ACTIVE. Background timer set for every {INTERVAL_HOURS} hours.")
    log("You can minimize this terminal. Press CTRL+C to stop.")
    
    # Infinite loop to keep the scheduler alive
    while True:
        try:
            schedule.run_pending()
            time.sleep(60) # Wake up every minute to check the schedule
        except KeyboardInterrupt:
            log("Scheduler stopped by user.")
            break
