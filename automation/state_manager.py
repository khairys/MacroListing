"""State Manager for MacroListing.

Provides atomic state persistence for resume capability.
State is stored as a simple JSON file in runtime/state.json.

Key design decisions:
- Atomic writes (write to temp, then rename) to prevent corruption
- Only marks listings as completed AFTER verified submission
- SubmissionUnknown listings are tracked separately and NEVER auto-retried
- State is reset at the start of each new cycle (after clear succeeds)
- No credentials, cookies, or secrets are stored
"""

import os
import json
import tempfile
from datetime import datetime
import config


def _ensure_runtime_dir():
    """Creates the runtime directory if it doesn't exist."""
    os.makedirs(config.RUNTIME_DIR, exist_ok=True)


def _atomic_write(data: dict):
    """Writes state to file atomically (write to temp, then rename)."""
    _ensure_runtime_dir()
    
    # Write to a temp file in the same directory, then rename
    fd, temp_path = tempfile.mkstemp(
        dir=config.RUNTIME_DIR, suffix=".tmp", prefix="state_"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        # Atomic rename (on Windows, need to remove target first if it exists)
        if os.path.exists(config.STATE_FILE):
            os.replace(temp_path, config.STATE_FILE)
        else:
            os.rename(temp_path, config.STATE_FILE)
    except Exception:
        # Cleanup temp file if rename failed
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def load_state() -> dict | None:
    """Loads the current state from disk. Returns None if no state exists."""
    if not os.path.exists(config.STATE_FILE):
        return None
    try:
        with open(config.STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def create_new_cycle(total_listings: int) -> dict:
    """Creates a fresh state for a new automation cycle.
    
    Call this AFTER clear_listings succeeds and BEFORE uploading.
    """
    state = {
        "cycle_id": datetime.now().isoformat(),
        "status": "in_progress",
        "total_listings": total_listings,
        "completed_listings": [],
        "failed_listings": [],
        "unknown_listings": [],
        "current_listing": None,
        "last_updated": datetime.now().isoformat()
    }
    _atomic_write(state)
    return state


def mark_listing_started(listing_no: str):
    """Marks a listing as currently being processed."""
    state = load_state()
    if state is None:
        return
    state["current_listing"] = listing_no
    state["last_updated"] = datetime.now().isoformat()
    _atomic_write(state)


def mark_listing_completed(listing_no: str):
    """Marks a listing as successfully submitted and verified."""
    state = load_state()
    if state is None:
        return
    if listing_no not in state["completed_listings"]:
        state["completed_listings"].append(listing_no)
    state["current_listing"] = None
    state["last_updated"] = datetime.now().isoformat()
    _atomic_write(state)


def mark_listing_failed(listing_no: str):
    """Marks a listing as definitively failed (all retries exhausted)."""
    state = load_state()
    if state is None:
        return
    if listing_no not in state["failed_listings"]:
        state["failed_listings"].append(listing_no)
    state["current_listing"] = None
    state["last_updated"] = datetime.now().isoformat()
    _atomic_write(state)


def mark_listing_unknown(listing_no: str):
    """Marks a listing as submission-unknown. Will NOT be auto-retried."""
    state = load_state()
    if state is None:
        return
    if listing_no not in state["unknown_listings"]:
        state["unknown_listings"].append(listing_no)
    state["current_listing"] = None
    state["last_updated"] = datetime.now().isoformat()
    _atomic_write(state)


def mark_cycle_paused(reason: str):
    """Marks the cycle as paused (e.g., site went down mid-batch)."""
    state = load_state()
    if state is None:
        return
    state["status"] = "paused"
    state["pause_reason"] = reason
    state["last_updated"] = datetime.now().isoformat()
    _atomic_write(state)


def mark_cycle_completed():
    """Marks the cycle as fully completed."""
    state = load_state()
    if state is None:
        return
    state["status"] = "completed"
    state["current_listing"] = None
    state["last_updated"] = datetime.now().isoformat()
    _atomic_write(state)


def get_completed_listings() -> list[str]:
    """Returns list of listing numbers that were already completed in this cycle."""
    state = load_state()
    if state is None:
        return []
    return state.get("completed_listings", [])


def get_unknown_listings() -> list[str]:
    """Returns list of listing numbers with unknown submission status."""
    state = load_state()
    if state is None:
        return []
    return state.get("unknown_listings", [])


def clear_state():
    """Removes the state file entirely. Call when starting a fresh cycle."""
    if os.path.exists(config.STATE_FILE):
        os.remove(config.STATE_FILE)
