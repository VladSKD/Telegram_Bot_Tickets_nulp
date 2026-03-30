from aiogram.fsm.state import State, StatesGroup

class AdminBroadcast(StatesGroup):
    choose_audience = State() 
    waiting_for_message = State() 
    
class Registration(StatesGroup):
    waiting_for_last_name = State()
    waiting_for_first_name = State()
    waiting_for_institute = State()
    waiting_for_group = State()
    
class EditProfile(StatesGroup):
    edit_field = State()
    enter_value = State()
    
class OrderState(StatesGroup):
    waiting_for_quantity = State()
    waiting_for_proof = State()

class AddEventState(StatesGroup):
    title = State()
    photo = State() 
    description = State()
    date_time = State()
    location = State() 
    total_tickets = State() 
    is_free = State()
    price_type = State() 
    price = State()
    bank_link = State()
    card_number = State()
    success_message = State()
    
class AdminDelete(StatesGroup):
    confirm = State()

class AdminEdit(StatesGroup):
    select_event = State()
    select_field = State()
    enter_value = State()