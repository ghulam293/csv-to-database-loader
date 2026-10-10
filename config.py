"""
config.py - all settings in ONE place.
Other files import from here, so we never repeat paths or settings.
"""

import logging
from pathlib import Path

# ---------- Folders and files ----------
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
REJECT_DIR = BASE_DIR / "rejected"
DB_PATH = BASE_DIR / "csv_database_loaded.duckdb"
LOG_FILE = BASE_DIR / "pipeline.log"

# ---------- Business settings ----------
PRODUCT_CATEGORY = {
    "Laptop": "Computers",
    "Monitor": "Computers",
    "Mouse": "Accessories",
    "Keyboard": "Accessories",
    "Webcam": "Accessories",
    "Headphones": "Audio",
}
DEFAULT_CATEGORY = "Other"


# ---------- Helper functions ----------
def ensure_folders():
    """Create the folders we need if they do not exist yet."""
    DATA_DIR.mkdir(exist_ok=True)
    REJECT_DIR.mkdir(exist_ok=True)


def get_logger(name="pipeline"):
    """Return a logger that prints to the screen AND writes to pipeline.log."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(formatter)

    screen_handler = logging.StreamHandler()
    screen_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(screen_handler)
    return logger