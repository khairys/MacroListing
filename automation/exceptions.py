class ValidationError(Exception):
    """Raised when data validation fails before or during execution."""
    pass

class FormInteractionError(Exception):
    """Raised when an interaction with the ZeusX form fails."""
    pass

class ImageUploadError(Exception):
    """Raised when image upload fails or preview is not detected."""
    pass

class LoginRequiredError(Exception):
    """Raised when manual login is required but not completed."""
    pass

class CaptchaDetectedError(Exception):
    """Raised when a CAPTCHA is detected and requires manual intervention."""
    pass

class SubmissionError(Exception):
    """Raised when the final form submission fails."""
    pass

class VerificationError(Exception):
    """Raised when the form state does not match expected values before submission."""
    pass

class SubmissionUnknownError(Exception):
    """Raised when the final form submission result is unknown (e.g. timeout after clicking submit)."""
    pass
