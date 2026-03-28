from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    waiting_for_last_name = State()
    waiting_for_first_name = State()
    waiting_for_institute = State()
    waiting_for_group = State()

# Твій старий клас для замовлення залишається
class AddEventState(StatesGroup):
    title = State()
    description = State()
    date_time = State()
    price = State()
    bank_link = State()
    card_number = State() # <-- Додали це
    

class AddEventState(StatesGroup):
    title = State()
    description = State()
    date_time = State()
    price = State()
    bank_link = State()