# =============================================================================
# Exception Hierarchy for MacroListing
# =============================================================================
#
# Three distinct categories:
#
# 1. SiteError        — ZeusX / network / infrastructure problems
# 2. AutomationError  — form filling / business logic problems
# 3. SubmissionUnknownError — submit clicked but result unknown (NEVER auto-retry)
#
# This hierarchy lets the scheduler/orchestrator take different actions
# depending on WHAT went wrong, not just THAT something went wrong.
# =============================================================================


# === SITE / NETWORK ERRORS ===================================================
# These indicate the website or network is the problem, NOT the automation code.

class SiteError(Exception):
    """Base class for all site/network/infrastructure errors."""
    pass

class SiteUnavailableError(SiteError):
    """ZeusX is down, returning HTTP 5xx, or page cannot be reached."""
    pass

class NetworkError(SiteError):
    """DNS failure, connection refused, timeout at network level."""
    pass

class CloudflareChallengeError(SiteError):
    """Cloudflare or security verification is blocking access."""
    pass

class AuthenticationError(SiteError):
    """Session expired or login required. Needs manual intervention."""
    pass

class PageNotReadyError(SiteError):
    """Page loaded but is not in an expected/usable state (blank, wrong URL, etc.)."""
    pass


# === AUTOMATION ERRORS ========================================================
# These indicate the automation logic or form interaction failed.
# The website itself is fine; something went wrong with our bot's actions.

class AutomationError(Exception):
    """Base class for all automation/form/business-logic errors."""
    pass

class ValidationError(AutomationError):
    """Raised when data validation fails before or during execution."""
    pass

class FormInteractionError(AutomationError):
    """Raised when an interaction with the ZeusX form fails."""
    pass

class ImageUploadError(AutomationError):
    """Raised when image upload fails or preview is not detected."""
    pass

class CaptchaDetectedError(AutomationError):
    """Raised when a CAPTCHA is detected and requires manual intervention."""
    pass

class VerificationError(AutomationError):
    """Raised when the form state does not match expected values before submission."""
    pass

class SubmissionError(AutomationError):
    """Raised when the final form submission definitively fails."""
    pass

# Keep LoginRequiredError as an alias for backward compatibility
LoginRequiredError = AuthenticationError


# === SUBMISSION UNKNOWN =======================================================
# This is intentionally NOT a subclass of AutomationError or SiteError.
# It represents a dangerous ambiguous state: submit was clicked, but we
# cannot determine if ZeusX accepted it. MUST NEVER be auto-retried.

class SubmissionUnknownError(Exception):
    """Raised when the final form submission result is unknown.
    
    Examples:
    - Submit button clicked, but network died before response
    - Submit button clicked, but page timed out before toast/redirect
    - Browser disconnected right after submit
    
    CRITICAL: Do NOT automatically resubmit. This risks duplicate listings.
    """
    pass
