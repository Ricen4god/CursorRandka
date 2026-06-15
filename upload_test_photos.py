#!/usr/bin/env python3
"""Upload desktop photos 1–20 to Telegram and save file_ids to seed_data/photos.json.

Telegram file_ids are tied to the bot token — the same BOT_TOKEN on Railway
can reuse these file_ids after committing seed_data/photos.json to git.

During upload you will receive one photo message per image in the admin chat.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from seed_logic import PERSONA_COUNT, PHOTOS_JSON, load_genders, save_photos

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or "0")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MIN_FILE_SIZE = 1000
PLACEHOLDER_TOKENS = {
    "",
    "your_bot_token",
    "your_bot_token_here",
    "paste_your_token_here",
    "xxx",
    "changeme",
    "token",
    "<your_bot_token>",
}


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _is_placeholder_token(token: str) -> bool:
    normalized = token.strip().lower()
    if normalized in PLACEHOLDER_TOKENS:
        return True
    if "your" in normalized and "token" in normalized:
        return True
    return len(normalized) < 20


def _desktop_dir() -> Path:
    return Path.home() / "OneDrive" / "Рабочий стол"


def _find_photo(number: int) -> Path | None:
    desktop = _desktop_dir()
    for ext in (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"):
        path = desktop / f"{number}{ext}"
        if path.is_file():
            try:
                if path.stat().st_size >= MIN_FILE_SIZE:
                    return path
            except OSError:
                continue
    return None


def find_local_images() -> list[tuple[int, Path]]:
    found: list[tuple[int, Path]] = []
    for number in range(1, PERSONA_COUNT + 1):
        path = _find_photo(number)
        if path:
            found.append((number, path))
    return found


async def upload_photos(items: list[tuple[int, Path]]) -> dict[str, str]:
    from aiogram import Bot
    from aiogram.types import FSInputFile

    bot = Bot(token=BOT_TOKEN)
    result: dict[str, str] = {}

    try:
        me = await bot.get_me()
        print(f"Bot: @{me.username} (id={me.id})")

        genders = load_genders()

        for number, path in items:
            persona = genders[str(number)]
            gender = persona["gender"]
            name = persona["name"]
            photo = FSInputFile(str(path))
            msg = await bot.send_photo(
                chat_id=ADMIN_ID,
                photo=photo,
                caption=(
                    f"📷 upload_test_photos #{number}: {path.name}\n"
                    f"Persona: {name} ({gender})"
                ),
            )
            if not msg.photo:
                print(f"  ⚠ No photo in response for {path.name}, skipped")
                continue
            file_id = msg.photo[-1].file_id
            result[str(number)] = file_id
            print(f"  ✓ #{number} {path.name} ({gender}) → …{file_id[-12:]}")
    finally:
        await bot.session.close()

    return result


def print_manual_instructions(items: list[tuple[int, Path]]) -> None:
    print("\n--- Ручная загрузка (если токен недействителен) ---")
    print("1. Отправьте каждое фото боту в личный чат.")
    print("2. Получите file_id через getUpdates (photo[-1].file_id).")
    print("3. Заполните seed_data/photos.json вручную и запустите seed_test_users.py")
    print("\nНайденные файлы:")
    for number, path in items:
        print(f"  #{number}: {path}")
    if not items:
        print(f"  (ничего не найдено в {_desktop_dir()})")


async def main_async() -> int:
    _configure_stdout()

    if _is_placeholder_token(BOT_TOKEN):
        print("❌ BOT_TOKEN не задан или содержит placeholder.")
        print("   Укажите реальный токен в .env и запустите снова:")
        print("   python upload_test_photos.py")
        print_manual_instructions(find_local_images())
        return 1

    if ADMIN_ID == 0:
        print("❌ ADMIN_ID не задан в .env (нужен ваш Telegram user id).")
        print_manual_instructions(find_local_images())
        return 1

    items = find_local_images()
    if len(items) < PERSONA_COUNT:
        found_nums = {n for n, _ in items}
        missing = [str(n) for n in range(1, PERSONA_COUNT + 1) if n not in found_nums]
        print(f"❌ Не все фото найдены на рабочем столе. Отсутствуют: {', '.join(missing)}")
        print(f"   Ожидаются: 1.jpg … 20.jpg (или .png) в {_desktop_dir()}")
        print_manual_instructions(items)
        return 1

    print(f"Найдено {len(items)} изображений:")
    for number, path in items:
        print(f"  • #{number}: {path.name} ({path.stat().st_size // 1024} KB)")

    print(f"\nЗагружаю в Telegram (chat_id={ADMIN_ID})…")
    try:
        uploaded = await upload_photos(items)
    except Exception as exc:
        print(f"\n❌ Ошибка Telegram API: {exc}")
        print("   Проверьте BOT_TOKEN и что вы написали боту /start.")
        print_manual_instructions(items)
        return 1

    if len(uploaded) < PERSONA_COUNT:
        print(f"❌ Загружено только {len(uploaded)}/{PERSONA_COUNT} фото.")
        return 1

    save_photos(uploaded)
    print(f"\n✅ Готово! file_ids сохранены в {PHOTOS_JSON}")
    print("   Следующий шаг: python seed_test_users.py")
    print("   Для Railway: закоммитьте seed_data/ и запустите seed на сервере.")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
