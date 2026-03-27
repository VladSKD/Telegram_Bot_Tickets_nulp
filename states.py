from aiogram.fsm.state import State, StatesGroup

class OrderState(StatesGroup):
    waiting_for_quantity = State()
    waiting_for_proof = State()

class AddEventState(StatesGroup):
    title = State()
    description = State()
    date_time = State()
    price = State()
    bank_link = State()