import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")


def _parse_admin_id(raw: str | None) -> int:
    if not raw or not str(raw).strip():
        return 0
    try:
        return int(str(raw).strip())
    except ValueError:
        return 0


ADMIN_ID = _parse_admin_id(os.getenv("ADMIN_ID"))
_db_path = os.getenv("DB_PATH", "database.db")
DB_PATH = str(BASE_DIR / _db_path) if not os.path.isabs(_db_path) else _db_path

DAILY_LIKE_LIMIT = 50
MIN_AGE = 16
AGE_RANGE = 2  # ±2 years for free users
PREMIUM_AGE_RANGE = 5  # ±5 years for Premium

PREMIUM_PRICE_PLN = 24.99
PREMIUM_PRICE_GROSZE = 2499  # Stripe: smallest currency unit (grosze)
PREMIUM_DAYS = 30
DAILY_REWIND_LIMIT = 5
DAILY_SUPERLIKE_LIMIT = 1

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "")
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
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
    key = (search_city or "").strip()
    if not key:
        return []
    lower = key.lower()
    for city, nearby in NEARBY_CITIES.items():
        if city.lower() == lower:
            return nearby
    return []


DISCLAIMER = (
    "⚠️ Pamiętaj, w internecie ludzie mogą udawać kogoś innego. "
    "Nigdy nie podawaj danych osobowych nieznajomym!"
)
