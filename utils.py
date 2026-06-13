from aiogram.types import User as TgUser

from db import user_search_city


GENDER_MAP = {
    "👨 Mężczyzna": "M",
    "👩 Kobieta": "F",
}

GENDER_LABEL = {
    "M": "👨 Mężczyzna",
    "F": "👩 Kobieta",
}

LOOKING_MAP = {
    "👨 Mężczyzn": "M",
    "👩 Kobiety": "F",
    "👫 Wszystkich": "both",
}

LOOKING_LABEL = {
    "M": "👨 Mężczyzn",
    "F": "👩 Kobiety",
    "both": "👫 Wszystkich",
}


def contact_link(user: TgUser | dict) -> str:
    if isinstance(user, dict):
        uid = user["user_id"]
        username = user.get("username")
    else:
        uid = user.id
        username = user.username

    if username:
        return f"https://t.me/{username}"
    return f"tg://user?id={uid}"


def format_profile(user: dict, own: bool = False) -> str:
    gender = GENDER_LABEL.get(user["gender"], user["gender"])
    looking = LOOKING_LABEL.get(user["looking_for"], user["looking_for"])

    lines = [
        f"{'📋 Twój profil' if own else '👤 Profil'}",
        "",
        f"📝 {user['name']}, {user['age']} lat",
        f"{gender} · szuka: {looking}",
        f"🏙️ {user['city']}",
        "",
        f"💬 {user['bio'] or 'Brak opisu'}",
    ]
    if own:
        search = user_search_city(user)
        lines += [
            "",
            f"🔍 Szukam w: {search}",
            f"👁️ Wyświetlenia: {user['views_count']}",
            f"❤️ Polubienia: {user['likes_received']}",
        ]
    return "\n".join(lines)


def format_match_text(partner: dict) -> str:
    return (
        "💥 Wzajemna sympatia!\n\n"
        f"To {partner['name']}, {partner['age']} lat z {partner['city']}!\n"
        f"Napisz do tej osoby — może to coś więcej? 💕\n\n"
        f"🔗 Kontakt: {contact_link(partner)}"
    )
