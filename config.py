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
HEADLESS = False  # Development mode requires False
MAX_RETRIES = 2

# Image Settings
IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"]

# Testing & Execution Modes
DRY_RUN = True  # If True, form is filled and verified but NOT submitted
TEST_SINGLE_ROW = True  # If True, only processes TEST_ROW_NO
TEST_ROW_NO = 1
