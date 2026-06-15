import asyncio
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeChat, Message

import db
from config import ADMIN_ID, BOT_TOKEN, DB_PATH, PUBLIC_URL, WEBHOOK_PORT
from handlers import admin, premium, profile, registration, start, swipe
from keyboards import main_menu_kb
from premium import is_premium_active, stripe_configured
from seed_logic import GENDERS_JSON, PHOTOS_JSON, SEED_DATA_DIR
from states import AdminBroadcast, AdminSearch
from stripe_pay import create_webhook_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bump when deploying — check Railway logs for this line after redeploy.
BUILD_VERSION = "2025-06-15-persist-v11"

DEFAULT_COMMANDS = [
    BotCommand(command="start", description="Uruchom bota / Start"),
    BotCommand(command="help", description="Pomoc / Help"),
    BotCommand(command="myid", description="Twój Telegram ID / Ваш ID"),
]

ADMIN_COMMANDS = [
    BotCommand(command="admin", description="Panel admina"),
    BotCommand(command="seed_demo", description="Wgraj 300 profili demo"),
    BotCommand(command="seed_status", description="Ile profili demo w bazie"),
    BotCommand(command="stats", description="Statystyki bota"),
]


async def setup_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(DEFAULT_COMMANDS, scope=BotCommandScopeAllPrivateChats())
    if ADMIN_ID:
        await bot.set_my_commands(
            DEFAULT_COMMANDS + ADMIN_COMMANDS,
            scope=BotCommandScopeChat(chat_id=ADMIN_ID),
        )
        logger.info("Admin command menu set for ADMIN_ID=%s", ADMIN_ID)


def register_handlers(dp: Dispatcher) -> None:
    """Register handlers. Admin commands FIRST; catch-all skips /commands."""
    admin.register(dp)
    logger.info(
        "Admin handlers registered: /admin /seed_demo /seed_status /stats /myid "
        "(aliases: seed demo, /seed demo) (build %s)",
        BUILD_VERSION,
    )

    start.register(dp)
    registration.register(dp)
    swipe.register(dp)
    profile.register(dp)
    premium.register(dp)

    @dp.message(F.text, ~F.text.startswith("/"))
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
                reply_markup=main_menu_kb(is_premium=is_premium_active(user)),
            )
        else:
            await message.answer(
                "Nie rozumiem 🤔 Wpisz /start aby rozpocząć!"
            )

    @dp.message(F.text.startswith("/"))
    async def unknown_command(message: Message, state: FSMContext):
        current = await state.get_state()
        if current in (
            AdminSearch.waiting_query.state,
            AdminBroadcast.waiting_message.state,
        ):
            return

        cmd = (message.text or "").split()[0].split("@")[0].lower()
        hint = ""
        if cmd in ("/seed_demo", "/seed", "/seed_status", "/admin"):
            hint = (
                "\n\nJeśli jesteś adminem, sprawdź logi Railway: "
                f"build={BUILD_VERSION}, ADMIN_ID."
            )
        await message.answer(
            f"Nieznana komenda: {cmd}{hint}\n\nWpisz /help"
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
    await setup_bot_commands(bot)

    logger.info(
        "CursorRandka bot started! build=%s admin_id=%s stripe=%s public_url=%s db=%s",
        BUILD_VERSION,
        ADMIN_ID or "not set",
        "yes" if stripe_configured() else "no",
        PUBLIC_URL or "not set",
        DB_PATH,
    )
    seed_ok = SEED_DATA_DIR.is_dir() and PHOTOS_JSON.is_file() and GENDERS_JSON.is_file()
    if seed_ok:
        logger.info(
            "seed_data OK: dir=%s photos.json=True genders.json=True",
            SEED_DATA_DIR,
        )
    else:
        logger.warning(
            "seed_data MISSING on container — /seed_demo will fail until you push "
            "seed_data/genders.json + seed_data/photos.json to GitHub and redeploy. "
            "dir_exists=%s photos.json=%s genders.json=%s path=%s",
            SEED_DATA_DIR.is_dir(),
            PHOTOS_JSON.is_file(),
            GENDERS_JSON.is_file(),
            SEED_DATA_DIR,
        )
    webhook_app = create_webhook_app(bot)
    runner = web.AppRunner(webhook_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEBHOOK_PORT)
    await site.start()
    logger.info("Webhook server on 0.0.0.0:%s (health /health)", WEBHOOK_PORT)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
