from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔎 Przeglądaj")],
            [KeyboardButton(text="👤 Mój profil"), KeyboardButton(text="💕 Sympatie")],
            [KeyboardButton(text="💤 Uśpij"), KeyboardButton(text="⚙️ Ustawienia")],
        ],
        resize_keyboard=True,
    )


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


def swipe_kb(candidate_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👎 Pomiń", callback_data=f"skip:{candidate_id}"),
                InlineKeyboardButton(text="❤️ Lubię", callback_data=f"like:{candidate_id}"),
            ],
            [
                InlineKeyboardButton(text="✉️ Napisz", callback_data=f"write:{candidate_id}"),
                InlineKeyboardButton(text="💤 Uśpij", callback_data="sleep_browse"),
            ],
            [
                InlineKeyboardButton(text="🚫 Zgłoś", callback_data=f"report:{candidate_id}"),
                InlineKeyboardButton(text="⛔ Zablokuj", callback_data=f"block:{candidate_id}"),
            ],
        ]
    )


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
