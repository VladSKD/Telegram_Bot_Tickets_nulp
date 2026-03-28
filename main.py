import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv
from database import Database
from states import OrderState, AddEventState, Registration
from aiohttp import web
import asyncio
import sheets

async def handle(request):
    return web.Response(text="Bot is alive!")

async def start_webhook():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 8000)))
    await site.start()

    
load_dotenv()
db = Database()
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

# --- Кнопочки головні ---
def main_kb(user_id):
    buttons = [[KeyboardButton(text="Доступні події")]]
    if user_id in ADMIN_IDS: 
        buttons.append([KeyboardButton(text="Адмін-панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Додати подію", callback_data="admin_add_event")],
        [InlineKeyboardButton(text="Видалити подію", callback_data="admin_del_list")]
    ])

# --- ЛОГІКА ЮЗЕРА ---
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await message.answer("Привіт! Давай зареєструємо тебе в системі. Введи своє Прізвище:")
    await state.set_state(Registration.waiting_for_last_name)

@dp.message(Registration.waiting_for_last_name)
async def process_last_name(message: Message, state: FSMContext):
    await state.update_data(last_name=message.text)
    await message.answer("Тепер введи своє Ім'я:")
    await state.set_state(Registration.waiting_for_first_name)

@dp.message(Registration.waiting_for_first_name)
async def process_first_name(message: Message, state: FSMContext):
    await state.update_data(first_name=message.text)
    await message.answer("З якого ти інституту? (напр. ІКНІ, ІАРХ...):")
    await state.set_state(Registration.waiting_for_institute)

@dp.message(Registration.waiting_for_institute)
async def process_institute(message: Message, state: FSMContext):
    await state.update_data(institute=message.text)
    await message.answer("Вкажи свою групу (напр. КН-201):")
    await state.set_state(Registration.waiting_for_group)

@dp.message(Registration.waiting_for_group)
async def process_group(message: Message, state: FSMContext):
    user_data = await state.get_data()
    group = message.text
    
    await db.register_full_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        first_name=user_data['first_name'],
        last_name=user_data['last_name'],
        institute=user_data['institute'],
        group=group
    )
    
    await message.answer(
        f"Реєстрація успішна, {user_data['first_name']}! Тепер ти можеш купувати квитки.",
        reply_markup=main_kb(message.from_user.id) 
    )
    await state.clear()

@dp.message(F.text == "🎟 Доступні події")
async def list_events(message: Message):
    events = await db.get_active_events()
    if not events:
        return await message.answer("Наразі подій немає.")
    
    for ev in events:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Купити квиток", callback_data=f"buy_{ev['id']}")]
        ])
        await message.answer(f"<b>{ev['title']}</b>\n {ev['date_time']}\n {ev['price']} грн\n\n{ev['description']}", 
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
    data = await state.get_data()
    
    event = await db.get_event(data['ev_id'])
    total_price = event['price'] * int(message.text)
    
    text = (f"Сума до оплати: <b>{total_price} грн</b>\n\n"
            f"🔗 Банка: {event['bank_link']}\n"
            f"💳 Картка: <code>{event['card_number']}</code>\n\n"
            f"Скинь скріншот або PDF квитанцію.")
    
    await message.answer(text, parse_mode="HTML")
    await state.set_state(OrderState.waiting_for_proof)

@dp.message(OrderState.waiting_for_proof, F.photo | F.document)
async def get_proof(message: Message, state: FSMContext):
    data = await state.get_data()
    f_id = message.photo[-1].file_id if message.photo else message.document.file_id
    f_type = "photo" if message.photo else "document"
    
    order_id = await db.add_order(message.from_user.id, data['ev_id'], data['qty'], f_id, f_type)
    
    user = await db.get_user(message.from_user.id)
    event = await db.get_event(data['ev_id'])
    username = user['username'] if user['username'] else "Без_юзернейму"
    
    await sheets.add_order_to_sheet(
        event['title'], order_id, user['last_name'], user['first_name'], 
        username, user['institute'], user['student_group'], data['qty'], "Очікує"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Підтвердити", callback_data=f"conf_{order_id}")],
        [InlineKeyboardButton(text="Відхилити", callback_data=f"reje_{order_id}")]
    ])
    
    caption = (f"Нова оплата #{order_id}!\n"
               f"{user['last_name']} {user['first_name']} (@{username})\n"
               f"{user['institute']}, {user['student_group']}\n"
               f"Кількість: {data['qty']} шт.")
               
    for admin in ADMIN_IDS:
        try:
            if f_type == "photo": await bot.send_photo(admin, f_id, caption=caption, reply_markup=kb)
            else: await bot.send_document(admin, f_id, caption=caption, reply_markup=kb)
        except Exception:
            pass
            
    await message.answer("Очікуйте підтвердження адміном.")
    await state.clear()

# --- ЛОГІКА АДМІНА (ДОДАВАННЯ ПОДІЇ) ---
@dp.message(F.text == "Адмін-панель", F.from_user.id.in_(ADMIN_IDS))
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
async def add_ev_link(message: Message, state: FSMContext):
    await state.update_data(link=message.text)
    await message.answer("Введіть номер картки (тільки цифри):")
    await state.set_state(AddEventState.card_number)

@dp.message(AddEventState.card_number)
async def add_ev_final(message: Message, state: FSMContext):
    d = await state.get_data()
    await db.add_event(d['title'], d['desc'], d['dt'], d['price'], d['link'], message.text)
    await message.answer("Подію успішно додано!", reply_markup=main_kb(message.from_user.id))
    await state.clear()

# --- ПІДТВЕРДЖЕННЯ ОПЛАТИ ---
@dp.callback_query(F.data.startswith("conf_") | F.data.startswith("reje_"))
async def handle_decision(callback: CallbackQuery):
    action = callback.data.split("_")[0]
    order_id = int(callback.data.split("_")[1])
    order = await db.get_order(order_id)
    event = await db.get_event(order['event_id'])
    
    if action == "conf":
        await db.update_order_status(order_id, "confirmed")
        await sheets.update_payment_in_sheet(event['title'], order_id, "Підтверджено")
        await bot.send_message(order['user_id'], "Твоя оплата підтверджена! Квиток чекає на тебе.")
        
        give_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Відмітити квитки як ВИДАНІ", callback_data=f"given_{order_id}")]
        ])
        await callback.message.edit_reply_markup(reply_markup=give_kb)
        await callback.answer("Оплата підтверджена!")
    else:
        await sheets.update_payment_in_sheet(event['title'], order_id, "Відхилено")
        await bot.send_message(order['user_id'], "Оплата не підтверджена. Перевір дані або напиши адміну.")
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.reply("Замовлення відхилено.")

@dp.callback_query(F.data.startswith("given_"))
async def mark_ticket_given(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    order = await db.get_order(order_id)
    event = await db.get_event(order['event_id'])
    
    await db.pool.execute("UPDATE orders SET is_ticket_given = TRUE WHERE id = $1", order_id)
    
    await sheets.update_ticket_in_sheet(event['title'], order_id, "Так")
    
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply(f"Квитки для замовлення #{order_id} успішно видані студенту!")

async def main():
    await db.connect()
    asyncio.create_task(start_webhook()) 
    await dp.start_polling(bot)
    await db.connect()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())