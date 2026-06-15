import asyncio
import time

from aiogram import Bot, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import db
from db import user_search_city
from config import FEED_RESET_HOURS, PREMIUM_ENABLED
from keyboards import like_notification_kb, main_menu_kb, report_reasons_kb, swipe_kb
from premium import age_range_for, is_premium_active
from states import DirectMessage, Report
from utils import contact_link, format_match_text, format_profile

SWIPE_COOLDOWN_SEC = 2.0
CARD_DELAY_SEC = 0.8
COOLDOWN_MSG = "Zwolnij 😅 Poczekaj chwilę"

_user_locks: dict[int, asyncio.Lock] = {}
_last_swipe_at: dict[int, float] = {}


def _user_lock(user_id: int) -> asyncio.Lock:
    if user_id not in _user_locks:
        _user_locks[user_id] = asyncio.Lock()
    return _user_locks[user_id]


def _on_cooldown(user_id: int) -> bool:
    return time.monotonic() - _last_swipe_at.get(user_id, 0) < SWIPE_COOLDOWN_SEC


def _mark_swipe(user_id: int) -> None:
    _last_swipe_at[user_id] = time.monotonic()


async def _safe_delete(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        pass


def _empty_browse_hint(user: dict | None, diag: dict) -> str:
    search = user_search_city(user) if user else ""
    min_age, max_age = diag.get("age_range", (None, None))

    lines = []
    if search:
        lines.append(f"Brak nowych osób w {search} 😔")
    else:
        lines.append("Brak nowych osób 😔")

    if diag.get("no_city_matches"):
        lines.append(
            f"W {search or 'tym mieście'} nikogo nie ma w wieku {min_age}–{max_age} lat."
        )
        lines.append("Zmień «🔍 Szukam w» w ⚙️ Ustawieniach (np. Opole).")
    elif diag.get("no_gender_matches"):
        lines.append("Brak profili pasujących do Twoich preferencji płci.")
    elif diag.get("all_viewed"):
        if diag.get("in_nearby_mode"):
            hours = int(FEED_RESET_HOURS) if FEED_RESET_HOURS == int(FEED_RESET_HOURS) else FEED_RESET_HOURS
            lines.append(
                f"Obejrzałeś/aś już wszystkich w pobliskich miastach — "
                f"za ~{hours} h wrócisz do profili z {search or 'Twojego miasta'}."
            )
        else:
            lines.append("Obejrzałeś/aś już wszystkich w okolicy — wróć później!")
    else:
        lines.append(
            f"Sprawdź «🔍 Szukam w» i wiek (±{age_range_for(user)} lat, teraz szukasz {min_age}–{max_age})."
        )
        lines.append("Ustawienia: ⚙️ Ustawienia → 🔍 Szukam w")

    return "\n".join(lines)


async def _show_candidate(message: Message, user_id: int, *, delay: bool = False):
    if delay:
        await asyncio.sleep(CARD_DELAY_SEC)

    user = await db.get_user(user_id)
    candidates, feed_notice = await db.get_candidates(user_id, limit=1)
    if feed_notice:
        await message.answer(feed_notice)
    if not candidates:
        diag = await db.diagnose_candidates(user_id)
        hint = _empty_browse_hint(user, diag)
        premium = is_premium_active(user)
        await message.answer(hint, reply_markup=main_menu_kb(is_premium=premium))
        return

    cand = candidates[0]
    await db.record_view(user_id, cand["user_id"])

    premium = is_premium_active(user)
    caption = format_profile(cand)
    photo_id = (cand.get("photo_file_id") or "").strip()
    kb = swipe_kb(cand["user_id"], is_premium=premium)
    if photo_id:
        await message.answer_photo(
            photo_id,
            caption=caption,
            reply_markup=kb,
        )
    else:
        await message.answer(caption, reply_markup=kb)


async def _notify_match(bot: Bot, user_id: int, partner: dict):
    text = format_match_text(partner)
    try:
        await bot.send_photo(
            user_id,
            partner["photo_file_id"],
            caption=text,
            reply_markup=main_menu_kb(),
        )
    except Exception:
        await bot.send_message(user_id, text, reply_markup=main_menu_kb())


async def _notify_like(bot: Bot, recipient_id: int, liker: dict, *, intro: str | None = None):
    """Tell user someone liked them — show profile + like/skip buttons."""
    if not liker or recipient_id == liker["user_id"]:
        return
    header = intro or "💖 <b>Ktoś Cię polubił!</b>\n\n"
    caption = f"{header}{format_profile(liker)}\n\nCo chcesz zrobić?"
    kb = like_notification_kb(liker["user_id"])
    photo_id = (liker.get("photo_file_id") or "").strip()
    try:
        if photo_id:
            await bot.send_photo(
                recipient_id,
                photo_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=kb,
            )
        else:
            await bot.send_message(
                recipient_id,
                caption,
                parse_mode="HTML",
                reply_markup=kb,
            )
    except Exception:
        pass


async def _like_back(user_id: int, candidate_id: int, bot: Bot) -> tuple[bool, str | None]:
    """Like someone from a notification. Returns (matched, error_msg)."""
    allowed, limit = await db.can_like_today(user_id)
    if not allowed:
        msg = f"Limit {limit} polubień na dziś!" if limit else "Limit polubień na dziś!"
        return False, msg

    if not await db.increment_daily_likes(user_id):
        return False, "Limit polubień na dziś wyczerpany!"

    matched = await db.add_like(user_id, candidate_id)
    if matched:
        partner = await db.get_user(candidate_id)
        me = await db.get_user(user_id)
        if partner:
            await _notify_match(bot, user_id, partner)
        if me:
            await _notify_match(bot, candidate_id, me)
    return matched, None


def register(dp: Dispatcher):
    @dp.message(F.text == "🔎 Przeglądaj")
    async def browse(message: Message, state: FSMContext):
        await state.clear()
        user = await db.get_user(message.from_user.id)
        if not user:
            await message.answer("Najpierw zarejestruj się — /start")
            return
        if user["is_banned"]:
            await message.answer("🚫 Twoje konto jest zablokowane.")
            return
        if not user["is_active"]:
            await message.answer(
                "Twój profil śpi 💤 Obudź go w Ustawieniach!",
                reply_markup=main_menu_kb(),
            )
            return

        user_id = message.from_user.id
        lock = _user_lock(user_id)
        if lock.locked():
            await message.answer(COOLDOWN_MSG)
            return

        async with lock:
            if _on_cooldown(user_id):
                await message.answer(COOLDOWN_MSG)
                return
            _mark_swipe(user_id)
            await db.touch_last_active(user_id)
            await _show_candidate(message, user_id)

    @dp.callback_query(F.data.startswith("skip:"))
    async def cb_skip(callback: CallbackQuery):
        user_id = callback.from_user.id
        lock = _user_lock(user_id)
        if lock.locked():
            await callback.answer(COOLDOWN_MSG, show_alert=True)
            return

        candidate_id = int(callback.data.split(":")[1])

        async with lock:
            if _on_cooldown(user_id):
                await callback.answer(COOLDOWN_MSG, show_alert=True)
                return
            _mark_swipe(user_id)
            await db.record_skip(user_id, candidate_id)
            await callback.answer("Pominięto")
            await _safe_delete(callback.message)
            await _show_candidate(callback.message, user_id, delay=True)

    @dp.callback_query(F.data.startswith("like:"))
    async def cb_like(callback: CallbackQuery, bot: Bot):
        user_id = callback.from_user.id
        lock = _user_lock(user_id)
        if lock.locked():
            await callback.answer(COOLDOWN_MSG, show_alert=True)
            return

        candidate_id = int(callback.data.split(":")[1])

        async with lock:
            if _on_cooldown(user_id):
                await callback.answer(COOLDOWN_MSG, show_alert=True)
                return

            allowed, limit = await db.can_like_today(user_id)
            if not allowed:
                msg = (
                    f"Limit {limit} polubień na dziś! Wróć jutro 😊"
                    if limit
                    else "Limit polubień na dziś!"
                )
                hint = (
                    "\n\n⭐ Premium = nielimitowane polubienia!"
                    if limit and PREMIUM_ENABLED
                    else ""
                )
                await callback.answer(f"{msg}{hint}", show_alert=True)
                return

            ok = await db.increment_daily_likes(user_id)
            if not ok:
                await callback.answer("Limit polubień na dziś wyczerpany!", show_alert=True)
                return

            _mark_swipe(user_id)
            matched = await db.add_like(user_id, candidate_id)
            await callback.answer("❤️ Polubiono!")

            if matched:
                partner = await db.get_user(candidate_id)
                me = await db.get_user(user_id)
                await _safe_delete(callback.message)
                await _notify_match(bot, user_id, partner)
                await _notify_match(bot, candidate_id, me)
            else:
                me = await db.get_user(user_id)
                if me:
                    recipient = await db.get_user(candidate_id)
                    if recipient:
                        await _notify_like(bot, candidate_id, me)
                await _safe_delete(callback.message)
                await _show_candidate(callback.message, user_id, delay=True)

    @dp.callback_query(F.data.startswith("superlike:"))
    async def cb_superlike(callback: CallbackQuery, bot: Bot):
        user_id = callback.from_user.id
        user = await db.get_user(user_id)
        if not is_premium_active(user):
            await callback.answer("Tylko Premium ⭐", show_alert=True)
            return

        lock = _user_lock(user_id)
        if lock.locked():
            await callback.answer(COOLDOWN_MSG, show_alert=True)
            return

        candidate_id = int(callback.data.split(":")[1])

        async with lock:
            if _on_cooldown(user_id):
                await callback.answer(COOLDOWN_MSG, show_alert=True)
                return

            if await db.get_daily_superlikes_count(user_id) >= 1:
                await callback.answer(
                    "Super polubienie: 1× dziennie! Wróć jutro ⭐",
                    show_alert=True,
                )
                return

            allowed, limit = await db.can_like_today(user_id)
            if not allowed:
                await callback.answer(
                    f"Limit {limit} polubień na dziś!",
                    show_alert=True,
                )
                return

            if not await db.increment_daily_superlikes(user_id):
                await callback.answer("Limit super polubień!", show_alert=True)
                return

            if not await db.increment_daily_likes(user_id):
                await callback.answer("Limit polubień na dziś!", show_alert=True)
                return

            _mark_swipe(user_id)
            matched = await db.add_like(user_id, candidate_id)
            await callback.answer("⭐ Super polubienie!")

            me = await db.get_user(user_id)
            if me and not matched:
                recipient = await db.get_user(candidate_id)
                if recipient:
                    await _notify_like(
                        bot,
                        candidate_id,
                        me,
                        intro="⭐ <b>Super polubienie!</b> Ktoś naprawdę Cię lubi!\n\n",
                    )

            if matched:
                partner = await db.get_user(candidate_id)
                await _safe_delete(callback.message)
                await _notify_match(bot, user_id, partner)
                await _notify_match(bot, candidate_id, me)
            else:
                await _safe_delete(callback.message)
                await _show_candidate(callback.message, user_id, delay=True)

    @dp.callback_query(F.data.startswith("write:"))
    async def cb_write(callback: CallbackQuery, state: FSMContext):
        candidate_id = int(callback.data.split(":")[1])
        await state.set_state(DirectMessage.waiting_message)
        await state.update_data(write_to=candidate_id)
        await callback.answer()
        await callback.message.answer(
            "Napisz wiadomość — trafi do tej osoby przed matchem! ✉️\n"
            "(Anuluj: wyślij /cancel)"
        )

    @dp.callback_query(F.data.startswith("liker_like:"))
    async def cb_liker_like(callback: CallbackQuery, bot: Bot):
        user_id = callback.from_user.id
        candidate_id = int(callback.data.split(":")[1])
        matched, err = await _like_back(user_id, candidate_id, bot)
        if err:
            await callback.answer(err, show_alert=True)
            return
        if matched:
            await callback.answer("💥 Match!")
            try:
                await callback.message.edit_caption(
                    caption="💕 Macie wzajemną sympatię!",
                    reply_markup=None,
                )
            except Exception:
                try:
                    await callback.message.edit_text("💕 Macie wzajemną sympatię!")
                except Exception:
                    pass
        else:
            await callback.answer("❤️ Polubiono!")
            try:
                await callback.message.edit_caption(
                    caption=callback.message.caption + "\n\n✅ Odpowiedziałeś/aś polubieniem!",
                    reply_markup=None,
                )
            except Exception:
                pass

    @dp.callback_query(F.data.startswith("liker_skip:"))
    async def cb_liker_skip(callback: CallbackQuery):
        user_id = callback.from_user.id
        liker_id = int(callback.data.split(":")[1])
        await db.record_skip(user_id, liker_id)
        await callback.answer("Pominięto")
        try:
            await callback.message.delete()
        except Exception:
            pass

    @dp.callback_query(F.data.startswith("liker_block:"))
    async def cb_liker_block(callback: CallbackQuery):
        user_id = callback.from_user.id
        liker_id = int(callback.data.split(":")[1])
        await db.block_user(user_id, liker_id)
        await callback.answer("Zablokowano ⛔")
        try:
            await callback.message.delete()
        except Exception:
            pass

    @dp.message(DirectMessage.waiting_message)
    async def direct_message_text(message: Message, state: FSMContext, bot: Bot):
        if message.text == "/cancel":
            await state.clear()
            await message.answer("Anulowano ✖️", reply_markup=main_menu_kb())
            return

        data = await state.get_data()
        candidate_id = data["write_to"]
        text = (message.text or "").strip()
        if len(text) < 1 or len(text) > 300:
            await message.answer("Wiadomość: 1–300 znaków ✏️")
            return

        allowed, limit = await db.can_like_today(message.from_user.id)
        if not allowed:
            await state.clear()
            await message.answer(
                f"Limit {limit} polubień na dziś!",
                reply_markup=main_menu_kb(
                    is_premium=is_premium_active(await db.get_user(message.from_user.id))
                ),
            )
            return

        await db.increment_daily_likes(message.from_user.id)
        matched = await db.add_like(message.from_user.id, candidate_id, message=text)
        await state.clear()

        me = await db.get_user(message.from_user.id)
        if me:
            try:
                await _notify_like(
                    bot,
                    candidate_id,
                    me,
                    intro=f"✉️ <b>Ktoś napisał do Ciebie!</b>\n\n💬 «{text}»\n\n",
                )
            except Exception:
                pass

        if matched:
            partner = await db.get_user(candidate_id)
            await _notify_match(bot, message.from_user.id, partner)
            await _notify_match(bot, candidate_id, me)
        else:
            await message.answer(
                "Wiadomość wysłana! 💌 Jeśli ta osoba też Cię polubi — macie match!",
                reply_markup=main_menu_kb(),
            )
            await _show_candidate(message, message.from_user.id, delay=True)

    @dp.callback_query(F.data == "sleep_browse")
    async def cb_sleep_browse(callback: CallbackQuery):
        await db.update_user(callback.from_user.id, is_active=0)
        await callback.answer("Profil uśpiony 💤")
        await _safe_delete(callback.message)
        await callback.message.answer(
            "Twój profil śpi — nikt Cię nie zobaczy.\n"
            "Obudź go w ⚙️ Ustawienia → ☀️ Obudź profil",
            reply_markup=main_menu_kb(),
        )

    @dp.callback_query(F.data.startswith("block:"))
    async def cb_block(callback: CallbackQuery):
        user_id = callback.from_user.id
        lock = _user_lock(user_id)
        if lock.locked():
            await callback.answer(COOLDOWN_MSG, show_alert=True)
            return

        candidate_id = int(callback.data.split(":")[1])
        async with lock:
            if _on_cooldown(user_id):
                await callback.answer(COOLDOWN_MSG, show_alert=True)
                return
            _mark_swipe(user_id)
            await db.block_user(user_id, candidate_id)
            await callback.answer("Zablokowano ⛔")
            await _safe_delete(callback.message)
            await _show_candidate(callback.message, user_id, delay=True)

    @dp.callback_query(F.data.startswith("report:"))
    async def cb_report(callback: CallbackQuery):
        candidate_id = int(callback.data.split(":")[1])
        await callback.answer()
        await callback.message.answer(
            "Dlaczego zgłaszasz ten profil?",
            reply_markup=report_reasons_kb(candidate_id),
        )

    @dp.callback_query(F.data.startswith("report_reason:"))
    async def cb_report_reason(callback: CallbackQuery):
        parts = callback.data.split(":")
        candidate_id = int(parts[1])
        reason = parts[2]
        reasons = {
            "spam": "Spam",
            "adult": "Treści dla dorosłych",
            "harassment": "Obraza / nękanie",
            "fake": "Fałszywy profil",
        }
        await db.add_report(
            callback.from_user.id,
            candidate_id,
            reasons.get(reason, reason),
        )
        await callback.answer("Zgłoszenie wysłane 🚫")
        await callback.message.edit_text("Dziękujemy za zgłoszenie. Sprawdzimy to! ✅")

    @dp.callback_query(F.data.startswith("cancel_report:"))
    async def cb_cancel_report(callback: CallbackQuery):
        await callback.answer("Anulowano")
        await callback.message.delete()

    @dp.callback_query(F.data.startswith("unblock:"))
    async def cb_unblock(callback: CallbackQuery):
        blocked_id = int(callback.data.split(":")[1])
        await db.unblock_user(callback.from_user.id, blocked_id)
        await callback.answer("Odblokowano 🔓")

    @dp.message(F.text == "💕 Sympatie")
    async def show_matches(message: Message, state: FSMContext):
        await state.clear()
        matches = await db.get_matches(message.from_user.id)
        if not matches:
            await message.answer(
                "Jeszcze brak sympatii 😔 Polub kogoś w 🔎 Przeglądaj!",
                reply_markup=main_menu_kb(),
            )
            return

        await message.answer(f"💕 Twoje sympatie ({len(matches)}):", reply_markup=main_menu_kb())
        for m in matches:
            caption = (
                f"💥 {m['name']}, {m['age']} lat · {m['city']}\n"
                f"🔗 {contact_link(m)}"
            )
            photo_id = (m.get("photo_file_id") or "").strip()
            if photo_id:
                await message.answer_photo(m["photo_file_id"], caption=caption)
            else:
                await message.answer(caption)

    @dp.message(F.text == "💤 Uśpij")
    async def sleep_profile(message: Message, state: FSMContext):
        await state.clear()
        user = await db.get_user(message.from_user.id)
        if not user:
            return
        await db.update_user(message.from_user.id, is_active=0)
        await message.answer(
            "Twój profil śpi 💤 Nikt Cię nie zobaczy.\n"
            "Obudź go w ⚙️ Ustawienia.",
            reply_markup=main_menu_kb(),
        )
