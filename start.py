from aiogram import Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import db
from config import BUILD_VERSION, DISCLAIMER, MIN_AGE, PREMIUM_ENABLED, PREMIUM_PRICE_PLN
from keyboards import main_menu_kb, remove_kb
from premium import is_premium_active
from states import AdminBroadcast, AdminSearch, Registration


def register(dp: Dispatcher):
    @dp.message(CommandStart())
    async def cmd_start(message: Message, state: FSMContext):
        await state.clear()
        user = await db.get_user(message.from_user.id)

        if user:
            await db.touch_last_active(message.from_user.id)
            if user["is_banned"]:
                await message.answer("🚫 Twoje konto zostało zablokowane.")
                return
            await message.answer(
                f"Hej {user['name']}! Gotowy/a na randkę? 💕\n\n{DISCLAIMER}",
                reply_markup=main_menu_kb(is_premium=is_premium_active(user)),
            )
            return

        await state.set_state(Registration.age)
        await message.answer(
            "Hej! Gotowy/a na randkę? 💕\n\n"
            f"{DISCLAIMER}\n\n"
            "Zaczynamy rejestrację! Ile masz lat? (minimum 16)",
            reply_markup=remove_kb(),
        )

    @dp.message(F.text == "◀️ Menu główne")
    async def back_to_menu(message: Message, state: FSMContext):
        await state.clear()
        user = await db.get_user(message.from_user.id)
        if not user:
            await message.answer("Najpierw ukończ rejestrację — wpisz /start")
            return
        await message.answer("Wracamy do menu! 💕", reply_markup=main_menu_kb(is_premium=is_premium_active(user)))

    @dp.message(Command("cancel"))
    async def cmd_cancel(message: Message, state: FSMContext):
        current = await state.get_state()
        if not current:
            return

        admin_fsm = current in (
            AdminBroadcast.waiting_message.state,
            AdminSearch.waiting_query.state,
        )
        await state.clear()

        if admin_fsm and db.is_admin(message.from_user.id):
            from handlers.admin import _send_dashboard

            await message.answer("❌ Действие отменено.")
            await _send_dashboard(message)
            return

        user = await db.get_user(message.from_user.id)
        kb = main_menu_kb() if user else None
        await message.answer("Anulowano ✖️", reply_markup=kb)

    @dp.message(Command("version"))
    async def cmd_version(message: Message):
        info = await db.get_db_status()
        persist = "✅ OK" if info["persistent_ok"] else "❌ слетит при Deploy"
        await message.answer(
            f"CursorRandka\n"
            f"Build: <code>{BUILD_VERSION}</code>\n"
            f"DB: <code>{info['path']}</code>\n"
            f"Persistence: {persist}",
            parse_mode="HTML",
        )

    @dp.message(Command("help"))
    async def cmd_help(message: Message):
        text = (
            "<b>CursorRandka</b> — bot randkowy 💕\n\n"
            "🔎 <b>Przeglądaj</b> — przeglądaj profile w wybranym mieście\n"
            "👤 <b>Mój profil</b> — zobacz i edytuj swój profil\n"
            "💕 <b>Sympatie</b> — wzajemne polubienia\n"
            "💤 <b>Uśpij</b> — ukryj profil na jakiś czas\n"
            "⚙️ <b>Ustawienia</b> — miasto, szukanie, obudź profil\n"
        )
        if PREMIUM_ENABLED:
            text += (
                "⭐ <b>Premium</b> — więcej polubień, kto Cię polubił i więcej\n\n"
                "Możesz szukać osób w dowolnym mieście — ustaw «🔍 Szukam w» w ustawieniach.\n"
                "Np. mieszkasz w Opolu, a przeglądasz profile we Wrocławiu!\n\n"
                f"Limit polubień: 50 dziennie (free) · Premium od {PREMIUM_PRICE_PLN:.2f} zł/mies. ⭐"
            )
        else:
            text += (
                "\nMożesz szukać osób w dowolnym mieście — ustaw «🔍 Szukam w» w ustawieniach.\n"
                "Np. mieszkasz w Opolu, a przeglądasz profile we Wrocławiu!\n\n"
                "Limit polubień: 50 dziennie."
            )
        await message.answer(text, parse_mode="HTML")
