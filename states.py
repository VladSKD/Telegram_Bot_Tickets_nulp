from aiogram.fsm.state import State, StatesGroup

class Registration(StatesGroup):
    waiting_for_last_name = State()
    waiting_for_first_name = State()
    waiting_for_institute = State()
    waiting_for_group = State()

class OrderState(StatesGroup):
    waiting_for_quantity = State()
    waiting_for_proof = State()

class AddEventState(StatesGroup):
    title = State()
    description = State()
    date_time = State()
    total_tickets = State() 
    is_free = State()       
    price = State()
    bank_link = State()
    card_number = State()
    success_message = State() 