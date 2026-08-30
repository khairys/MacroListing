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
HEADLESS = False  # Set to True for production, False for development
MAX_RETRIES = 2

# Image Settings
IMAGE_EXTENSION = ".jpg"

# Development / Testing Modes
DRY_RUN = True  # If True, form is filled but 'List Items' is NOT clicked
TEST_SINGLE_ROW = True  # If True, only processes one specific row
TEST_ROW_NO = 1  # The 'No' value in Excel to test if TEST_SINGLE_ROW is True
