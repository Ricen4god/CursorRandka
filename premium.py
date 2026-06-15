"""Premium subscription helpers."""

from datetime import datetime

from config import (
    AGE_RANGE,
    DAILY_LIKE_LIMIT,
    DAILY_REWIND_LIMIT,
    DAILY_SUPERLIKE_LIMIT,
    PREMIUM_AGE_RANGE,
    PREMIUM_DAYS,
    PREMIUM_ENABLED,
    PREMIUM_PRICE_PLN,
    PUBLIC_URL,
    STRIPE_SECRET_KEY,
)


def stripe_configured() -> bool:
    if not PREMIUM_ENABLED:
        return False
    return bool(
        STRIPE_SECRET_KEY
        and STRIPE_SECRET_KEY.startswith(("sk_live_", "sk_test_"))
        and PUBLIC_URL.startswith("https://")
    )


def is_premium_active(user: dict | None) -> bool:
    if not PREMIUM_ENABLED:
        return False
    if not user:
        return False
    until = user.get("premium_until")
    if not until:
        return False
    try:
        return datetime.fromisoformat(until) > datetime.utcnow()
    except ValueError:
        return False


def age_range_for(user: dict | None) -> int:
    return PREMIUM_AGE_RANGE if is_premium_active(user) else AGE_RANGE


def daily_like_limit_for(user: dict | None) -> int | None:
    """None = unlimited."""
    if is_premium_active(user):
        return None
    return DAILY_LIKE_LIMIT


PREMIUM_FEATURES_TEXT = (
    "⭐ <b>CursorRandka Premium</b> — <b>{price:.2f} zł / mies.</b>\n\n"
    "✅ <b>Nielimitowane polubienia</b> (zamiast 50/dzień)\n"
    "✅ <b>Kto Cię polubił</b> — zobacz i odpowiedz od razu\n"
    "✅ <b>Cofnij «Pomiń»</b> — do {rewinds} razy dziennie\n"
    "✅ <b>Szerszy wiek</b> — ±{premium_age} lat (zamiast ±{free_age})\n"
    "✅ <b>Priorytet w feedzie</b> — Twój profil częściej widoczny\n"
    "✅ <b>Super polubienie</b> — {superlikes}× dziennie z powiadomieniem\n"
    "✅ <b>Rozszerzone statystyki</b>\n"
    "✅ <b>Znaczek ⭐ Premium</b> na profilu"
).format(
    price=PREMIUM_PRICE_PLN,
    rewinds=DAILY_REWIND_LIMIT,
    premium_age=PREMIUM_AGE_RANGE,
    free_age=AGE_RANGE,
    superlikes=DAILY_SUPERLIKE_LIMIT,
)
