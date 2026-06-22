"""Premium menu handlers (NOT root premium.py — helpers live in ../premium.py)."""

from aiogram import Dispatcher, F
from aiogram.types import CallbackQuery, Message

import db
from config import DAILY_REWIND_LIMIT, PREMIUM_ENABLED, PREMIUM_PRICE_PLN
from keyboards import likers_kb, main_menu_kb, premium_kb
from premium import PREMIUM_FEATURES_TEXT, is_premium_active, stripe_configured
from stripe_pay import create_checkout_session
from utils import format_profile


def _premium_status_line(user: dict) -> str:
    if is_premium_active(user):
        until = (user.get("premium_until") or "")[:10]
        return f"\n\n✅ <b>Twój Premium aktywny</b> do {until}"
    return f"\n\n💳 <b>{PREMIUM_PRICE_PLN:.2f} zł / mies.</b>"


def register(dp: Dispatcher):
    if not PREMIUM_ENABLED:
        return

    @dp.message(F.text == "⭐ Premium")
    async def premium_menu(message: Message):
        user = await db.get_user(message.from_user.id)
        if not user:
            await message.answer("Najpierw zarejestruj się — /start")
            return

        text = PREMIUM_FEATURES_TEXT + _premium_status_line(user)
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=premium_kb(is_premium_active(user), stripe_configured()),
        )

    @dp.callback_query(F.data == "premium:buy")
    async def cb_premium_buy(callback: CallbackQuery):
        user = await db.get_user(callback.from_user.id)
        if not user:
            await callback.answer("Najpierw /start", show_alert=True)
            return
        if is_premium_active(user):
            await callback.answer("Masz już aktywne Premium! ⭐", show_alert=True)
            return
        if not stripe_configured():
            await callback.answer(
                "Płatności wkrótce dostępne. Napisz do admina.",
                show_alert=True,
            )
            return

        url, err = await create_checkout_session(callback.from_user.id)
        if err or not url:
            await callback.answer(
                (err or "Błąd płatności.")[:200],
                show_alert=True,
            )
            return

        await callback.answer()
        await callback.message.answer(
            f"💳 Opłać Premium — <b>{PREMIUM_PRICE_PLN:.2f} zł / mies.</b>\n\n"
            "👇 Kliknij <b>Zapłać teraz</b> — otworzy się strona Stripe.\n"
            "Po płatności wróć tutaj — Premium włączy się automatycznie.",
            parse_mode="HTML",
            reply_markup=premium_kb(False, True, checkout_url=url),
        )

    @dp.message(F.text == "💖 Kto Cię polubił")
    async def who_liked_me(message: Message):
        user = await db.get_user(message.from_user.id)
        if not user:
            return
        if not is_premium_active(user):
            await message.answer(
                "💖 <b>Kto Cię polubił</b> jest dostępne tylko w Premium ⭐\n\n"
                f"Wejdź w ⭐ Premium — od {PREMIUM_PRICE_PLN:.2f} zł/mies.",
                parse_mode="HTML",
                reply_markup=premium_kb(False, stripe_configured()),
            )
            return

        likers = await db.get_likers(message.from_user.id)
        if not likers:
            await message.answer(
                "Jeszcze nikt Cię nie polubił w tajemnicy 😔\n"
                "Przeglądaj dalej w 🔎 Przeglądaj!",
                reply_markup=main_menu_kb(is_premium=True),
            )
            return

        await message.answer(
            f"💖 <b>Kto Cię polubił</b> ({len(likers)}):\n"
            "Kliknij ❤️, żeby dać match!",
            parse_mode="HTML",
            reply_markup=likers_kb(likers),
        )

    @dp.callback_query(F.data == "premium:likers_hint")
    async def cb_likers_hint(callback: CallbackQuery):
        await callback.answer()
        await callback.message.answer("Użyj przycisku 💖 Kto Cię polubił w menu głównym")

    @dp.callback_query(F.data == "premium:rewind")
    async def cb_premium_rewind(callback: CallbackQuery):
        user_id = callback.from_user.id
        user = await db.get_user(user_id)
        if not is_premium_active(user):
            await callback.answer("Tylko Premium ⭐", show_alert=True)
            return

        rewinds = await db.get_daily_rewinds_count(user_id)
        if rewinds >= DAILY_REWIND_LIMIT:
            await callback.answer(
                f"Limit {DAILY_REWIND_LIMIT} cofnięć na dziś!",
                show_alert=True,
            )
            return

        last = await db.get_last_skip(user_id)
        if not last:
            await callback.answer("Brak ostatniego pominięcia", show_alert=True)
            return

        ok = await db.increment_daily_rewinds(user_id)
        if not ok:
            await callback.answer("Limit cofnięć wyczerpany!", show_alert=True)
            return

        restored = await db.undo_last_skip(user_id)
        if not restored:
            await callback.answer("Nie udało się cofnąć", show_alert=True)
            return

        await callback.answer("↩️ Przywrócono!")
        caption = format_profile(restored)
        photo_id = (restored.get("photo_file_id") or "").strip()
        from keyboards import swipe_kb

        kb = swipe_kb(restored["user_id"], is_premium=True)
        if photo_id:
            await callback.message.answer_photo(
                photo_id, caption=caption, reply_markup=kb
            )
        else:
            await callback.message.answer(caption, reply_markup=kb)
