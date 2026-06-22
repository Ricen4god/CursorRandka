import html

from aiogram.types import User as TgUser

from db import user_search_city
from premium import is_premium_active


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
        f"{'📋 Twój profil' if own else '👤 Profil'}"
        + (" ⭐" if not own and is_premium_active(user) else ""),
        "",
        f"📝 {user['name']}, {user['age']} lat",
        f"{gender} · szuka: {looking}",
        f"🏙️ {user['city']}",
        "",
        f"💬 {user['bio'] or 'Brak opisu'}",
    ]
    if own:
        search = user_search_city(user)
        premium_line = ""
        if is_premium_active(user):
            until = (user.get("premium_until") or "")[:10]
            premium_line = f"⭐ Premium do: {until}"
        lines += [
            "",
            f"🔍 Szukam w: {search}",
            f"👁️ Wyświetlenia: {user['views_count']}",
            f"❤️ Polubienia: {user['likes_received']}",
        ]
        if premium_line:
            lines.append(premium_line)
    return "\n".join(lines)


def format_profile_html(user: dict, own: bool = False) -> str:
    """format_profile with HTML-safe escaping for Telegram parse_mode=HTML."""
    gender = GENDER_LABEL.get(user["gender"], user["gender"])
    looking = LOOKING_LABEL.get(user["looking_for"], user["looking_for"])
    name = html.escape(str(user["name"]))
    city = html.escape(str(user["city"]))
    bio = html.escape(str(user["bio"] or "Brak opisu"))

    lines = [
        f"{'📋 Twój profil' if own else '👤 Profil'}"
        + (" ⭐" if not own and is_premium_active(user) else ""),
        "",
        f"📝 {name}, {user['age']} lat",
        f"{gender} · szuka: {looking}",
        f"🏙️ {city}",
        "",
        f"💬 {bio}",
    ]
    if own:
        search = html.escape(user_search_city(user))
        premium_line = ""
        if is_premium_active(user):
            until = (user.get("premium_until") or "")[:10]
            premium_line = f"⭐ Premium do: {until}"
        lines += [
            "",
            f"🔍 Szukam w: {search}",
            f"👁️ Wyświetlenia: {user['views_count']}",
            f"❤️ Polubienia: {user['likes_received']}",
        ]
        if premium_line:
            lines.append(premium_line)
    return "\n".join(lines)


def format_match_text(partner: dict) -> str:
    return (
        "💥 Wzajemna sympatia!\n\n"
        f"To {partner['name']}, {partner['age']} lat z {partner['city']}!\n"
        f"Napisz do tej osoby — może to coś więcej? 💕\n\n"
        f"🔗 Kontakt: {contact_link(partner)}"
    )
