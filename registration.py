from aiogram import Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import db
from config import MIN_AGE
from keyboards import gender_kb, looking_for_kb, main_menu_kb
from states import Registration
from utils import GENDER_MAP, LOOKING_MAP


def register(dp: Dispatcher):
    @dp.message(Registration.age)
    async def reg_age(message: Message, state: FSMContext):
        if not message.text or not message.text.isdigit():
            await message.answer("Podaj wiek liczbą, np. 22")
            return

        age = int(message.text)
        if age < MIN_AGE:
            await message.answer(f"Musisz mieć co najmniej {MIN_AGE} lat 😔")
            return
        if age > 99:
            await message.answer("Hmm, podaj prawdziwy wiek 😄")
            return

        await state.update_data(age=age)
        await state.set_state(Registration.gender)
        await message.answer("Jaka jest Twoja płeć?", reply_markup=gender_kb())

    @dp.message(Registration.gender, F.text.in_(GENDER_MAP.keys()))
    async def reg_gender(message: Message, state: FSMContext):
        await state.update_data(gender=GENDER_MAP[message.text])
        await state.set_state(Registration.looking_for)
        await message.answer("Kogo szukasz?", reply_markup=looking_for_kb())

    @dp.message(Registration.gender)
    async def reg_gender_invalid(message: Message):
        await message.answer("Wybierz płeć przyciskiem 👇", reply_markup=gender_kb())

    @dp.message(Registration.looking_for, F.text.in_(LOOKING_MAP.keys()))
    async def reg_looking_for(message: Message, state: FSMContext):
        await state.update_data(looking_for=LOOKING_MAP[message.text])
        await state.set_state(Registration.city)
        await message.answer(
            "W jakim mieście mieszkasz? 🏙️\n"
            "(Wielkość liter nie ma znaczenia — np. opole = Opole)\n"
            "(To Twoje miasto — możesz później szukać osób w innym mieście w ustawieniach)",
        )

    @dp.message(Registration.looking_for)
    async def reg_looking_for_invalid(message: Message):
        await message.answer("Wybierz opcję przyciskiem 👇", reply_markup=looking_for_kb())

    @dp.message(Registration.city)
    async def reg_city(message: Message, state: FSMContext):
        city = (message.text or "").strip()
        if len(city) < 2:
            await message.answer("Podaj prawdziwą nazwę miasta 🏙️")
            return

        await state.update_data(city=city)
        await state.set_state(Registration.name)
        await message.answer("Jak masz na imię? (lub pseudonim)")

    @dp.message(Registration.name)
    async def reg_name(message: Message, state: FSMContext):
        name = (message.text or "").strip()
        if len(name) < 2 or len(name) > 30:
            await message.answer("Imię powinno mieć 2–30 znaków ✏️")
            return

        await state.update_data(name=name)
        await state.set_state(Registration.bio)
        await message.answer(
            "Napisz coś o sobie — hobby, czego szukasz, ulubiony serial… 💬\n"
            "(Możesz też wysłać «-» jeśli nie chcesz pisać opisu)"
        )

    @dp.message(Registration.bio)
    async def reg_bio(message: Message, state: FSMContext):
        bio = (message.text or "").strip()
        if bio == "-":
            bio = ""
        elif len(bio) > 500:
            await message.answer("Opis max 500 znaków — skróć trochę 😄")
            return

        await state.update_data(bio=bio)
        await state.set_state(Registration.photo)
        await message.answer("Teraz wyślij swoje najlepsze zdjęcie! 📷")

    @dp.message(Registration.photo, F.photo)
    async def reg_photo(message: Message, state: FSMContext):
        photo_id = message.photo[-1].file_id
        data = await state.get_data()

        try:
            await db.create_user(
                {
                    "user_id": message.from_user.id,
                    "username": message.from_user.username,
                    "age": data["age"],
                    "gender": data["gender"],
                    "looking_for": data["looking_for"],
                    "city": data["city"],
                    "search_city": data["city"],
                    "name": data["name"],
                    "bio": data["bio"],
                    "photo_file_id": photo_id,
                }
            )
        except Exception as exc:
            existing = await db.get_user(message.from_user.id)
            if existing:
                await state.clear()
                await message.answer(
                    f"Masz już profil, {existing['name']}! 💕",
                    reply_markup=main_menu_kb(),
                )
                return
            await message.answer(
                "❌ Nie udało się zapisać profilu. Spróbuj ponownie za chwilę.\n"
                f"(Błąd: {type(exc).__name__})"
            )
            return

        await state.clear()

        await message.answer_photo(
            photo_id,
            caption=(
                f"🎉 Profil gotowy, {data['name']}!\n\n"
                "Możesz zacząć przeglądać osoby. W ⚙️ Ustawieniach możesz "
                "ustawić «🔍 Szukam w», żeby przeglądać profile w innym mieście! 💕"
            ),
            reply_markup=main_menu_kb(),
        )

    @dp.message(Registration.photo)
    async def reg_photo_invalid(message: Message):
        await message.answer("Wyślij zdjęcie (nie plik, tylko zdjęcie) 📷")
