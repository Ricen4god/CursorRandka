from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from config import PREMIUM_ENABLED


def main_menu_kb(*, is_premium: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="🔎 Przeglądaj")],
        [KeyboardButton(text="👤 Mój profil"), KeyboardButton(text="💕 Sympatie")],
    ]
    if PREMIUM_ENABLED and is_premium:
        rows.append([KeyboardButton(text="💖 Kto Cię polubił")])
    if PREMIUM_ENABLED:
        rows.append([KeyboardButton(text="⭐ Premium")])
    rows += [
        [KeyboardButton(text="💤 Uśpij"), KeyboardButton(text="⚙️ Ustawienia")],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def gender_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👨 Mężczyzna"), KeyboardButton(text="👩 Kobieta")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def looking_for_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👨 Mężczyzn"), KeyboardButton(text="👩 Kobiety")],
            [KeyboardButton(text="👫 Wszystkich")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def profile_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✏️ Edytuj bio"), KeyboardButton(text="📷 Zmień zdjęcie")],
            [KeyboardButton(text="🏙️ Zmień miasto")],
            [KeyboardButton(text="📊 Statystyki"), KeyboardButton(text="🗑️ Usuń konto")],
            [KeyboardButton(text="◀️ Menu główne")],
        ],
        resize_keyboard=True,
    )


def settings_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏙️ Moje miasto"), KeyboardButton(text="🔍 Szukam w")],
            [KeyboardButton(text="☀️ Obudź profil"), KeyboardButton(text="🚫 Zablokowani")],
            [KeyboardButton(text="◀️ Menu główne")],
        ],
        resize_keyboard=True,
    )


def blocked_list_kb(blocked_ids: list[int]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"🔓 Odblokuj {uid}", callback_data=f"unblock:{uid}")]
        for uid in blocked_ids
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def swipe_kb(candidate_id: int, *, is_premium: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="👎 Pomiń", callback_data=f"skip:{candidate_id}"),
            InlineKeyboardButton(text="❤️ Lubię", callback_data=f"like:{candidate_id}"),
        ],
    ]
    if PREMIUM_ENABLED and is_premium:
        rows.append(
            [
                InlineKeyboardButton(
                    text="⭐ Super polubienie",
                    callback_data=f"superlike:{candidate_id}",
                ),
            ]
        )
    rows += [
        [
            InlineKeyboardButton(text="✉️ Napisz", callback_data=f"write:{candidate_id}"),
            InlineKeyboardButton(text="💤 Uśpij", callback_data="sleep_browse"),
        ],
        [
            InlineKeyboardButton(text="🚫 Zgłoś", callback_data=f"report:{candidate_id}"),
            InlineKeyboardButton(text="⛔ Zablokuj", callback_data=f"block:{candidate_id}"),
        ],
    ]
    if PREMIUM_ENABLED and is_premium:
        rows.append(
            [InlineKeyboardButton(text="↩️ Cofnij ostatnie", callback_data="premium:rewind")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def premium_kb(
    is_premium: bool,
    payments_ok: bool,
    *,
    checkout_url: str | None = None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if not is_premium and payments_ok:
        if checkout_url:
            rows.append(
                [InlineKeyboardButton(text="💳 Zapłać teraz", url=checkout_url)]
            )
        else:
            rows.append(
                [InlineKeyboardButton(text="💳 Kup Premium", callback_data="premium:buy")]
            )
    if is_premium:
        rows.append(
            [InlineKeyboardButton(text="💖 Kto Cię polubił", callback_data="premium:likers_hint")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def likers_kb(likers: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"❤️ {u['name']}, {u['age']}",
                callback_data=f"liker_like:{u['user_id']}",
            )
        ]
        for u in likers[:20]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def report_reasons_kb(candidate_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚫 Spam", callback_data=f"report_reason:{candidate_id}:spam")],
            [InlineKeyboardButton(text="🔞 Treści dla dorosłych", callback_data=f"report_reason:{candidate_id}:adult")],
            [InlineKeyboardButton(text="😡 Obraza / nękanie", callback_data=f"report_reason:{candidate_id}:harassment")],
            [InlineKeyboardButton(text="🎭 Fałszywy profil", callback_data=f"report_reason:{candidate_id}:fake")],
            [InlineKeyboardButton(text="❌ Anuluj", callback_data=f"cancel_report:{candidate_id}")],
        ]
    )


def remove_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
