from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    age = State()
    gender = State()
    looking_for = State()
    city = State()
    name = State()
    bio = State()
    photo = State()


class DirectMessage(StatesGroup):
    waiting_message = State()


class ProfileEdit(StatesGroup):
    bio = State()
    photo = State()
    city = State()
    search_city = State()


class Report(StatesGroup):
    reason = State()


class AdminBroadcast(StatesGroup):
    waiting_message = State()


class AdminSearch(StatesGroup):
    waiting_query = State()
