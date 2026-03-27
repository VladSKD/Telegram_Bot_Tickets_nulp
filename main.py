import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv
from database import Database
from states import OrderState, AddEventState

load_dotenv()
db = Database()
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# --- Клавіатури ---
def main_kb(user_id):
    buttons = [[KeyboardButton(text="🎟 Доступні події")]]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="⚙️ Адмін-панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Додати подію", callback_data="admin_add_event")],
        [InlineKeyboardButton(text="❌ Видалити подію", callback_data="admin_del_list")]
    ])

# --- ЛОГІКА ЮЗЕРА ---
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("Привіт! Я бот для квитків Політехніки.", reply_markup=main_kb(message.from_user.id))

@dp.message(F.text == "🎟 Доступні події")
async def list_events(message: Message):
    events = await db.get_active_events()
    if not events:
        return await message.answer("Наразі подій немає.")
    
    for ev in events:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Купити квиток", callback_data=f"buy_{ev['id']}")]
        ])
        await message.answer(f"<b>{ev['title']}</b>\n📅 {ev['date_time']}\n💰 {ev['price']} грн\n\n{ev['description']}", 
                           reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("buy_"))
async def start_buy(callback: CallbackQuery, state: FSMContext):
    await state.update_data(ev_id=int(callback.data.split("_")[1]))
    await callback.message.answer("Скільки квитків? (Напиши число)")
    await state.set_state(OrderState.waiting_for_quantity)

@dp.message(OrderState.waiting_for_quantity)
async def set_qty(message: Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Введи число!")
    await state.update_data(qty=int(message.text))
    await message.answer("Оплачуй на банку (посилання) і скинь скріншот або PDF квитанцію.")
    await state.set_state(OrderState.waiting_for_proof)

@dp.message(OrderState.waiting_for_proof, F.photo | F.document)
async def get_proof(message: Message, state: FSMContext):
    data = await state.get_data()
    f_id = message.photo[-1].file_id if message.photo else message.document.file_id
    f_type = "photo" if message.photo else "document"
    
    order_id = await db.add_order(message.from_user.id, data['ev_id'], data['qty'], f_id, f_type)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"conf_{order_id}")],
        [InlineKeyboardButton(text="❌ Відхилити", callback_data=f"reje_{order_id}")]
    ])
    
    await bot.send_message(ADMIN_ID, f"Нова оплата #{order_id}!")
    if f_type == "photo": await bot.send_photo(ADMIN_ID, f_id, reply_markup=kb)
    else: await bot.send_document(ADMIN_ID, f_id, reply_markup=kb)
    
    await message.answer("Очікуйте підтвердження адміном.")
    await state.clear()

# --- ЛОГІКА АДМІНА (ДОДАВАННЯ ПОДІЇ) ---
@dp.message(F.text == "⚙️ Адмін-панель", F.from_user.id == ADMIN_ID)
async def admin_panel(message: Message):
    await message.answer("Що бажаєте зробити?", reply_markup=admin_kb())

@dp.callback_query(F.data == "admin_add_event")
async def add_ev_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введіть назву події:")
    await state.set_state(AddEventState.title)

@dp.message(AddEventState.title)
async def add_ev_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("Введіть опис події:")
    await state.set_state(AddEventState.description)

@dp.message(AddEventState.description)
async def add_ev_desc(message: Message, state: FSMContext):
    await state.update_data(desc=message.text)
    await message.answer("Введіть дату та час (напр. 20.05 о 18:00):")
    await state.set_state(AddEventState.date_time)

@dp.message(AddEventState.date_time)
async def add_ev_dt(message: Message, state: FSMContext):
    await state.update_data(dt=message.text)
    await message.answer("Введіть ціну (тільки число):")
    await state.set_state(AddEventState.price)

@dp.message(AddEventState.price)
async def add_ev_price(message: Message, state: FSMContext):
    await state.update_data(price=int(message.text))
    await message.answer("Введіть посилання на банку Monobank:")
    await state.set_state(AddEventState.bank_link)

@dp.message(AddEventState.bank_link)
async def add_ev_final(message: Message, state: FSMContext):
    d = await state.get_data()
    await db.add_event(d['title'], d['desc'], d['dt'], d['price'], message.text)
    await message.answer("✅ Подію успішно додано!", reply_markup=main_kb(ADMIN_ID))
    await state.clear()

# --- ПІДТВЕРДЖЕННЯ ОПЛАТИ ---
@dp.callback_query(F.data.startswith("conf_") | F.data.startswith("reje_"))
async def handle_decision(callback: CallbackQuery):
    action = callback.data.split("_")[0]
    order_id = int(callback.data.split("_")[1])
    order = await db.get_order(order_id)
    
    if action == "conf":
        await db.update_order_status(order_id, "confirmed")
        await bot.send_message(order['user_id'], "✅ Твоя оплата підтверджена! Квиток чекає на тебе.")
        await callback.message.answer(f"Замовлення #{order_id} підтверджено.")
    else:
        await bot.send_message(order['user_id'], "❌ Оплата не підтверджена. Перевір дані або напиши адміну.")
    
    await callback.message.delete()

async def main():
    await db.connect()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())