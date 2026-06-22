import asyncio
import logging
import traceback
from functools import wraps

from aiogram import Bot, Dispatcher, F
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import db
from config import BUILD_VERSION, DB_PATH, PREMIUM_ENABLED
from seed_logic import (
    CITIES,
    PERSONA_COUNT,
    SEED_DATA_DIR,
    TEST_ID_END,
    TEST_ID_START,
    count_test_users,
    seed_all_profiles,
)
from states import AdminBroadcast, AdminSearch
from utils import GENDER_LABEL, LOOKING_LABEL

logger = logging.getLogger(__name__)

USERS_PER_PAGE = 10
REPORTS_PER_PAGE = 5
BROADCAST_RATE = 30


def is_admin(user_id: int) -> bool:
    return db.is_admin(user_id)


def admin_only(func):
    @wraps(func)
    async def wrapper(event, *args, **kwargs):
        user_id = event.from_user.id
        if not is_admin(user_id):
            if isinstance(event, CallbackQuery):
                await event.answer("Доступ запрещён", show_alert=True)
            elif isinstance(event, Message):
                await _deny_not_admin(event)
            return None
        return await func(event, *args, **kwargs)

    return wrapper


def _matches_seed_demo_text(text: str | None) -> bool:
    """Match /seed_demo, /seed demo, seed demo (any case, extra spaces)."""
    if not text:
        return False
    raw = text.strip()
    if "@" in raw:
        raw = raw.split("@", 1)[0].strip()
    if raw.startswith("/"):
        raw = raw[1:].strip()
    compact = " ".join(raw.lower().replace("_", " ").split())
    return compact == "seed demo"


class SeedDemoTrigger(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return _matches_seed_demo_text(message.text)


async def _deny_not_admin(message: Message) -> None:
    user_id = message.from_user.id
    logger.info(
        "admin access denied: user_id=%s text=%r",
        user_id,
        message.text,
    )
    await message.answer(
        f"🚫 Доступ запрещён. Ваш ID: {user_id}\n"
        "Проверьте, что ADMIN_ID в Railway Variables совпадает с вашим ID.\n"
        "Отправьте /myid чтобы узнать свой Telegram ID."
    )


def admin_only_command(func):
    @wraps(func)
    async def wrapper(message: Message, *args, **kwargs):
        if not is_admin(message.from_user.id):
            await _deny_not_admin(message)
            return None
        return await func(message, *args, **kwargs)

    return wrapper


def _log_admin_message(message: Message, tag: str) -> None:
    logger.info(
        "admin %s: user_id=%s username=%s text=%r is_admin=%s",
        tag,
        message.from_user.id,
        message.from_user.username,
        message.text,
        is_admin(message.from_user.id),
    )


async def _log(admin_id: int, action: str, target_id: int | None = None, details: str | None = None):
    await db.log_admin_action(admin_id, action, target_id, details)


def _dashboard_kb(pending_reports: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="adm:stats")],
            [InlineKeyboardButton(text="👥 Пользователи", callback_data="adm:users:0")],
            [
                InlineKeyboardButton(
                    text=f"🚨 Жалобы ({pending_reports})",
                    callback_data="adm:reports:0",
                )
            ],
            [InlineKeyboardButton(text="📢 Рассылка", callback_data="adm:broadcast")],
            [InlineKeyboardButton(text="🔍 Найти юзера", callback_data="adm:search")],
            [InlineKeyboardButton(text="⬅️ Закрыть", callback_data="adm:close")],
        ]
    )


def _back_dashboard_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ В панель", callback_data="adm:menu")],
        ]
    )


def _pagination_kb(prefix: str, page: int, total: int, per_page: int) -> list[InlineKeyboardButton]:
    buttons = []
    max_page = max(0, (total - 1) // per_page) if total else 0
    if page > 0:
        buttons.append(
            InlineKeyboardButton(text="⬅️", callback_data=f"adm:{prefix}:{page - 1}")
        )
    if page < max_page:
        buttons.append(
            InlineKeyboardButton(text="➡️", callback_data=f"adm:{prefix}:{page + 1}")
        )
    return buttons


def _user_actions_kb(user_id: int, user: dict, back: str = "adm:menu") -> InlineKeyboardMarkup:
    rows = []

    if user.get("is_banned"):
        rows.append([
            InlineKeyboardButton(text="✅ Разбанить", callback_data=f"adm:unban:{user_id}")
        ])
    else:
        rows.append([
            InlineKeyboardButton(text="🚫 Забанить", callback_data=f"adm:ban:{user_id}")
        ])

    if user.get("is_shadow_banned"):
        rows.append([
            InlineKeyboardButton(
                text="👻 Снять теневой бан",
                callback_data=f"adm:shadow_off:{user_id}",
            )
        ])
    else:
        rows.append([
            InlineKeyboardButton(
                text="👻 Теневой бан",
                callback_data=f"adm:shadow_on:{user_id}",
            )
        ])

    rows.append([
        InlineKeyboardButton(text="📊 Статистика", callback_data=f"adm:ustats:{user_id}"),
        InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"adm:delete:{user_id}"),
    ])
    rows.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data=back),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _format_admin_user_card(user: dict) -> str:
    gender = GENDER_LABEL.get(user["gender"], user["gender"])
    looking = LOOKING_LABEL.get(user["looking_for"], user["looking_for"])
    username = f"@{user['username']}" if user.get("username") else "—"

    flags = []
    if user.get("is_banned"):
        flags.append("🚫 Забанен")
    if user.get("is_shadow_banned"):
        flags.append("👻 Теневой бан")
    if not user.get("is_active"):
        flags.append("💤 Профиль на паузе")
    status = ", ".join(flags) if flags else "🟢 Активен"

    lines = [
        "👤 Карточка пользователя",
        "",
        f"🆔 ID: {user['user_id']}",
        f"📛 Username: {username}",
        f"📝 {user['name']}, {user['age']} лет",
        f"{gender} · ищет: {looking}",
        f"🏙️ {user['city']}",
        "",
        f"💬 {user['bio'] or 'Без описания'}",
        "",
        f"📅 Регистрация: {user.get('created_at', '—')}",
        f"🕐 Последняя активность: {user.get('last_active') or user.get('created_at', '—')}",
        f"Статус: {status}",
    ]
    if user.get("ban_reason"):
        lines.append(f"📋 Причина бана: {user['ban_reason']}")
    return "\n".join(lines)


def _format_stats_text(stats: dict) -> str:
    cities_lines = []
    for i, row in enumerate(stats["top_cities"], 1):
        cities_lines.append(f"  {i}. {row['city']} — {row['cnt']}")

    cities_block = "\n".join(cities_lines) if cities_lines else "  —"

    return (
        "📊 <b>Статистика CursorRandka</b>\n\n"
        f"👥 Всего пользователей: <b>{stats['total_users']}</b>\n"
        f"🟢 Активны сегодня (24ч): <b>{stats['active_today']}</b>\n"
        f"✅ Активные профили: <b>{stats['active_profiles']}</b>\n"
        f"💤 На паузе: <b>{stats['paused_profiles']}</b>\n"
        f"❤️ Всего лайков: <b>{stats['total_likes']}</b>\n"
        f"💕 Матчей: <b>{stats['total_matches']}</b>\n"
        f"🚨 Жалоб (ожидают): <b>{stats['pending_reports']}</b>\n"
        f"🆕 Регистраций сегодня: <b>{stats['registrations_today']}</b>\n\n"
        f"🏙️ <b>Топ-5 городов:</b>\n{cities_block}"
    )


async def _send_dashboard(message: Message, edit: bool = False):
    pending = await db.count_pending_reports()
    text = (
        "🛡️ <b>Админ-панель CursorRandka</b>\n\n"
        f"Ожидают рассмотрения жалоб: <b>{pending}</b>\n"
        "Выберите раздел:"
    )
    kb = _dashboard_kb(pending)
    if edit:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")


async def _render_reports(callback: CallbackQuery, page: int):
    reports, total = await db.get_pending_reports(page, REPORTS_PER_PAGE)

    if not reports:
        text = "🚨 Нет ожидающих жалоб ✅"
        kb = _back_dashboard_kb()
        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=kb)
        else:
            await callback.message.edit_text(text, reply_markup=kb)
        return

    lines = [f"🚨 <b>Жалобы</b> (стр. {page + 1})\n"]
    buttons = []

    for r in reports:
        reporter = r.get("reporter_name") or str(r["reporter_id"])
        reported = r.get("reported_name") or str(r["reported_id"])
        lines.append(
            f"#{r['id']} · {reported} ← {reporter}\n"
            f"   {r['reason']} · {r['created_at']}"
        )
        buttons.append([
            InlineKeyboardButton(
                text=f"#{r['id']} — {reported}",
                callback_data=f"adm:report:{r['id']}:{page}",
            )
        ])

    nav = _pagination_kb("reports", page, total, REPORTS_PER_PAGE)
    if nav:
        buttons.append(nav)
    buttons.append([
        InlineKeyboardButton(text="⬅️ В панель", callback_data="adm:menu")
    ])

    text = "\n".join(lines)
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    if callback.message.photo:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


async def _show_user_card(
    bot,
    chat_id: int,
    user_id: int,
    back: str = "adm:menu",
    message: Message | None = None,
    callback: CallbackQuery | None = None,
):
    user = await db.get_user(user_id)
    if not user:
        text = f"❌ Пользователь {user_id} не найден."
        kb = _back_dashboard_kb()
        if callback and callback.message.photo:
            await callback.message.delete()
            await bot.send_message(chat_id, text, reply_markup=kb)
        elif callback:
            await callback.message.edit_text(text, reply_markup=kb)
        elif message:
            await message.answer(text, reply_markup=kb)
        return

    caption = _format_admin_user_card(user)
    kb = _user_actions_kb(user_id, user, back)

    if callback:
        await callback.message.delete()
        await bot.send_photo(
            chat_id,
            user["photo_file_id"],
            caption=caption,
            reply_markup=kb,
        )
    elif message:
        await message.answer_photo(
            user["photo_file_id"],
            caption=caption,
            reply_markup=kb,
        )


def register(dp: Dispatcher):
    @dp.message(Command("myid"))
    async def cmd_myid(message: Message):
        user = message.from_user
        admin_flag = "✅ вы админ" if is_admin(user.id) else "❌ не админ"
        await message.answer(
            f"🆔 Ваш Telegram ID: <code>{user.id}</code>\n"
            f"Username: @{user.username or '—'}\n"
            f"Статус: {admin_flag}\n\n"
            "Сравните ID с переменной ADMIN_ID в Railway Variables.",
            parse_mode="HTML",
        )

    async def _run_seed_demo(message: Message):
        _log_admin_message(message, "seed_demo")
        if not is_admin(message.from_user.id):
            await _deny_not_admin(message)
            return

        await message.answer(
            "⏳ Ładowanie profili demo… / Загрузка демо-профилей…"
        )
        try:
            result = await asyncio.to_thread(seed_all_profiles, DB_PATH)
            stats = result["stats"]
            cities_ok = sum(
                1 for c in CITIES if stats["by_city"].get(c, 0) == PERSONA_COUNT
            )

            await _log(
                message.from_user.id,
                "seed_demo",
                details=(
                    f"removed={result['removed']}, seeded={result['seeded']}, "
                    f"in_db={stats['total']}"
                ),
            )
            await message.answer(
                "✅ <b>Profili demo gotowe!</b> / Демо-профили загружены.\n\n"
                f"Usunięto starych / Удалено: {result['removed']}\n"
                f"Dodano / Создано: {result['seeded']} "
                f"(ID {TEST_ID_START}–{TEST_ID_END})\n"
                f"W bazie / В БД: <b>{stats['total']}/{stats['expected']}</b>\n"
                f"Aktywnych / Активных: {stats['active']}\n"
                f"Ze zdjęciem / С фото: {stats['with_photo']}\n"
                f"Miasta {PERSONA_COUNT}/{PERSONA_COUNT} / Города: {cities_ok}/{len(CITIES)}\n"
                f"Unikalne zdjęcia / Уник. фото: "
                f"{PERSONA_COUNT} na miasto / в городе ✅\n"
                f"photos.json: {result['photos_count']} osób\n\n"
                "🔎 <b>Przeglądaj</b> — ustaw «🔍 Szukam w» na np. "
                "<b>Warszawa</b> (⚙️ Ustawienia).\n"
                "Wiek demo: 18–22 lat (±2 od Twojego wieku).\n\n"
                "Sprawdź: /seed_status",
                parse_mode="HTML",
            )
        except FileNotFoundError as exc:
            await message.answer(
                f"❌ Brak pliku / Файл не найден:\n{exc}\n\n"
                f"Oczekiwana ścieżka / Ожидаемый путь: {SEED_DATA_DIR}/\n\n"
                "Na GitHub musi być FOLDER seed_data/ (nie pliki w korzeniu repo):\n"
                "  seed_data/genders.json\n"
                "  seed_data/photos.json\n"
                "Potem: push → redeploy Railway → /seed_demo"
            )
        except ValueError as exc:
            await message.answer(
                f"❌ Błąd danych / Ошибка данных:\n{exc}\n\n"
                "photos.json musi być z tego samego BOT_TOKEN co Railway.\n"
                "Uruchom lokalnie: python upload_test_photos.py"
            )
        except Exception as exc:
            logger.exception("seed_demo failed")
            tb = traceback.format_exc()
            tail = tb[-1500:] if len(tb) > 1500 else tb
            await message.answer(
                f"❌ Błąd / Ошибка seed_demo: {exc}\n\n"
                f"DB: {DB_PATH}\n"
                f"seed_data: {SEED_DATA_DIR}\n\n"
                f"<pre>{tail}</pre>",
                parse_mode="HTML",
            )

    @dp.message(Command("seed_demo"))
    @dp.message(Command("seed", "demo"))
    @dp.message(SeedDemoTrigger())
    async def cmd_seed_demo(message: Message):
        await _run_seed_demo(message)

    @dp.message(Command("seed_status"))
    @admin_only_command
    async def cmd_seed_status(message: Message):
        try:
            stats = count_test_users(DB_PATH)
            if stats["total"] == 0:
                await message.answer(
                    "📭 Brak profili demo w bazie (910001–910300).\n"
                    "Нет демо-профилей в БД.\n\n"
                    "Uruchom /seed_demo po deploy seed_data/ + main.py"
                )
                return

            gender_lines = ", ".join(
                f"{g}={n}" for g, n in sorted(stats["by_gender"].items())
            )
            city_lines = []
            unique_photos = stats.get("unique_photos_by_city") or {}
            for city in CITIES:
                cnt = stats["by_city"].get(city, 0)
                uniq = unique_photos.get(city, 0)
                mark = "✓" if cnt == PERSONA_COUNT else "⚠"
                photo_note = ""
                if cnt and uniq < cnt:
                    photo_note = f" ({uniq} unikalnych zdjęć ⚠)"
                elif cnt == PERSONA_COUNT and uniq == PERSONA_COUNT:
                    photo_note = " (20 unikalnych zdjęć ✓)"
                city_lines.append(f"  {mark} {city}: {cnt}{photo_note}")

            dup_cities = stats.get("cities_with_duplicate_photos") or []
            photo_warning = ""
            if dup_cities:
                photo_warning = (
                    "\n\n⚠️ Powtarzające się zdjęcia w miastach / Дубли фото: "
                    f"{', '.join(dup_cities[:5])}\n"
                    "Uruchom /seed_demo ponownie po deploy."
                )

            admin_user = await db.get_user(message.from_user.id)
            browse_hint = ""
            if admin_user:
                search = db.user_search_city(admin_user)
                in_city = stats["by_city"].get(search, 0)
                diag = await db.diagnose_candidates(message.from_user.id)
                browse_hint = (
                    f"\n\n🔍 Ваш «Szukam w»: {search or '—'}\n"
                    f"Демо в этом городе: {in_city}\n"
                    f"Кандидатов для вас: {diag.get('after_views_filter', 0)} "
                    f"(возраст {diag.get('age_range', ('?', '?'))[0]}–"
                    f"{diag.get('age_range', ('?', '?'))[1]})"
                )
                if in_city == 0 and search:
                    browse_hint += (
                        f"\n⚠️ Смените город в ⚙️ Ustawienia → 🔍 Szukam w "
                        f"(например Opole, Warszawa)."
                    )

            await message.answer(
                f"📊 <b>Статус демо-профилей</b>\n\n"
                f"В БД: <b>{stats['total']}</b> / {stats['expected']}\n"
                f"Активных: {stats['active']}\n"
                f"С photo_file_id: {stats['with_photo']}\n"
                f"Пол: {gender_lines}\n\n"
                f"<b>По городам:</b>\n"                 + "\n".join(city_lines)
                + photo_warning
                + browse_hint,
                parse_mode="HTML",
            )
        except Exception as exc:
            logger.exception("seed_status failed")
            await message.answer(f"❌ Ошибка /seed_status: {exc}\nDB: {DB_PATH}")

    @dp.message(Command("dbinfo"))
    @admin_only_command
    async def cmd_dbinfo(message: Message):
        try:
            info = await db.get_db_status()
            persist = "✅ Volume OK" if info["persistent_ok"] else "❌ БД слетит при Deploy!"
            size_kb = info["size_bytes"] // 1024
            vol = info["volume_mount"] or "brak (нет Volume!)"
            await message.answer(
                "🗄 <b>Baza danych / Database</b>\n\n"
                f"Build: <code>{BUILD_VERSION}</code>\n"
                f"Path: <code>{info['path']}</code>\n"
                f"Plik istnieje: {'tak' if info['exists'] else 'nie'} ({size_kb} KB)\n"
                f"Volume mount: <code>{vol}</code>\n"
                f"Zapis do folderu: {'tak' if info['writable'] else 'NIE'}\n"
                f"Użytkownicy (real): {info['real_users']}\n"
                f"Persistence: {persist}\n\n"
                "Jeśli «brak» — Ctrl+K → Volume → /app/data → redeploy.\n"
                "Wyłącz też lokalny start.bat (ten sam BOT_TOKEN).",
                parse_mode="HTML",
            )
        except Exception as exc:
            await message.answer(f"❌ dbinfo: {exc}\nDB_PATH={DB_PATH}")

    @dp.message(Command("admin"))
    @admin_only_command
    async def cmd_admin(message: Message, state: FSMContext):
        await state.clear()
        await _send_dashboard(message)

    @dp.message(Command("stats"))
    @admin_only
    async def cmd_stats(message: Message):
        stats = await db.get_admin_stats()
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="adm:stats")],
                [InlineKeyboardButton(text="⬅️ В панель", callback_data="adm:menu")],
            ]
        )
        await message.answer(
            _format_stats_text(stats),
            reply_markup=kb,
            parse_mode="HTML",
        )

    @dp.message(Command("ban"))
    @admin_only
    async def cmd_ban(message: Message):
        parts = message.text.split(maxsplit=2)
        if len(parts) < 2 or not parts[1].isdigit():
            await message.answer("Использование: /ban <tg_id> [причина]")
            return

        target_id = int(parts[1])
        reason = parts[2] if len(parts) > 2 else None
        user = await db.get_user(target_id)
        if not user:
            await message.answer(f"❌ Пользователь {target_id} не найден.")
            return

        await db.ban_user(target_id, reason=reason, shadow=False)
        await _log(message.from_user.id, "ban", target_id, reason)
        await message.answer(
            f"🚫 Пользователь {target_id} ({user['name']}) забанен."
            + (f"\nПричина: {reason}" if reason else "")
        )

        try:
            await message.bot.send_message(
                target_id,
                "🚫 Ваш аккаунт заблокирован администратором.",
            )
        except Exception:
            pass

    @dp.message(Command("unban"))
    @admin_only
    async def cmd_unban(message: Message):
        parts = message.text.split()
        if len(parts) < 2 or not parts[1].isdigit():
            await message.answer("Использование: /unban <tg_id>")
            return

        target_id = int(parts[1])
        user = await db.get_user(target_id)
        if not user:
            await message.answer(f"❌ Пользователь {target_id} не найден.")
            return

        await db.unban_user(target_id)
        await _log(message.from_user.id, "unban", target_id)
        await message.answer(f"✅ Пользователь {target_id} ({user['name']}) разбанен.")

    @dp.message(Command("givepremium"))
    @admin_only
    async def cmd_givepremium(message: Message, bot: Bot):
        if not PREMIUM_ENABLED:
            await message.answer("⭐ Premium wyłączone (PREMIUM_ENABLED=0).")
            return
        parts = message.text.split()
        if len(parts) < 2 or not parts[1].isdigit():
            await message.answer("Использование: /givepremium <tg_id> [dni=30]")
            return

        target_id = int(parts[1])
        days = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 30
        user = await db.get_user(target_id)
        if not user:
            await message.answer(
                f"❌ Пользователь {target_id} не найден в базе бота.\n\n"
                "Premium можно выдать только после регистрации — "
                "пусть человек напишет боту /start и пройдёт анкету.\n"
                "Потом повторите: /givepremium "
                f"{target_id} {days}"
            )
            return

        until = await db.activate_premium(target_id, days)
        await _log(message.from_user.id, "givepremium", target_id, f"{days}d until {until}")
        await message.answer(
            f"⭐ Premium выдан {target_id} ({user['name']}) на {days} дн. до {until[:10]}"
        )
        try:
            await bot.send_message(
                target_id,
                f"⭐ Admin włączył Ci Premium do <b>{until[:10]}</b>!",
                parse_mode="HTML",
            )
        except Exception:
            pass

    @dp.message(Command("user"))
    @admin_only
    async def cmd_user(message: Message):
        parts = message.text.split()
        if len(parts) < 2 or not parts[1].isdigit():
            await message.answer("Использование: /user <tg_id>")
            return

        target_id = int(parts[1])
        await _show_user_card(message.bot, message.chat.id, target_id, message=message)

    @dp.callback_query(F.data == "adm:close")
    @admin_only
    async def cb_close(callback: CallbackQuery, state: FSMContext):
        await state.clear()
        await callback.answer()
        await callback.message.delete()

    @dp.callback_query(F.data == "adm:menu")
    @admin_only
    async def cb_menu(callback: CallbackQuery, state: FSMContext):
        await state.clear()
        await callback.answer()
        pending = await db.count_pending_reports()
        text = (
            "🛡️ <b>Админ-панель CursorRandka</b>\n\n"
            f"Ожидают рассмотрения жалоб: <b>{pending}</b>\n"
            "Выберите раздел:"
        )
        kb = _dashboard_kb(pending)
        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
        else:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

    @dp.callback_query(F.data == "adm:stats")
    @admin_only
    async def cb_stats(callback: CallbackQuery):
        await callback.answer("Обновлено")
        stats = await db.get_admin_stats()
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="adm:stats")],
                [InlineKeyboardButton(text="⬅️ В панель", callback_data="adm:menu")],
            ]
        )
        text = _format_stats_text(stats)
        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
        else:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

    @dp.callback_query(F.data.startswith("adm:users:"))
    @admin_only
    async def cb_users(callback: CallbackQuery):
        await callback.answer()
        page = int(callback.data.split(":")[2])
        users, total = await db.get_users_page(page, USERS_PER_PAGE)

        if not users:
            text = "👥 Пользователи не найдены."
            kb = _back_dashboard_kb()
        else:
            lines = [f"👥 <b>Пользователи</b> (стр. {page + 1})\n"]
            buttons = []
            for u in users:
                flag = ""
                if u.get("is_banned"):
                    flag = " 🚫"
                elif u.get("is_shadow_banned"):
                    flag = " 👻"
                elif not u.get("is_active"):
                    flag = " 💤"
                lines.append(
                    f"• {u['name']}, {u['age']} · {u['city']} · ID {u['user_id']}{flag}"
                )
                buttons.append([
                    InlineKeyboardButton(
                        text=f"{u['name']} ({u['user_id']})",
                        callback_data=f"adm:user:{u['user_id']}:users:{page}",
                    )
                ])

            nav = _pagination_kb("users", page, total, USERS_PER_PAGE)
            if nav:
                buttons.append(nav)
            buttons.append([
                InlineKeyboardButton(text="⬅️ В панель", callback_data="adm:menu")
            ])
            text = "\n".join(lines)
            kb = InlineKeyboardMarkup(inline_keyboard=buttons)

        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
        else:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

    @dp.callback_query(F.data.startswith("adm:user:"))
    @admin_only
    async def cb_user_card(callback: CallbackQuery):
        await callback.answer()
        parts = callback.data.split(":")
        user_id = int(parts[2])
        back = "adm:menu"
        if len(parts) >= 5 and parts[3] == "users":
            back = f"adm:users:{parts[4]}"
        elif len(parts) >= 5 and parts[3] == "reports":
            back = f"adm:reports:{parts[4]}"
        await _show_user_card(
            callback.bot,
            callback.message.chat.id,
            user_id,
            back=back,
            callback=callback,
        )

    @dp.callback_query(F.data.startswith("adm:reports:"))
    @admin_only
    async def cb_reports(callback: CallbackQuery):
        await callback.answer()
        page = int(callback.data.split(":")[2])
        await _render_reports(callback, page)

    @dp.callback_query(F.data.startswith("adm:report:"))
    @admin_only
    async def cb_report_detail(callback: CallbackQuery):
        await callback.answer()
        parts = callback.data.split(":")
        report_id = int(parts[2])
        page = int(parts[3]) if len(parts) > 3 else 0

        report = await db.get_report(report_id)
        if not report:
            await callback.answer("Жалоба не найдена", show_alert=True)
            return

        reporter = report.get("reporter_name") or report["reporter_id"]
        reported = report.get("reported_name") or report["reported_id"]
        text = (
            f"🚨 <b>Жалоба #{report_id}</b>\n\n"
            f"👤 Жалоба на: {reported} (ID {report['reported_id']})\n"
            f"📨 От: {reporter} (ID {report['reporter_id']})\n"
            f"📋 Причина: {report['reason']}\n"
            f"📅 Дата: {report['created_at']}"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👁️ Посмотреть анкету",
                        callback_data=f"adm:user:{report['reported_id']}:reports:{page}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🚫 Забанить",
                        callback_data=f"adm:rban:{report_id}:{page}",
                    ),
                    InlineKeyboardButton(
                        text="👻 Теневой бан",
                        callback_data=f"adm:rshadow:{report_id}:{page}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="✅ Отклонить",
                        callback_data=f"adm:rdismiss:{report_id}:{page}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⬅️ К списку",
                        callback_data=f"adm:reports:{page}",
                    )
                ],
            ]
        )

        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
        else:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

    @dp.callback_query(F.data.startswith("adm:rban:"))
    @admin_only
    async def cb_report_ban(callback: CallbackQuery):
        parts = callback.data.split(":")
        report_id = int(parts[2])
        page = int(parts[3])
        report = await db.get_report(report_id)
        if not report:
            await callback.answer("Жалоба не найдена", show_alert=True)
            return

        target_id = report["reported_id"]
        reason = f"Жалоба #{report_id}: {report['reason']}"
        await db.ban_user(target_id, reason=reason, shadow=False)
        await db.update_report_status(report_id, "actioned")
        await _log(callback.from_user.id, "report_ban", target_id, reason)

        await callback.answer("Пользователь забанен")
        try:
            await callback.bot.send_message(
                target_id,
                "🚫 Ваш аккаунт заблокирован администратором.",
            )
        except Exception:
            pass

        await _render_reports(callback, page)

    @dp.callback_query(F.data.startswith("adm:rshadow:"))
    @admin_only
    async def cb_report_shadow(callback: CallbackQuery):
        parts = callback.data.split(":")
        report_id = int(parts[2])
        page = int(parts[3])
        report = await db.get_report(report_id)
        if not report:
            await callback.answer("Жалоба не найдена", show_alert=True)
            return

        target_id = report["reported_id"]
        reason = f"Жалоба #{report_id}: {report['reason']}"
        await db.ban_user(target_id, reason=reason, shadow=True)
        await db.update_report_status(report_id, "actioned")
        await _log(callback.from_user.id, "report_shadow_ban", target_id, reason)

        await callback.answer("Теневой бан применён")
        await _render_reports(callback, page)

    @dp.callback_query(F.data.startswith("adm:rdismiss:"))
    @admin_only
    async def cb_report_dismiss(callback: CallbackQuery):
        parts = callback.data.split(":")
        report_id = int(parts[2])
        page = int(parts[3])

        report = await db.get_report(report_id)
        if not report:
            await callback.answer("Жалоба не найдена", show_alert=True)
            return

        await db.update_report_status(report_id, "dismissed")
        await _log(
            callback.from_user.id,
            "report_dismiss",
            report["reported_id"],
            f"#{report_id}",
        )

        await callback.answer("Жалоба отклонена")
        await _render_reports(callback, page)

    @dp.callback_query(F.data.startswith("adm:ban:"))
    @admin_only
    async def cb_ban_user(callback: CallbackQuery):
        user_id = int(callback.data.split(":")[2])
        user = await db.get_user(user_id)
        if not user:
            await callback.answer("Не найден", show_alert=True)
            return

        await db.ban_user(user_id, shadow=False)
        await _log(callback.from_user.id, "ban", user_id)
        await callback.answer("Забанен")

        try:
            await callback.bot.send_message(
                user_id,
                "🚫 Ваш аккаунт заблокирован администратором.",
            )
        except Exception:
            pass

        await _show_user_card(
            callback.bot,
            callback.message.chat.id,
            user_id,
            callback=callback,
        )

    @dp.callback_query(F.data.startswith("adm:unban:"))
    @admin_only
    async def cb_unban_user(callback: CallbackQuery):
        user_id = int(callback.data.split(":")[2])
        user = await db.get_user(user_id)
        if not user:
            await callback.answer("Не найден", show_alert=True)
            return

        await db.unban_user(user_id)
        await _log(callback.from_user.id, "unban", user_id)
        await callback.answer("Разбанен")
        await _show_user_card(
            callback.bot,
            callback.message.chat.id,
            user_id,
            callback=callback,
        )

    @dp.callback_query(F.data.startswith("adm:shadow_on:"))
    @admin_only
    async def cb_shadow_on(callback: CallbackQuery):
        user_id = int(callback.data.split(":")[2])
        user = await db.get_user(user_id)
        if not user:
            await callback.answer("Не найден", show_alert=True)
            return

        await db.set_shadow_ban(user_id, True)
        await _log(callback.from_user.id, "shadow_ban", user_id)
        await callback.answer("Теневой бан включён")
        await _show_user_card(
            callback.bot,
            callback.message.chat.id,
            user_id,
            callback=callback,
        )

    @dp.callback_query(F.data.startswith("adm:shadow_off:"))
    @admin_only
    async def cb_shadow_off(callback: CallbackQuery):
        user_id = int(callback.data.split(":")[2])
        user = await db.get_user(user_id)
        if not user:
            await callback.answer("Не найден", show_alert=True)
            return

        await db.set_shadow_ban(user_id, False)
        await _log(callback.from_user.id, "shadow_unban", user_id)
        await callback.answer("Теневой бан снят")
        await _show_user_card(
            callback.bot,
            callback.message.chat.id,
            user_id,
            callback=callback,
        )

    @dp.callback_query(F.data.startswith("adm:delete:"))
    @admin_only
    async def cb_delete_user(callback: CallbackQuery):
        user_id = int(callback.data.split(":")[2])
        user = await db.get_user(user_id)
        if not user:
            await callback.answer("Не найден", show_alert=True)
            return

        await callback.answer()
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⚠️ Да, удалить навсегда",
                        callback_data=f"adm:delok:{user_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Отмена",
                        callback_data=f"adm:user:{user_id}",
                    )
                ],
            ]
        )
        warn = (
            f"⚠️ Удалить аккаунт <b>{user['name']}</b> "
            f"(<code>{user_id}</code>)?\nЭто действие необратимо!"
        )
        if callback.message.photo:
            await callback.message.edit_caption(
                caption=warn, reply_markup=kb, parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(warn, reply_markup=kb, parse_mode="HTML")

    @dp.callback_query(F.data.startswith("adm:delok:"))
    @admin_only
    async def cb_delete_user_confirm(callback: CallbackQuery):
        user_id = int(callback.data.split(":")[2])
        user = await db.get_user(user_id)
        if not user:
            await callback.answer("Не найден", show_alert=True)
            return

        await db.delete_user(user_id)
        await _log(callback.from_user.id, "delete_user", user_id, user.get("name"))
        await callback.answer("Удалён")

        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(
                f"🗑️ Пользователь {user_id} ({user['name']}) удалён.",
                reply_markup=_back_dashboard_kb(),
            )
        else:
            await callback.message.edit_text(
                f"🗑️ Пользователь {user_id} ({user['name']}) удалён.",
                reply_markup=_back_dashboard_kb(),
            )

    @dp.callback_query(F.data.startswith("adm:ustats:"))
    @admin_only
    async def cb_user_stats(callback: CallbackQuery):
        user_id = int(callback.data.split(":")[2])
        stats = await db.get_user_admin_stats(user_id)
        if not stats:
            await callback.answer("Не найден", show_alert=True)
            return

        user = stats["user"]
        text = (
            f"📊 <b>Статистика — {user['name']}</b>\n\n"
            f"👁️ Просмотры: {stats['views_count']}\n"
            f"❤️ Лайков получено: {stats['likes_received']}\n"
            f"💌 Лайков отправлено: {stats['likes_given']}\n"
            f"💕 Матчей: {stats['matches_count']}"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ К карточке",
                        callback_data=f"adm:user:{user_id}",
                    )
                ]
            ]
        )
        await callback.answer()
        if callback.message.photo:
            await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
        else:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

    @dp.callback_query(F.data == "adm:search")
    @admin_only
    async def cb_search_start(callback: CallbackQuery, state: FSMContext):
        await state.set_state(AdminSearch.waiting_query)
        await callback.answer()
        text = (
            "🔍 <b>Поиск пользователя</b>\n\n"
            "Отправьте tg_id, @username или имя.\n"
            "Отмена: /cancel"
        )
        kb = _back_dashboard_kb()
        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
        else:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

    @dp.message(AdminSearch.waiting_query)
    @admin_only
    async def search_query(message: Message, state: FSMContext):
        query = (message.text or "").strip()
        if query == "/cancel":
            await state.clear()
            await message.answer("❌ Поиск отменён.")
            await _send_dashboard(message)
            return
        if not query:
            await message.answer("Введите запрос для поиска.")
            return

        await state.clear()
        results = await db.search_users(query)

        if not results:
            await message.answer(
                f"❌ По запросу «{query}» ничего не найдено.",
                reply_markup=_back_dashboard_kb(),
            )
            return

        if len(results) == 1:
            await _log(message.from_user.id, "search", results[0]["user_id"], query)
            await _show_user_card(
                message.bot,
                message.chat.id,
                results[0]["user_id"],
                message=message,
            )
            return

        buttons = []
        lines = [f"🔍 Найдено: {len(results)}\n"]
        for u in results[:10]:
            uname = f"@{u['username']}" if u.get("username") else "—"
            lines.append(
                f"• {u['name']}, {u['age']} · {u['city']} · ID {u['user_id']} · {uname}"
            )
            buttons.append([
                InlineKeyboardButton(
                    text=f"{u['name']} ({u['user_id']})",
                    callback_data=f"adm:user:{u['user_id']}",
                )
            ])
        buttons.append([
            InlineKeyboardButton(text="⬅️ В панель", callback_data="adm:menu")
        ])
        await _log(message.from_user.id, "search", details=query)
        await message.answer(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )

    @dp.callback_query(F.data == "adm:broadcast")
    @admin_only
    async def cb_broadcast_start(callback: CallbackQuery, state: FSMContext):
        await state.set_state(AdminBroadcast.waiting_message)
        await callback.answer()
        text = (
            "📢 <b>Рассылка</b>\n\n"
            "Отправьте текст сообщения для всех активных пользователей.\n"
            "Отмена: /cancel"
        )
        kb = _back_dashboard_kb()
        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
        else:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

    @dp.message(AdminBroadcast.waiting_message)
    @admin_only
    async def broadcast_message(message: Message, state: FSMContext):
        text = (message.text or "").strip()
        if text == "/cancel":
            await state.clear()
            await message.answer("❌ Рассылка отменена.")
            await _send_dashboard(message)
            return
        if not text:
            await message.answer("Отправьте текстовое сообщение.")
            return

        user_ids = await db.get_broadcast_user_ids()
        count = len(user_ids)
        await state.update_data(broadcast_text=text)

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Отправить",
                        callback_data="adm:broadcast:confirm",
                    ),
                    InlineKeyboardButton(
                        text="❌ Отмена",
                        callback_data="adm:broadcast:cancel",
                    ),
                ]
            ]
        )
        preview = (
            f"📢 <b>Предпросмотр рассылки</b>\n\n"
            f"{text}\n\n"
            f"Отправить <b>{count}</b> пользователям?"
        )
        await message.answer(preview, reply_markup=kb, parse_mode="HTML")

    @dp.callback_query(F.data == "adm:broadcast:cancel")
    @admin_only
    async def cb_broadcast_cancel(callback: CallbackQuery, state: FSMContext):
        await state.clear()
        await callback.answer("Отменено")
        pending = await db.count_pending_reports()
        text = (
            "🛡️ <b>Админ-панель CursorRandka</b>\n\n"
            f"Ожидают рассмотрения жалоб: <b>{pending}</b>\n"
            "Выберите раздел:"
        )
        kb = _dashboard_kb(pending)
        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
        else:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

    @dp.callback_query(F.data == "adm:broadcast:confirm")
    @admin_only
    async def cb_broadcast_confirm(callback: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        text = data.get("broadcast_text")
        if not text:
            await callback.answer("Сообщение не найдено", show_alert=True)
            return

        await state.clear()
        await callback.answer("Рассылка запущена…")

        user_ids = await db.get_broadcast_user_ids()
        sent = 0
        failed = 0

        status_msg = await callback.message.edit_text(
            f"📢 Рассылка… 0/{len(user_ids)}",
            reply_markup=None,
        )

        for i, uid in enumerate(user_ids, 1):
            try:
                await callback.bot.send_message(uid, text)
                sent += 1
            except Exception as exc:
                failed += 1
                logger.debug("Broadcast failed for %s: %s", uid, exc)

            if i % BROADCAST_RATE == 0:
                await status_msg.edit_text(f"📢 Рассылка… {i}/{len(user_ids)}")
                await asyncio.sleep(1)

        await _log(
            callback.from_user.id,
            "broadcast",
            details=f"sent={sent}, failed={failed}",
        )

        result = (
            f"📢 <b>Рассылка завершена</b>\n\n"
            f"✅ Отправлено: {sent}\n"
            f"❌ Ошибок: {failed}"
        )
        await status_msg.edit_text(
            result,
            reply_markup=_back_dashboard_kb(),
            parse_mode="HTML",
        )
