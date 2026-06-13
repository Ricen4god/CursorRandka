#!/usr/bin/env python3
"""Upload local images to Telegram and assign file_ids to test profiles (900001–900030).

Telegram bots cannot use local paths in answer_photo() — each image must be sent once
via Bot API to obtain a file_id, then stored in users.photo_file_id.

During upload you will receive one photo message per image in the admin chat (ADMIN_ID).
That is expected and required to capture valid file_ids.

Manual fallback (if BOT_TOKEN invalid):
  1. Send each image below to your bot in a private chat with @BotFather token.
  2. Call getUpdates or use @userinfobot / bot logs to read photo[-1].file_id.
  3. UPDATE users SET photo_file_id = '<file_id>' WHERE user_id = 900001; etc.

Uses exactly three desktop images (1.jpg, 2.jpg, 3.jpg). Each image is uploaded
once to Telegram; each test profile (900001–900030) receives exactly one
photo_file_id, chosen at random from the three file_ids.
"""

from __future__ import annotations

import asyncio
import os
import random
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or "0")
DB_PATH = os.getenv("DB_PATH", "database.db")

TEST_ID_START = 900001
TEST_ID_END = 900030

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MIN_FILE_SIZE = 1000
DESKTOP_IMAGE_NAMES = ("1.jpg", "2.jpg", "3.jpg")
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

# Fallback paths documented for manual upload (relative to user home)
DOCUMENTED_IMAGE_HINTS = [
    rf"OneDrive\Рабочий стол\{name}" for name in DESKTOP_IMAGE_NAMES
]


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _is_placeholder_token(token: str) -> bool:
    normalized = token.strip().lower()
    if normalized in PLACEHOLDER_TOKENS:
        return True
    if "your" in normalized and "token" in normalized:
        return True
    if len(normalized) < 20:
        return True
    return False


def _desktop_dir() -> Path:
    return Path.home() / "OneDrive" / "Рабочий стол"


def find_local_images() -> list[Path]:
    """Return exactly 1.jpg, 2.jpg, 3.jpg from the desktop (in that order)."""
    desktop = _desktop_dir()
    if not desktop.is_dir():
        return []

    images: list[Path] = []
    for name in DESKTOP_IMAGE_NAMES:
        path = desktop / name
        if not path.is_file():
            continue
        try:
            if path.stat().st_size < MIN_FILE_SIZE:
                continue
        except OSError:
            continue
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        images.append(path)
    return images


async def upload_photos(image_paths: list[Path]) -> list[tuple[Path, str]]:
    from aiogram import Bot
    from aiogram.types import FSInputFile

    bot = Bot(token=BOT_TOKEN)
    file_ids: list[tuple[Path, str]] = []

    try:
        me = await bot.get_me()
        print(f"Bot: @{me.username} (id={me.id})")

        for path in image_paths:
            photo = FSInputFile(str(path))
            msg = await bot.send_photo(
                chat_id=ADMIN_ID,
                photo=photo,
                caption=f"📷 upload_test_photos: {path.name}",
            )
            if not msg.photo:
                print(f"  ⚠ No photo in response for {path.name}, skipped")
                continue
            file_id = msg.photo[-1].file_id
            file_ids.append((path, file_id))
            print(f"  ✓ {path.name} → file_id …{file_id[-12:]}")
    finally:
        await bot.session.close()

    return file_ids


def update_test_users(file_ids: list[str]) -> tuple[int, dict[str, int]]:
    if not file_ids:
        return 0, {}

    db_file = Path(DB_PATH)
    if not db_file.is_file():
        raise SystemExit(f"Database not found: {db_file.resolve()}")

    user_ids = list(range(TEST_ID_START, TEST_ID_END + 1))
    random.shuffle(user_ids)
    assignments = {user_id: random.choice(file_ids) for user_id in user_ids}

    conn = sqlite3.connect(DB_PATH)
    try:
        for user_id, file_id in assignments.items():
            conn.execute(
                "UPDATE users SET photo_file_id = ? WHERE user_id = ?",
                (file_id, user_id),
            )
        conn.commit()

        count = conn.execute(
            f"""SELECT COUNT(*) FROM users
                WHERE user_id BETWEEN {TEST_ID_START} AND {TEST_ID_END}
                  AND TRIM(COALESCE(photo_file_id, '')) != ''"""
        ).fetchone()[0]

        distribution: dict[str, int] = {fid: 0 for fid in file_ids}
        for file_id in assignments.values():
            distribution[file_id] += 1
        return count, distribution
    finally:
        conn.close()


def print_manual_instructions(image_paths: list[Path]) -> None:
    print("\n--- Ручная загрузка (если токен недействителен) ---")
    print("1. Откройте личный чат с ботом и отправьте каждое фото.")
    print("2. Получите file_id через getUpdates или лог бота (photo[-1].file_id).")
    print("3. Обновите БД: UPDATE users SET photo_file_id='...' WHERE user_id=900001;")
    print("\nНайденные файлы:")
    for p in image_paths:
        print(f"  - {p}")
    if not image_paths:
        print("  (ничего не найдено — проверьте пути ниже)")
        for hint in DOCUMENTED_IMAGE_HINTS:
            print(f"  - {Path.home() / hint}")


async def main_async() -> int:
    _configure_stdout()

    if _is_placeholder_token(BOT_TOKEN):
        print("❌ BOT_TOKEN не задан или содержит placeholder.")
        print("   Откройте .env и укажите реальный токен от @BotFather, затем запустите снова:")
        print("   python upload_test_photos.py")
        images = find_local_images()
        print_manual_instructions(images)
        return 1

    if ADMIN_ID == 0:
        print("❌ ADMIN_ID не задан в .env (нужен ваш Telegram user id).")
        print_manual_instructions(find_local_images())
        return 1

    images = find_local_images()
    if len(images) < len(DESKTOP_IMAGE_NAMES):
        missing = [n for n in DESKTOP_IMAGE_NAMES if not (_desktop_dir() / n).is_file()]
        print(f"❌ Не все файлы найдены на рабочем столе. Отсутствуют: {', '.join(missing) or '—'}")
        print(f"   Ожидаются: {', '.join(DESKTOP_IMAGE_NAMES)} в {_desktop_dir()}")
        print_manual_instructions(images)
        return 1

    print(f"Найдено {len(images)} изображений:")
    for p in images:
        print(f"  • {p.name} ({p.stat().st_size // 1024} KB)")

    print(f"\nЗагружаю в Telegram (chat_id={ADMIN_ID})…")
    try:
        uploaded = await upload_photos(images)
    except Exception as exc:
        print(f"\n❌ Ошибка Telegram API: {exc}")
        print("   Проверьте BOT_TOKEN и что вы хотя бы раз написали боту /start.")
        print_manual_instructions(images)
        return 1

    if not uploaded:
        print("❌ Не удалось получить ни одного file_id.")
        return 1

    file_ids = [fid for _, fid in uploaded]
    profiles_with_photo, distribution = update_test_users(file_ids)

    print(f"\n✅ Готово!")
    print(f"   Загружено фото: {len(uploaded)}")
    print(f"   Профилей с photo_file_id (900001–900030): {profiles_with_photo}/30")
    print("\nИспользованные файлы:")
    for path, fid in uploaded:
        count = distribution.get(fid, 0)
        print(f"   {path.name} → …{fid[-12:]} ({count} профилей)")
    print("\nФото будут видны в 🔎 Przeglądaj (swipe.py использует photo_file_id).")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
