import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
_db_path = os.getenv("DB_PATH", "database.db")
DB_PATH = str(BASE_DIR / _db_path) if not os.path.isabs(_db_path) else _db_path

DAILY_LIKE_LIMIT = 50
MIN_AGE = 16
AGE_RANGE = 2  # ±2 years for matching

DISCLAIMER = (
    "⚠️ Pamiętaj, w internecie ludzie mogą udawać kogoś innego. "
    "Nigdy nie podawaj danych osobowych nieznajomym!"
)
