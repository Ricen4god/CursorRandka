from aiogram import Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import db
from db import user_search_city
from keyboards import blocked_list_kb, main_menu_kb, profile_menu_kb, settings_kb
from states import ProfileEdit
from utils import format_profile


def register(dp: Dispatcher):
    @dp.message(F.text == "👤 Mój profil")
    async def my_profile(message: Message, state: FSMContext):
        await state.clear()
        user = await db.get_user(message.from_user.id)
        if not user:
            await message.answer("Najpierw zarejestruj się — /start")
            return

        status = "🟢 Aktywny" if user["is_active"] else "💤 Uśpiony"
        caption = f"{format_profile(user, own=True)}\n\nStatus: {status}"
        photo_id = (user.get("photo_file_id") or "").strip()
        if photo_id:
            await message.answer_photo(
                photo_id,
                caption=caption,
                reply_markup=profile_menu_kb(),
            )
        else:
            await message.answer(caption, reply_markup=profile_menu_kb())

    @dp.message(F.text == "✏️ Edytuj bio")
    async def edit_bio_start(message: Message, state: FSMContext):
        await state.set_state(ProfileEdit.bio)
        await message.answer(
            "Napisz nowy opis (max 500 znaków).\nAnuluj: /cancel"
        )

    @dp.message(ProfileEdit.bio)
    async def edit_bio_save(message: Message, state: FSMContext):
        if message.text == "/cancel":
            await state.clear()
            await message.answer("Anulowano", reply_markup=profile_menu_kb())
            return

        bio = (message.text or "").strip()
        if len(bio) > 500:
            await message.answer("Max 500 znaków ✏️")
            return

        await db.update_user(message.from_user.id, bio=bio)
        await state.clear()
        await message.answer("Bio zaktualizowane! ✅", reply_markup=profile_menu_kb())

    @dp.message(F.text == "📷 Zmień zdjęcie")
    async def edit_photo_start(message: Message, state: FSMContext):
        await state.set_state(ProfileEdit.photo)
        await message.answer("Wyślij nowe zdjęcie 📷\nAnuluj: /cancel")

    @dp.message(ProfileEdit.photo, F.photo)
    async def edit_photo_save(message: Message, state: FSMContext):
        photo_id = message.photo[-1].file_id
        await db.update_user(message.from_user.id, photo_file_id=photo_id)
        await state.clear()
        await message.answer("Zdjęcie zmienione! 📷✅", reply_markup=profile_menu_kb())

    @dp.message(ProfileEdit.photo)
    async def edit_photo_invalid(message: Message):
        await message.answer("Wyślij zdjęcie (nie plik) 📷")

    @dp.message(F.text == "🏙️ Zmień miasto")
    async def edit_city_start(message: Message, state: FSMContext):
        user = await db.get_user(message.from_user.id)
        if not user:
            await message.answer("Najpierw zarejestruj się — /start")
            return

        await state.update_data(edit_return="profile")
        await state.set_state(ProfileEdit.city)
        await message.answer(
            f"🏙️ Moje miasto (obecnie: {user['city']})\n\n"
            "Podaj miasto, w którym mieszkasz:\nAnuluj: /cancel"
        )

    @dp.message(F.text == "🏙️ Moje miasto")
    async def settings_home_city(message: Message, state: FSMContext):
        user = await db.get_user(message.from_user.id)
        if not user:
            await message.answer("Najpierw zarejestruj się — /start")
            return

        await state.update_data(edit_return="settings")
        await state.set_state(ProfileEdit.city)
        await message.answer(
            f"🏙️ Moje miasto (obecnie: {user['city']})\n\n"
            "Podaj miasto, w którym mieszkasz:\nAnuluj: /cancel"
        )

    @dp.message(ProfileEdit.city)
    async def edit_city_save(message: Message, state: FSMContext):
        data = await state.get_data()
        return_to = data.get("edit_return", "profile")
        return_kb = settings_kb() if return_to == "settings" else profile_menu_kb()

        if message.text == "/cancel":
            await state.clear()
            await message.answer("Anulowano", reply_markup=return_kb)
            return

        city = (message.text or "").strip()
        if len(city) < 2:
            await message.answer("Podaj prawdziwą nazwę miasta")
            return

        user = await db.get_user(message.from_user.id)
        updates = {"city": city}
        if user:
            old_search = (user.get("search_city") or user.get("city") or "").strip()
            old_city = (user.get("city") or "").strip()
            if old_search.lower() == old_city.lower():
                updates["search_city"] = city

        await db.update_user(message.from_user.id, **updates)
        await state.clear()
        await message.answer(f"Miasto zmienione na {city}! ✅", reply_markup=return_kb)

    @dp.message(F.text == "🔍 Szukam w")
    async def edit_search_city_start(message: Message, state: FSMContext):
        user = await db.get_user(message.from_user.id)
        if not user:
            await message.answer("Najpierw zarejestruj się — /start")
            return

        current = user_search_city(user)
        await state.set_state(ProfileEdit.search_city)
        await message.answer(
            f"🔍 Szukam w (obecnie: {current})\n\n"
            "W jakim mieście chcesz przeglądać profile?\n"
            "Np. mieszkasz w Opolu, a szukasz osób we Wrocławiu — wpisz «Wrocław».\n"
            "Anuluj: /cancel"
        )

    @dp.message(ProfileEdit.search_city)
    async def edit_search_city_save(message: Message, state: FSMContext):
        if message.text == "/cancel":
            await state.clear()
            await message.answer("Anulowano", reply_markup=settings_kb())
            return

        search_city = (message.text or "").strip()
        if len(search_city) < 2:
            await message.answer("Podaj prawdziwą nazwę miasta")
            return

        await db.update_user(message.from_user.id, search_city=search_city)
        await state.clear()
        await message.answer(
            f"✅ Szukasz teraz w: {search_city}",
            reply_markup=settings_kb(),
        )

    @dp.message(F.text == "📊 Statystyki")
    async def show_stats(message: Message):
        user = await db.get_user(message.from_user.id)
        if not user:
            return
        likes_today = await db.get_daily_likes_count(message.from_user.id)
        from config import DAILY_LIKE_LIMIT

        await message.answer(
            f"📊 Twoje statystyki:\n\n"
            f"👁️ Wyświetlenia profilu: {user['views_count']}\n"
            f"❤️ Otrzymane polubienia: {user['likes_received']}\n"
            f"💕 Sympatie: {len(await db.get_matches(message.from_user.id))}\n"
            f"📅 Polubienia dziś: {likes_today}/{DAILY_LIKE_LIMIT}\n"
            f"🔍 Szukam w: {user_search_city(user)}",
            reply_markup=profile_menu_kb(),
        )

    @dp.message(F.text == "🗑️ Usuń konto")
    async def delete_account_confirm(message: Message, state: FSMContext):
        await state.clear()
        await message.answer(
            "Na pewno chcesz usunąć konto?\n"
            "Wpisz «USUŃ» aby potwierdzić, lub cokolwiek innego aby anulować."
        )

    @dp.message(F.text == "USUŃ")
    async def delete_account(message: Message, state: FSMContext):
        await db.delete_user(message.from_user.id)
        await state.clear()
        await message.answer(
            "Konto usunięte. Do zobaczenia! 👋\n"
            "Wróć kiedy chcesz — wpisz /start",
            reply_markup=main_menu_kb(),
        )

    @dp.message(F.text == "⚙️ Ustawienia")
    async def settings(message: Message, state: FSMContext):
        await state.clear()
        user = await db.get_user(message.from_user.id)
        if not user:
            return
        status = "aktywny 🟢" if user["is_active"] else "uśpiony 💤"
        search = user_search_city(user)
        await message.answer(
            f"⚙️ Ustawienia\n\n"
            f"Profil: {status}\n"
            f"🏙️ Moje miasto: {user['city']}\n"
            f"🔍 Szukam w: {search}\n\n"
            f"Możesz szukać osób w dowolnym mieście — ustaw «🔍 Szukam w».",
            reply_markup=settings_kb(),
        )

    @dp.message(F.text == "☀️ Obudź profil")
    async def wake_profile(message: Message):
        await db.update_user(message.from_user.id, is_active=1)
        await message.answer(
            "Profil obudzony! ☀️ Jesteś znowu widoczny/a!",
            reply_markup=main_menu_kb(),
        )

    @dp.message(F.text == "🚫 Zablokowani")
    async def blocked_list(message: Message):
        blocked_ids = await db.get_blocked_ids(message.from_user.id)
        if not blocked_ids:
            await message.answer(
                "Nie masz zablokowanych użytkowników.",
                reply_markup=settings_kb(),
            )
            return
        await message.answer(
            "Zablokowani użytkownicy — kliknij, żeby odblokować:",
            reply_markup=blocked_list_kb(blocked_ids),
        )
