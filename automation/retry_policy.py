"""Centralized retry policy for MacroListing.

Provides progressive backoff delays and error classification for retry decisions.
All retry logic across the project should use this module instead of ad-hoc sleep values.
"""

import config
from automation.exceptions import (
    SiteError, SiteUnavailableError, NetworkError, CloudflareChallengeError,
    AuthenticationError, PageNotReadyError,
    AutomationError, ValidationError, SubmissionUnknownError
)

# Progressive backoff schedule (in seconds)
_BACKOFF_SCHEDULE = [60, 120, 300, 600, 900]


def get_backoff_delay(attempt: int) -> int:
    """Returns the delay in seconds for a given retry attempt (1-indexed).
    
    Uses a progressive schedule capped at RETRY_MAX_DELAY from config.
    
    attempt 1 → 60s  (1 minute)
    attempt 2 → 120s (2 minutes)
    attempt 3 → 300s (5 minutes)
    attempt 4 → 600s (10 minutes)
    attempt 5+ → 900s (15 minutes)
    """
    idx = min(attempt - 1, len(_BACKOFF_SCHEDULE) - 1)
    delay = _BACKOFF_SCHEDULE[idx]
    return min(delay, config.RETRY_MAX_DELAY)


def is_retryable_for_listing(error: Exception) -> bool:
    """Determines if a listing-level error should be retried.
    
    Returns True for transient automation errors (selector failed, image upload failed).
    Returns False for errors that retrying won't fix.
    """
    # NEVER retry these
    if isinstance(error, SubmissionUnknownError):
        return False
    if isinstance(error, ValidationError):
        return False
    if isinstance(error, AuthenticationError):
        return False
    
    # Site errors should NOT be retried at listing level — they should be
    # escalated to the orchestrator for site-level recovery
    if isinstance(error, SiteError):
        return False
    
    # Automation errors (form, image, verification) CAN be retried
    if isinstance(error, AutomationError):
        return True
    
    # Unknown exceptions — don't retry by default
    return False


def is_site_retryable(error: Exception) -> bool:
    """Determines if a site-level error should trigger a health-check retry loop.
    
    Returns True for transient site problems (down, slow, Cloudflare).
    Returns False for problems that need manual intervention.
    """
    if isinstance(error, AuthenticationError):
        return False  # Needs manual login — don't keep retrying
    
    if isinstance(error, (SiteUnavailableError, NetworkError, 
                          CloudflareChallengeError, PageNotReadyError)):
        return True
    
    return False


def classify_exit_code(error: Exception) -> int:
    """Maps an exception to the appropriate process exit code."""
    if isinstance(error, SubmissionUnknownError):
        return config.EXIT_SUBMISSION_UNKNOWN
    if isinstance(error, AuthenticationError):
        return config.EXIT_AUTH_REQUIRED
    if isinstance(error, SiteError):
        return config.EXIT_SITE_UNAVAILABLE
    if isinstance(error, (AutomationError, Exception)):
        return config.EXIT_AUTOMATION_FAILURE
    return config.EXIT_AUTOMATION_FAILURE
