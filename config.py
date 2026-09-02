import os

# Base Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
IMAGES_DIR = os.path.join(BASE_DIR, "images")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
SCREENSHOTS_DIR = os.path.join(LOGS_DIR, "screenshots")
BROWSER_PROFILE_PATH = os.path.join(BASE_DIR, "browser-profile")
EXCEL_FILE_PATH = os.path.join(DATA_DIR, "data.xlsx")

# Target
TARGET_URL = "https://zeusx.com/create-offer"

# Playwright Settings
MAX_RETRIES = 2
CDP_URL = "http://127.0.0.1:9222"

# Image Settings
IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"]

# Execution Mode
MODE = "batch" # 'test' or 'batch'
TEST_ROW_NO = 30

# --- Resilience Configuration ---

# Timeouts (milliseconds, for Playwright)
SITE_HEALTH_TIMEOUT = 15000
NAVIGATION_TIMEOUT = 15000
ELEMENT_TIMEOUT = 10000

# Retry Policy
RETRY_INITIAL_DELAY = 60       # seconds — first retry wait
RETRY_MAX_DELAY = 900          # seconds (15 minutes) — cap between retries
MAX_SITE_RETRIES = 5           # max health-check retries before giving up for the cycle
MAX_LISTING_RETRIES = MAX_RETRIES  # per-listing retries (uses existing MAX_RETRIES = 2)

# State / Runtime
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")
STATE_FILE = os.path.join(RUNTIME_DIR, "state.json")

# Exit Codes (used by main.py and clear_listings.py)
EXIT_SUCCESS = 0
EXIT_AUTOMATION_FAILURE = 1
EXIT_SITE_UNAVAILABLE = 2
EXIT_AUTH_REQUIRED = 3
EXIT_SUBMISSION_UNKNOWN = 4
EXIT_INTERRUPTED = 5
