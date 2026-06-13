import asyncio
import time

from aiogram import Bot, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import db
from db import user_search_city
from config import AGE_RANGE, DAILY_LIKE_LIMIT
from keyboards import main_menu_kb, report_reasons_kb, swipe_kb
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
        lines.append("Obejrzałeś/aś już wszystkich w okolicy — wróć później!")
    else:
        lines.append(
            f"Sprawdź «🔍 Szukam w» i wiek (±{AGE_RANGE} lata, teraz szukasz {min_age}–{max_age})."
        )
        lines.append("Ustawienia: ⚙️ Ustawienia → 🔍 Szukam w")

    return "\n".join(lines)


async def _show_candidate(message: Message, user_id: int, *, delay: bool = False):
    if delay:
        await asyncio.sleep(CARD_DELAY_SEC)

    user = await db.get_user(user_id)
    candidates = await db.get_candidates(user_id, limit=1)
    if not candidates:
        diag = await db.diagnose_candidates(user_id)
        hint = _empty_browse_hint(user, diag)
        await message.answer(hint, reply_markup=main_menu_kb())
        return

    cand = candidates[0]
    await db.record_view(user_id, cand["user_id"])

    caption = format_profile(cand)
    photo_id = (cand.get("photo_file_id") or "").strip()
    if photo_id:
        await message.answer_photo(
            photo_id,
            caption=caption,
            reply_markup=swipe_kb(cand["user_id"]),
        )
    else:
        await message.answer(caption, reply_markup=swipe_kb(cand["user_id"]))


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

        async with lock:
            if _on_cooldown(user_id):
                await callback.answer(COOLDOWN_MSG, show_alert=True)
                return
            _mark_swipe(user_id)
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

            count = await db.get_daily_likes_count(user_id)
            if count >= DAILY_LIKE_LIMIT:
                await callback.answer(
                    f"Limit {DAILY_LIKE_LIMIT} polubień na dziś! Wróć jutro 😊",
                    show_alert=True,
                )
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

        count = await db.get_daily_likes_count(message.from_user.id)
        if count >= DAILY_LIKE_LIMIT:
            await state.clear()
            await message.answer(
                f"Limit {DAILY_LIKE_LIMIT} polubień na dziś!",
                reply_markup=main_menu_kb(),
            )
            return

        await db.increment_daily_likes(message.from_user.id)
        matched = await db.add_like(message.from_user.id, candidate_id, message=text)
        await state.clear()

        me = await db.get_user(message.from_user.id)
        try:
            await bot.send_photo(
                candidate_id,
                me["photo_file_id"],
                caption=(
                    f"✉️ Ktoś napisał do Ciebie!\n\n"
                    f"{me['name']}, {me['age']} lat · {me['city']}\n\n"
                    f"💬 «{text}»\n\n"
                    "Wejdź w 🔎 Przeglądaj, żeby odpowiedzieć!"
                ),
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
