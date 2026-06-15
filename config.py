import os
from pathlib import Path

from dotenv import load_dotenv

from cities import cities_equal, normalize_city_name

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Bump when deploying — check Railway logs or /version in bot.
BUILD_VERSION = "2025-06-16-seed-fix-v20"

BOT_TOKEN = os.getenv("BOT_TOKEN", "")


def _parse_admin_id(raw: str | None) -> int:
    if not raw or not str(raw).strip():
        return 0
    try:
        return int(str(raw).strip())
    except ValueError:
        return 0


ADMIN_ID = _parse_admin_id(os.getenv("ADMIN_ID"))

_ON_RAILWAY = bool(
    os.getenv("RAILWAY_ENVIRONMENT")
    or os.getenv("RAILWAY_PROJECT_ID")
    or os.getenv("RAILWAY_SERVICE_ID")
)
_volume_mount = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "").strip().rstrip("/")
_db_path = os.getenv("DB_PATH", "").strip()
if _volume_mount:
    # Railway sets this when a volume is attached to the service.
    _db_path = f"{_volume_mount}/database.db"
elif not _db_path:
    _db_path = "/app/data/database.db" if _ON_RAILWAY else "database.db"
elif _ON_RAILWAY and _db_path in ("database.db", "./database.db"):
    _db_path = "/app/data/database.db"
DB_PATH = str(BASE_DIR / _db_path) if not os.path.isabs(_db_path) else _db_path
VOLUME_MOUNT_PATH = _volume_mount

PREMIUM_ENABLED = os.getenv("PREMIUM_ENABLED", "0").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

DAILY_LIKE_LIMIT = 50
MIN_AGE = 16
AGE_RANGE = 2  # ±2 years for free users
PREMIUM_AGE_RANGE = 5  # ±5 years for Premium

PREMIUM_PRICE_PLN = 24.99
PREMIUM_PRICE_GROSZE = 2499  # Stripe: smallest currency unit (grosze)
PREMIUM_DAYS = 30
DAILY_REWIND_LIMIT = 5
DAILY_SUPERLIKE_LIMIT = 1

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "").strip()
PUBLIC_URL = os.getenv("PUBLIC_URL", "").strip().rstrip("/")
WEBHOOK_PORT = int(os.getenv("PORT", "8080"))

# After local city feed is exhausted, reset to local after this many hours
# (or sooner when a new user registers in search_city).
FEED_RESET_HOURS = float(os.getenv("FEED_RESET_HOURS", "2"))

# Nearby-city groups for the 15 demo cities (seed_logic.CITIES).
NEARBY_CITIES: dict[str, list[str]] = {
    "Warszawa": ["Łódź", "Lublin", "Białystok", "Kielce"],
    "Kraków": ["Katowice", "Rzeszów", "Kielce", "Opole"],
    "Wrocław": ["Opole", "Łódź", "Poznań"],
    "Łódź": ["Warszawa", "Wrocław", "Poznań", "Kielce"],
    "Poznań": ["Wrocław", "Bydgoszcz", "Toruń", "Szczecin"],
    "Gdańsk": ["Bydgoszcz", "Toruń", "Szczecin"],
    "Szczecin": ["Poznań", "Gdańsk", "Bydgoszcz"],
    "Bydgoszcz": ["Toruń", "Poznań", "Gdańsk"],
    "Lublin": ["Warszawa", "Białystok", "Rzeszów", "Kielce"],
    "Katowice": ["Kraków", "Opole", "Rzeszów", "Wrocław"],
    "Białystok": ["Warszawa", "Lublin", "Gdańsk"],
    "Opole": ["Wrocław", "Katowice", "Kraków"],
    "Rzeszów": ["Kraków", "Lublin", "Katowice"],
    "Toruń": ["Bydgoszcz", "Gdańsk", "Poznań", "Warszawa"],
    "Kielce": ["Kraków", "Warszawa", "Lublin", "Łódź"],
}


def resolve_nearby_cities(search_city: str) -> list[str]:
    key = normalize_city_name(search_city)
    if not key:
        return []
    for city, nearby in NEARBY_CITIES.items():
        if cities_equal(city, key):
            return nearby
    return []


DISCLAIMER = (
    "⚠️ Pamiętaj, w internecie ludzie mogą udawać kogoś innego. "
    "Nigdy nie podawaj danych osobowych nieznajomym!"
)
