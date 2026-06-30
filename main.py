import asyncio
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeChat, Message

import premium as premium_helpers

if not getattr(premium_helpers, "PREMIUM_HELPERS_MODULE", False):
    raise SystemExit(
        "Błędny plik premium.py! To musi być moduł pomocniczy w katalogu głównym. "
        "Handlery Premium są w handlers/premium_menu.py."
    )

import db
from config import ADMIN_ID, BOT_TOKEN, BUILD_VERSION, DB_PATH, PREMIUM_ENABLED, PUBLIC_URL, WEBHOOK_PORT
from handlers import admin, profile, registration, start, swipe
from handlers.admin import run_giveadmin
from keyboards import main_menu_kb
from premium import is_premium_active
from seed_logic import GENDERS_JSON, PHOTOS_JSON, SEED_DATA_DIR
from states import AdminBroadcast, AdminSearch
from stripe_pay import create_health_app, create_webhook_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_COMMANDS = [
    BotCommand(command="start", description="Uruchom bota / Start"),
    BotCommand(command="help", description="Pomoc / Help"),
    BotCommand(command="myid", description="Twój Telegram ID / Ваш ID"),
    BotCommand(command="version", description="Wersja bota / Версия"),
]

ADMIN_COMMANDS = [
    BotCommand(command="admin", description="Panel admina"),
    BotCommand(command="giveadmin", description="Daj admina / Выдать админа"),
    BotCommand(command="seed_demo", description="Wgraj 300 profili demo"),
    BotCommand(command="seed_status", description="Ile profili demo w bazie"),
    BotCommand(command="dbinfo", description="Status bazy / Volume"),
    BotCommand(command="stats", description="Statystyki bota"),
]


async def setup_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(DEFAULT_COMMANDS, scope=BotCommandScopeAllPrivateChats())
    for admin_id in db.get_all_admin_ids():
        await bot.set_my_commands(
            DEFAULT_COMMANDS + ADMIN_COMMANDS,
            scope=BotCommandScopeChat(chat_id=admin_id),
        )
    logger.info("Admin command menu set for %s admin(s)", len(db.get_all_admin_ids()))


def register_handlers(dp: Dispatcher) -> None:
    """Register handlers. Admin commands FIRST; catch-all skips /commands."""
    admin.register(dp)
    logger.info(
        "Admin handlers registered: /admin /giveadmin /seed_demo /seed_status /stats /myid "
        "(aliases: seed demo, /seed demo) (build %s)",
        BUILD_VERSION,
    )

    @dp.message(Command("giveadmin"))
    async def cmd_giveadmin(message: Message, bot: Bot):
        await run_giveadmin(message, bot)

    start.register(dp)
    registration.register(dp)
    swipe.register(dp)
    profile.register(dp)
    if PREMIUM_ENABLED:
        from handlers import premium_menu

        premium_menu.register(dp)
        logger.info("Premium handlers enabled")
    else:
        logger.info("Premium disabled (PREMIUM_ENABLED=0)")

    @dp.message(Command("version"))
    async def cmd_version(message: Message):
        info = await db.get_db_status()
        persist = "✅ OK" if info["persistent_ok"] else "❌ слетит при Deploy"
        await message.answer(
            "CursorRandka\n"
            f"Build: <code>{BUILD_VERSION}</code>\n"
            f"DB: <code>{info['path']}</code>\n"
            f"Persistence: {persist}",
            parse_mode="HTML",
        )

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
        await message.answer(
            f"Nieznana komenda: {cmd}\n"
            f"Build na serwerze: <code>{BUILD_VERSION}</code>\n\n"
            f"Wpisz /help lub /version",
            parse_mode="HTML",
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
        "CursorRandka bot started! build=%s admin_id=%s premium=%s public_url=%s db=%s",
        BUILD_VERSION,
        ADMIN_ID or "not set",
        "yes" if PREMIUM_ENABLED else "no",
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
    if PREMIUM_ENABLED:
        webhook_app = create_webhook_app(bot)
    else:
        webhook_app = create_health_app()
    runner = web.AppRunner(webhook_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEBHOOK_PORT)
    await site.start()
    logger.info("Webhook server on 0.0.0.0:%s (health /health)", WEBHOOK_PORT)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
