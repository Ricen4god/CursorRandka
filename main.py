import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

import db
from config import BOT_TOKEN
from handlers import admin, profile, registration, start, swipe
from keyboards import main_menu_kb
from states import AdminBroadcast, AdminSearch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def register_handlers(dp: Dispatcher):
    """Register all handlers. Form/state handlers BEFORE catch-all."""
    start.register(dp)
    registration.register(dp)
    swipe.register(dp)
    profile.register(dp)
    admin.register(dp)

    @dp.message(F.text)
    async def unknown_text(message: Message, state: FSMContext):
        current = await state.get_state()
        if current in (
            AdminSearch.waiting_query.state,
            AdminBroadcast.waiting_message.state,
        ):
            return

        user = await db.get_user(message.from_user.id)
        if user:
            await message.answer(
                "Nie rozumiem 🤔 Użyj menu poniżej:",
                reply_markup=main_menu_kb(),
            )
        else:
            await message.answer(
                "Nie rozumiem 🤔 Wpisz /start aby rozpocząć!"
            )


async def main():
    if not BOT_TOKEN:
        raise SystemExit(
            "Brak BOT_TOKEN! Skopiuj .env.example do .env i uzupełnij token."
        )

    await db.init_db()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    register_handlers(dp)

    logger.info("CursorRandka bot started!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
