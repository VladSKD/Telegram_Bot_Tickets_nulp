import asyncio
import os
import time
import re
from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv
from database import Database
from states import AdminBroadcast, AdminEdit, EditProfile, OrderState, AddEventState, Registration, AdminBlacklist
from aiohttp import web
import sheets
import json
from aiogram.types import WebAppInfo
from aiogram.types import ReplyKeyboardRemove
from states import AdminTickets
from aiohttp import web
import aiohttp 

async def handle(request):
    return web.Response(text="Bot is alive!")

async def mono_webhook(request):
    try:
        data = await request.json()
        print(f"🔥 [МОНОБАНК RAW]: {data}") # Виводить АБСОЛЮТНО ВСЕ, що прислав банк
        
        if data.get("type") == "StatementItem":
            item = data["data"]["statementItem"]
            
            # 1. ПЕРЕВІРКА СУМИ (ігноруємо списання)
            raw_amount = item.get("amount", 0)
            if raw_amount <= 0:
                print(f"➖ [МОНОБАНК] Це списання ({raw_amount/100} грн). Ігноруємо.")
                return web.Response(text="OK", status=200)
                
            incoming_amount = raw_amount / 100 
            
            # 2. Беремо унікальний ID транзакції
            tx_id = item.get("id")
            
            # 3. ПЕРЕВІРКА НА ДУБЛІКАТ (якщо раптом банк пришле двічі)
            if await db.is_transaction_processed(tx_id):
                print(f"♻️ [МОНОБАНК] Транзакція {tx_id} вже оброблена раніше. Ігнорую дубль.")
                return web.Response(text="OK", status=200)

            desc = item.get("description", "")
            comm = item.get("comment", "")
            full_text = f"{desc} {comm}".strip().upper()
            
            print(f"💰 [МОНОБАНК] ПЛЮС: {incoming_amount} грн. Текст: {full_text}")
            
            if "NULP-" in full_text:
                import re
                match = re.search(r'NULP-(\d+)', full_text)
                if match:
                    order_id = int(match.group(1))
                    print(f"🔍 [БОТ] Знайдено код NULP-{order_id}. Шукаю в базі...")
                    order = await db.get_order(order_id)
                    
                    if order and order['status'] != 'confirmed':
                        event = await db.get_event(order['event_id'])
                        
                        # ЗАПИСУЄМО ТРАНЗАКЦІЮ ЯК ОБРОБЛЕНУ
                        await db.mark_transaction_processed(tx_id)
                        
                        # Додаємо гроші
                        await db.update_order_paid_amount(order_id, incoming_amount)
                        updated_order = await db.get_order(order_id)
                        
                        # Округлюємо до 2 знаків після коми
                        total_paid = round(float(updated_order.get('paid_amount', 0.0)), 2)
                        
                        min_unit_price = extract_min_price(event['price'])
                        required_total = round(float(min_unit_price * order['ticket_count']), 2)
                        
                        print(f"📊 [БОТ] Замовлення {order_id}. Є: {total_paid}, Треба: {required_total}")
                        
                        if total_paid >= required_total:
                            print("✅ [БОТ] Сума зійшлася, видаємо квиток!")
                            await db.update_order_status(order_id, "confirmed")
                            await sheets.update_payment_in_sheet(event['title'], order_id, "Підтверджено (Авто)")
                            
                            msg = (f"✅ <b>Оплату отримано повністю!</b>\n\n"
                                   f"💰 Всього сплачено: {total_paid} грн.\n"
                                   f"📌 {event['success_message']}")
                            await bot.send_message(order['user_id'], msg, parse_mode="HTML")
                            
                            if order['file_type'] == 'organ_seats' and order['file_id']:
                                await bot.send_message(order['user_id'], "🎫 Твої офіційні квитки:")
                                seats = order['file_id'].split(',')
                                for s_info in seats:
                                    row, seat = s_info.split('-')
                                    ticket = await db.get_seat_ticket(order['event_id'], row, seat)
                                    if ticket:
                                        caption = f"🎟 Ряд {row}, Місце {seat}"
                                        if ticket['file_type'] == 'photo':
                                            await bot.send_photo(order['user_id'], ticket['file_id'], caption=caption)
                                        else:
                                            await bot.send_document(order['user_id'], ticket['file_id'], caption=caption)
                                    else:
                                        await bot.send_message(order['user_id'], f"⚠️ Квиток для Ряду {row}, Місця {seat} ще не завантажений адміном.")
                        else:
                            print("⚠️ [БОТ] НЕДОПЛАТА!")
                            # Рахуємо різницю і теж округлюємо до 2 знаків
                            difference = round(required_total - total_paid, 2)
                            msg = (f"⚠️ <b>Недостатня сума для квитків!</b>\n\n"
                                   f"📥 Отримано зараз: {incoming_amount} грн\n"
                                   f"💰 Всього сплачено: {total_paid} грн\n"
                                   f"❌ <b>Потрібно ще: {difference} грн</b>\n\n"
                                   f"Будь ласка, доплати різницю на ту саму Банку, <u>обов'язково</u> вказавши той самий код: <code>NULP-{order_id}</code>")
                            await bot.send_message(order['user_id'], msg, parse_mode="HTML")
                            await sheets.update_payment_in_sheet(event['title'], order_id, f"Недоплата (є {total_paid} з {required_total})")

    except Exception as e:
        print(f"❌ [ПОМИЛКА]: {e}")
    return web.Response(text="OK", status=200)



# --- РЕЄСТРАЦІЯ ВЕБХУКУ В МОНОБАНКУ ---
async def setup_mono_webhook():
    mono_token = os.getenv("MONO_TOKEN")
    web_url = os.getenv("WEB_APP_URL")
    if mono_token and web_url:
        webhook_endpoint = f"{web_url.rstrip('/')}/mono"
        headers = {"X-Token": mono_token}
        payload = {"webHookUrl": webhook_endpoint}
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post("https://api.monobank.ua/personal/webhook", headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        print(f"✅ Вебхук Монобанку успішно встановлено на {webhook_endpoint}")
                    else:
                        print(f"⚠️ Помилка встановлення вебхуку: {await resp.text()}")
            except Exception as e:
                print(f"⚠️ Не вдалося підключитися до Монобанку: {e}")

async def start_webhook():
    app = web.Application()
    app.router.add_get("/", handle)
    app.router.add_post("/mono", mono_webhook) # Додали слухача для Моно
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 8000)))
    await site.start()
    
    # Реєструємо вебхук у Монобанку при запуску
    await setup_mono_webhook()


def extract_min_price(price_str):
    """Витягує перше число з рядка. Якщо там просто '150', поверне 150."""
    price_str = str(price_str).strip()
    if price_str.isdigit():
        return int(price_str)
    match = re.search(r'\d+', price_str)
    return int(match.group()) if match else 0

load_dotenv()
db = Database()
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

# --- MIDDLEWARE ДЛЯ ЧОРНОГО СПИСКУ ---
class BlacklistMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = event.from_user
        if user and user.username:
            if await db.is_blacklisted(user.username):
                if isinstance(event, Message):
                    await event.answer("🚫 Ви заблоковані адміністрацією і не можете користуватися ботом.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("🚫 Ви заблоковані адміністрацією.", show_alert=True)
                return
        return await handler(event, data)

dp.message.middleware(BlacklistMiddleware())
dp.callback_query.middleware(BlacklistMiddleware())
# ------------------------------------

def main_kb(user_id):
    buttons = [
        [KeyboardButton(text="Доступні події"), KeyboardButton(text="Мій профіль")]
    ]
    if user_id in ADMIN_IDS: 
        buttons.append([KeyboardButton(text="Адмін-панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Додати подію", callback_data="admin_add_event")],
        [InlineKeyboardButton(text="Редагувати подію", callback_data="admin_edit_list")],
        [InlineKeyboardButton(text="Видалити подію", callback_data="admin_del_list")],
        [InlineKeyboardButton(text="Розсилка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="⚫ Чорний список", callback_data="admin_blacklist")],
        [InlineKeyboardButton(text="📎 Завантажити квитки (1шт + підпис)", callback_data="admin_upload_tickets")],
        [InlineKeyboardButton(text="📂 МАСОВЕ завантаження ПДФ", callback_data="admin_mass_upload")],
        [InlineKeyboardButton(text="🗺 Керування залом (Адмін)", callback_data="admin_manage_hall")]
    ])

# --- ЛОГІКА ЮЗЕРА ---
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await message.answer(
        "👋 <b>Привіт!</b> Раді бачити тебе в системі.\n\n"
        "Давай швиденько зареєструємось, щоб ти міг бронювати квитки на івенти.\n\n"
        "✍️ <b>Введи своє Прізвище:</b>",
        parse_mode="HTML"
    )
    await state.set_state(Registration.waiting_for_last_name)

@dp.message(Registration.waiting_for_last_name)
async def process_last_name(message: Message, state: FSMContext):
    await state.update_data(last_name=message.text)
    await message.answer("👤 <b>Тепер введи своє Ім'я:</b>", parse_mode="HTML")
    await state.set_state(Registration.waiting_for_first_name)

@dp.message(Registration.waiting_for_first_name)
async def process_first_name(message: Message, state: FSMContext):
    await state.update_data(first_name=message.text)
    await message.answer("🏛 <b>З якого ти інституту?</b>\n<i>(напр. ІКНІ, ІАРХ тощо):</i>", parse_mode="HTML")
    await state.set_state(Registration.waiting_for_institute)

@dp.message(Registration.waiting_for_institute)
async def process_institute(message: Message, state: FSMContext):
    await state.update_data(institute=message.text)
    await message.answer("🎓 <b>Вкажи свою групу:</b>\n<i>(напр. КН-201):</i>", parse_mode="HTML")
    await state.set_state(Registration.waiting_for_group)

@dp.message(Registration.waiting_for_group)
async def process_group(message: Message, state: FSMContext):
    user_data = await state.get_data()
    group = message.text
    
    # 1. Зберігаємо в нашу основну базу даних (PostgreSQL)
    await db.register_full_user(
        tg_id=message.from_user.id, 
        username=message.from_user.username,
        first_name=user_data['first_name'], 
        last_name=user_data['last_name'],
        institute=user_data['institute'], 
        group=group
    )
    
    # 2. ДУБЛЮЄМО В ГУГЛ ТАБЛИЦЮ (прямо за твоїм посиланням)
    # 2. СИНХРОНІЗАЦІЯ З РЕЄСТРОМ (Upsert)
    asyncio.create_task(sheets.upsert_user_in_registry(
        user_data['last_name'], 
        user_data['first_name'], 
        message.from_user.username,
        user_data['institute'], 
        group
    ))
    
    await message.answer(
        f"✅ <b>Реєстрація успішна, {user_data['first_name']}!</b>\n\n"
        "Тепер тобі доступний перегляд та купівля квитків. Обирай подію в меню нижче 👇", 
        reply_markup=main_kb(message.from_user.id),
        parse_mode="HTML"
    )
    await state.clear()

@dp.message(F.text == "Мій профіль")
async def show_profile(message: Message, state: FSMContext):
    await state.clear() 
    user = await db.get_user(message.from_user.id)
    if not user: return await message.answer("❌ Профіль не знайдено. Напиши /start для реєстрації.")

    profile_text = (
        f"👤 <b>ТВІЙ ПРОФІЛЬ</b>\n\n"
        f"📝 <b>Прізвище:</b> {user['last_name']}\n"
        f"📝 <b>Ім'я:</b> {user['first_name']}\n"
        f"🏛 <b>Інститут:</b> {user['institute']}\n"
        f"🎓 <b>Група:</b> {user['student_group']}\n\n"
        f"<i>Якщо помітив помилку, ти можеш змінити свої дані натиснувши кнопку нижче 👇</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Змінити Прізвище", callback_data="prof_edit_last_name")],
        [InlineKeyboardButton(text="✏️ Змінити Ім'я", callback_data="prof_edit_first_name")],
        [InlineKeyboardButton(text="✏️ Змінити Інститут", callback_data="prof_edit_institute")],
        [InlineKeyboardButton(text="✏️ Змінити Групу", callback_data="prof_edit_group")]
    ])
    await message.answer(profile_text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("prof_edit_"))
async def ask_new_profile_value(callback: CallbackQuery, state: FSMContext):
    field_to_edit = callback.data.replace("prof_edit_", "")
    await state.update_data(edit_field=field_to_edit)
    
    prompts = {
        "last_name": "нове Прізвище", "first_name": "нове Ім'я",
        "institute": "свій Інститут (напр. ІКНІ, ІАРХ)", "group": "свою Групу (напр. КН-201)"
    }
    
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(f"✍️ <b>Введи {prompts.get(field_to_edit, 'нове значення')}:</b>", parse_mode="HTML")
    await state.set_state(EditProfile.enter_value)
    await callback.answer()

@dp.message(EditProfile.enter_value)
async def save_new_profile_value(message: Message, state: FSMContext):
    if message.text in ["Доступні події", "Мій профіль", "Адмін-панель"]:
        await state.clear()
        if message.text == "Доступні події": return await list_events(message)
        elif message.text == "Мій профіль": return await show_profile(message, state)
        else: return await admin_panel(message)

    data = await state.get_data()
    await db.update_user_field(message.from_user.id, data['edit_field'], message.text)
    

    user = await db.get_user(message.from_user.id)
    if user:
        asyncio.create_task(sheets.upsert_user_in_registry(
            user['last_name'], 
            user['first_name'], 
            user['username'],
            user['institute'], 
            user['student_group']
        ))

    
    await message.answer("✅ <b>Дані успішно оновлено!</b>", parse_mode="HTML")
    await state.clear()
    await show_profile(message, state)

@dp.message(F.text == "Доступні події")
async def list_events(message: Message):
    events = await db.get_active_events()
    if not events: return await message.answer("📭 <b>Наразі активних подій немає.</b>", parse_mode="HTML")
    
    for ev in events:
        rem = ev['remaining_tickets']
        if rem <= 0:
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Квитків немає", callback_data="sold_out")]])
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎟 Купити квиток", callback_data=f"buy_{ev['id']}")]])
        
        type_str = "<i>Безкоштовно</i>" if ev['is_free'] else f"<b>{ev['price']}</b>"
        
        event_text = (
            f"🎉 <b>{ev['title']}</b>\n\n"
            f"📅 <b>Коли:</b> {ev['date_time']}\n"
            f"📍 <b>Локація:</b> {ev['location']}\n"
            f"💵 <b>Вартість:</b> {type_str}\n"
            f"📊 <b>Залишилось квитків:</b> {rem} з {ev['total_tickets']}\n\n"
            f"📝 <b>Опис:</b>\n<i>{ev['description']}</i>"
        )
        
        if ev.get('photo_id'):
            await message.answer_photo(ev['photo_id'], caption=event_text, reply_markup=kb, parse_mode="HTML")
        else:
            await message.answer(event_text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "sold_out")
async def handle_sold_out(callback: CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("🥺 На жаль, усі квитки на цю подію вже розібрали!", parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_"))
async def start_buy(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    event_id = int(callback.data.split("_")[1])
    await state.update_data(ev_id=event_id)
    event = await db.get_event(event_id)
    
    if event.get('venue_type') == 'organ_hall':
        occ_list = await db.get_occupied_seats(event_id)
        occ_str = ",".join(occ_list)
        
        web_app_url = f"https://telegram-bot-tickets-nulp.vercel.app/?occ={occ_str}&t={int(time.time())}"
        
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🗺 Відкрити схему залу", web_app=WebAppInfo(url=web_app_url))]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await callback.message.answer("Обери бажані місця на інтерактивній схемі залу (натисни кнопку внизу екрану 👇)", reply_markup=kb)
    else:
        await callback.message.answer("🛒 <b>Скільки квитків беремо?</b>\n<i>Напиши просто число (наприклад: 1, 2):</i>", parse_mode="HTML")
        await state.set_state(OrderState.waiting_for_quantity)

# --- ФІНАЛІЗАЦІЯ ЗАМОВЛЕННЯ (Спільна функція) ---
async def process_order_payment(message: Message, state: FSMContext, is_organ=False):
    data = await state.get_data()
    qty = data['qty']
    event_id = data['ev_id']
    friends = data.get('friends', [])
    
    event = await db.get_event(event_id)
    user = await db.get_user(message.from_user.id)
    username = user['username'] if user['username'] else "Без_юзернейму"
    
    # Готуємо рядок з місцями для бази даних
    f_id = None
    f_type = None
    if is_organ:
        seats = data['selected_seats']
        f_id = ",".join([f"{s['row']}-{s['seat']}" for s in seats])
        f_type = "organ_seats"

    if is_organ or event['is_free']:
        # Записуємо в БД для безкоштовних/органного залу
        order_id = await db.add_order(message.from_user.id, event_id, qty, f_id, f_type)
        await db.update_order_status(order_id, "confirmed")
        
        if is_organ:
            buyer_seat = seats[0]
            await sheets.add_order_to_sheet(event['title'], order_id, user['last_name'], user['first_name'], username, user['institute'], user['student_group'], 1, f"Підтверджено (Р{buyer_seat['row']}М{buyer_seat['seat']})")
            
            for i, friend_info in enumerate(friends):
                f_seat = seats[i+1]
                await sheets.add_order_to_sheet(event['title'], order_id, "Друг", friend_info, "-", "Гість", f"від @{username}", 1, f"Підтверджено (Р{f_seat['row']}М{f_seat['seat']})")
            
            formatted_seats = "\n".join([f"📍 Ряд: <b>{s['row']}</b>, Місце: <b>{s['seat']}</b>" for s in seats])
            await message.answer(f"✅ <b>Бронювання успішне!</b>\n\n🎟 <b>Твої місця ({qty} шт.):</b>\n{formatted_seats}\n\n📌 {event['success_message']}", parse_mode="HTML")
            
            await message.answer("Ось твої офіційні квитки для входу:")
            for s in seats:
                ticket_data = await db.get_seat_ticket(event_id, s['row'], s['seat'])
                if ticket_data:
                    caption = f"🎟 Ряд {s['row']}, Місце {s['seat']}"
                    if ticket_data['file_type'] == 'photo':
                        await bot.send_photo(message.chat.id, ticket_data['file_id'], caption=caption)
                    else:
                        await bot.send_document(message.chat.id, ticket_data['file_id'], caption=caption)
                else:
                    await message.answer(f"⚠️ Квиток для Ряду {s['row']}, Місця {s['seat']} ще генерується. Організатори надішлють його згодом.")
        else:
            await sheets.add_order_to_sheet(event['title'], order_id, user['last_name'], user['first_name'], username, user['institute'], user['student_group'], 1, "Безкоштовно")
            for friend_info in friends:
                await sheets.add_order_to_sheet(event['title'], order_id, "Друг", friend_info, "-", "Гість", f"від @{username}", 1, "Безкоштовно")
                
            await message.answer(f"✅ <b>Бронювання успішне!</b>\n\n🎟 <b>Кількість:</b> {qty} шт.\n\n📌 {event['success_message']}", parse_mode="HTML")
            
        await state.clear()
    else:
        order_id = await db.add_order(message.from_user.id, event_id, qty, f_id, f_type)
        await db.update_order_status(order_id, "pending")
        
        # 👇👇👇 ОСЬ ЦІ 4 РЯДКИ ТРЕБА ДОДАТИ 👇👇👇
        status_str = "Очікує оплати"
        await sheets.add_order_to_sheet(event['title'], order_id, user['last_name'], user['first_name'], username, user['institute'], user['student_group'], 1, status_str)
        for friend_info in friends:
            await sheets.add_order_to_sheet(event['title'], order_id, "Друг", friend_info, "-", "Гість", f"від @{username}", 1, status_str)
        # 👆👆👆 ============================== 👆👆👆
        
        price_str = str(event['price']).strip()
        min_unit_price = extract_min_price(price_str)
        total_required = min_unit_price * qty
        
        payment_code = f"NULP-{order_id}"
        
        if price_str.isdigit():
            price_display = f"💳 <b>Сума до оплати:</b> {total_required} грн (по {price_str} грн/шт)"
        else:
            price_display = (f"💵 <b>Умова:</b> {price_str} за один квиток.\n"
                             f"📈 <b>Разом за {qty} шт:</b> від {total_required} грн")

        text = (
            f"📝 <b>Твоє замовлення:</b> {qty} шт.\n"
            f"{price_display}\n\n"
            f"💳 <b>Реквізити:</b>\n"
            f"🔗 Банка: {event['bank_link']}\n"
            f"🏦 Картка: <code>{event['card_number']}</code>\n\n"
            f"⚠️ <b>ОБОВ'ЯЗКОВО вкажи код у коментарі:</b>\n"
            f"👉 <code>{payment_code}</code> 👈\n\n"
            f"<i>Бот автоматично підсумує всі твої платежі з цим кодом.</i>"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📸 Я забув вказати код (надіслати скрін)", callback_data=f"forgot_{order_id}")]
        ])
        
        await message.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
        await state.clear()





@dp.message(F.web_app_data)
async def handle_web_app_data(message: Message, state: FSMContext):
    await message.answer("🔄 Обробляю твій вибір...", reply_markup=main_kb(message.from_user.id))
    raw_data = message.web_app_data.data
    
    # 🌟 ЯКЩО ЦЕ АДМІН ВІДПРАВИВ ЗАПИТ НА ІНФУ ПРО МІСЦЕ:
    if raw_data.startswith("admin_seat|"):
        _, ev_id_str, seat_str = raw_data.split("|")
        row, seat = seat_str.split('-')
        
        info = await db.get_seat_info(int(ev_id_str), row, seat)
        if not info:
            return await message.answer(f"ℹ️ Місце {row}-{seat} не знайдено або вже вільне.")
            
        event = await db.get_event(int(ev_id_str))
        username = f"@{info['username']}" if info['username'] else "Без юзернейму"
        
        text = (
            f"🛠 <b>Деталі квитка</b>\n\n"
            f"🎫 <b>Подія:</b> {event['title']}\n"
            f"📍 <b>Місце:</b> Ряд {row}, Місце {seat}\n\n"
            f"👤 <b>Покупець:</b> {info['first_name']} {info['last_name']} ({username})\n"
            f"🎓 <b>Група:</b> {info['institute']}, {info['student_group']}\n"
            f"📦 <b>ID Замовлення:</b> #{info['order_id']}"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Скасувати цей квиток", callback_data=f"adm_cancel_{info['order_id']}_{row}_{seat}")]
        ])
        
        return await message.answer(text, reply_markup=kb, parse_mode="HTML")

    # 🌟 ЯКЩО ЦЕ ЗВИЧАЙНИЙ ПОКУПЕЦЬ КУПУЄ МІСЦЯ:
    if not raw_data or raw_data == "null":
        return await message.answer(f"⚠️ Помилка: Дані не отримано.\n<i>(Debug: <code>{raw_data}</code>)</i>", parse_mode="HTML")

    # ... ДАЛІ ТВІЙ СТАРИЙ КОД З try ... except ...

    try:
        # 👈 Розпаковуємо наш новий формат "Ряд-Місце|Ряд-Місце"
        selected_seats = []
        seat_items = raw_data.split('|')
        
        for item in seat_items:
            row_part, seat_part = item.split('-')
            selected_seats.append({
                'id': item, # Для сумісності
                'row': row_part,
                'seat': int(seat_part)
            })
            
        if not selected_seats:
            return await message.answer("⚠️ Список місць порожній.")
            
    except Exception as e:
        return await message.answer(f"⚠️ Помилка обробки: {e}\n<i>(Отримано: <code>{raw_data}</code>)</i>", parse_mode="HTML")

    qty = len(selected_seats)
    
    # Далі логіка без змін
    if qty == 1:
        await state.update_data(qty=qty, selected_seats=selected_seats)
        await process_order_payment(message, state, is_organ=True)
    else:
        await state.update_data(qty=qty, selected_seats=selected_seats, total_friends=qty-1, current_friend=1, friends=[])
        await message.answer(
            f"👥 Оскільки ти береш {qty} квитків, нам потрібні дані твоїх друзів.\n\n"
            f"Введи Прізвище, Ім'я та @тег для <b>1-го друга</b>:", 
            parse_mode="HTML"
        )
        await state.set_state(OrderState.waiting_for_friend_data)


@dp.message(OrderState.waiting_for_quantity)
async def set_qty(message: Message, state: FSMContext):
    if message.text in ["Доступні події", "Адмін-панель"]:
        await state.clear()
        if message.text == "Доступні події": return await list_events(message)
        else: return await admin_panel(message)

    if not message.text.isdigit() or int(message.text) <= 0: 
        return await message.answer("⚠️ <b>Помилка:</b> Будь ласка, введи коректне число квитків (більше нуля)!", parse_mode="HTML")
        
    qty = int(message.text)
    data = await state.get_data()
    event = await db.get_event(data['ev_id'])
    
    if qty > event['remaining_tickets']:
        return await message.answer(f"❌ Ти не можеш взяти стільки. Залишилось всього <b>{event['remaining_tickets']}</b> квитків.", parse_mode="HTML")
    
    if qty == 1:
        await state.update_data(qty=qty)
        await process_order_payment(message, state)
    else:
        await state.update_data(qty=qty, total_friends=qty-1, current_friend=1, friends=[])
        await message.answer(
            f"👥 Оскільки ти береш {qty} квитків, нам потрібні дані твоїх друзів.\n\n"
            f"Введи Прізвище, Ім'я та @тег для <b>1-го друга</b> (наприклад: <i>Шевченко Тарас @taras123</i>):", 
            parse_mode="HTML"
        )
        await state.set_state(OrderState.waiting_for_friend_data)


@dp.message(OrderState.waiting_for_friend_data)
async def process_friend_data(message: Message, state: FSMContext):
    data = await state.get_data()
    friends = data.get('friends', [])
    friends.append(message.text)
    
    current = data['current_friend']
    total = data['total_friends']
    
    if current < total:
        await state.update_data(friends=friends, current_friend=current+1)
        await message.answer(f"Введи дані для <b>{current+1}-го друга</b>:", parse_mode="HTML")
    else:
        await state.update_data(friends=friends)
        is_organ = 'selected_seats' in data
        await process_order_payment(message, state, is_organ)


@dp.callback_query(F.data.startswith("forgot_"))
async def forgot_code_handler(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split("_")[1])
    await state.update_data(manual_order_id=order_id)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Нічого страшного! Надішли сюди скріншот або PDF-квитанцію, і адмін підтвердить оплату вручну 👇")
    await state.set_state(OrderState.waiting_for_proof)
    
@dp.message(OrderState.waiting_for_proof, F.photo | F.document)
async def get_proof(message: Message, state: FSMContext):
    data = await state.get_data()
    f_id = message.photo[-1].file_id if message.photo else message.document.file_id
    f_type = "photo" if message.photo else "document"
    
    order_id = data.get('manual_order_id')
    if not order_id:
        return await message.answer("⚠️ Помилка: замовлення не знайдено. Спробуй ще раз.")
        
    order = await db.get_order(order_id)
    event = await db.get_event(order['event_id'])
    user = await db.get_user(message.from_user.id)
    username = user['username'] if user['username'] else "Без_юзернейму"
    
    # 1. Беремо кількість квитків із бази даних
    qty = order['ticket_count']

    # Оновлюємо замовлення файлом
    await db.attach_proof_to_order(order_id, f_id, f_type)
    
    req_conf = event.get('requires_confirmation', True)
    status_str = "Очікує (Скріншот)" if req_conf else "Підтверджено"
    
    # 2. ОНОВЛЮЄМО статус у таблиці (замість створення нових рядків)
    await sheets.update_payment_in_sheet(event['title'], order_id, status_str)
    
    caption = (
        f"🚨 Нова оплата #{order_id}!\n\n"
        f"👤 Студент: {user['last_name']} {user['first_name']} (@{username})\n"
        f"📚 Група: {user['institute']}, {user['student_group']}\n"
        f"🎟 Кількість квитків: {qty} шт."
    )
               
    if req_conf:
        # ЗВИЧАЙНИЙ РЕЖИМ (з кнопками)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Підтвердити", callback_data=f"conf_{order_id}")],
            [InlineKeyboardButton(text="Відхилити", callback_data=f"reje_{order_id}")]
        ])
        for admin in ADMIN_IDS:
            try:
                if f_type == "photo": await bot.send_photo(admin, f_id, caption=caption, reply_markup=kb)
                else: await bot.send_document(admin, f_id, caption=caption, reply_markup=kb)
            except Exception:
                pass
        await message.answer("⏳ <b>Квитанцію прийнято!</b>\nОчікуй на підтвердження адміністратором. Ми надішлемо тобі повідомлення.", parse_mode="HTML")
    else:
        # РЕЖИМ АВТОПІДТВЕРДЖЕННЯ
        caption += "\n\n✅ <i>(Автоматично підтверджено системою)</i>"
        for admin in ADMIN_IDS:
            try:
                if f_type == "photo": await bot.send_photo(admin, f_id, caption=caption)
                else: await bot.send_document(admin, f_id, caption=caption)
            except Exception:
                pass
                
        await db.update_order_status(order_id, "confirmed")
        await message.answer(f"✅ <b>Квитанцію прийнято та підтверджено!</b>\n\n{event['success_message']}", parse_mode="HTML")
        
    await state.clear()

@dp.message(OrderState.waiting_for_proof)
async def wrong_proof_format(message: Message, state: FSMContext):
    if message.text in ["Доступні події", "Адмін-панель"]:
        await state.clear()
        if message.text == "Доступні події": return await list_events(message)
        else: return await admin_panel(message)
        
    await message.answer("❌ <b>Неправильний формат!</b>\nБудь ласка, надішли скріншот (фото) або PDF-файл квитанції.", parse_mode="HTML")


# --- ЛОГІКА АДМІНА ---
@dp.message(F.text == "Адмін-панель", F.from_user.id.in_(ADMIN_IDS))
async def admin_panel(message: Message):
    await message.answer("Що бажаєте зробити?", reply_markup=admin_kb())

# (ТУТ ЗАЛИШАЄТЬСЯ ВСЯ ВАША СТАРА ЛОГІКА СТВОРЕННЯ/ВИДАЛЕННЯ ПОДІЙ)
@dp.callback_query(F.data == "admin_add_event")
async def add_ev_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введіть назву події:")
    await state.set_state(AddEventState.title)

@dp.message(AddEventState.title)
async def add_ev_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("Прикріпіть афішу до події (надішліть фото):")
    await state.set_state(AddEventState.photo)

@dp.message(AddEventState.photo, F.photo)
async def add_ev_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    await message.answer("Введіть опис події:")
    await state.set_state(AddEventState.description)

@dp.message(AddEventState.photo)
async def add_ev_photo_wrong(message: Message):
    await message.answer("❌ Будь ласка, надішліть саме фотографію (афішу):")

@dp.message(AddEventState.description)
async def add_ev_desc(message: Message, state: FSMContext):
    await state.update_data(desc=message.text)
    await message.answer("Введіть дату та час (напр. 20.05 о 18:00):")
    await state.set_state(AddEventState.date_time)

@dp.message(AddEventState.date_time)
async def add_ev_dt(message: Message, state: FSMContext):
    await state.update_data(dt=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎹 Органний зал (з вибором місць)", callback_data="venue_organ_hall")],
        [InlineKeyboardButton(text="🏢 Інше / Немає значення", callback_data="venue_other")]
    ])
    await message.answer("Обери тип локації:", reply_markup=kb)
    await state.set_state(AddEventState.venue_type)

@dp.callback_query(AddEventState.venue_type, F.data.startswith("venue_"))
async def add_ev_venue_type(callback: CallbackQuery, state: FSMContext):
    venue_type = callback.data.replace("venue_", "") 
    await state.update_data(venue_type=venue_type)
    await callback.message.edit_text("Тепер введи точне місце проведення текстом:")
    await state.set_state(AddEventState.location)

@dp.message(AddEventState.location)
async def add_ev_location(message: Message, state: FSMContext):
    await state.update_data(location=message.text)
    await message.answer("Введіть загальну кількість квитків на подію (тільки число):")
    await state.set_state(AddEventState.total_tickets)

@dp.message(AddEventState.total_tickets)
async def add_ev_tickets(message: Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) <= 0: 
        return await message.answer("Введіть ціле додатнє число (більше нуля)!")
    await state.update_data(total_tickets=int(message.text))
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Безкоштовна", callback_data="ev_free")],
        [InlineKeyboardButton(text="Платна", callback_data="ev_paid")]
    ])
    await message.answer("Яка це подія?", reply_markup=kb)
    await state.set_state(AddEventState.is_free)

@dp.callback_query(AddEventState.is_free, F.data.in_(["ev_free", "ev_paid"]))
async def set_ev_type(callback: CallbackQuery, state: FSMContext):
    is_free = (callback.data == "ev_free")
    await state.update_data(is_free=is_free)
    
    if is_free:
        await state.update_data(is_fixed_price=True, price="0", link="", card="", requires_confirmation=False)
        await state.update_data(is_fixed_price=True, price="0", link="", card="")
        await callback.message.answer("Введіть фінальне повідомлення (напр. 'Забирай квиток в 218 кабінеті'):")
        await state.set_state(AddEventState.success_message)
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Фіксована ціна", callback_data="price_fixed")],
            [InlineKeyboardButton(text="Гнучка ціна (текст)", callback_data="price_flex")]
        ])
        await callback.message.answer("Який формат ціни буде у події?", reply_markup=kb)
        await state.set_state(AddEventState.price_type)
    await callback.answer()

@dp.callback_query(AddEventState.price_type, F.data.in_(["price_fixed", "price_flex"]))
async def set_price_type(callback: CallbackQuery, state: FSMContext):
    is_fixed = (callback.data == "price_fixed")
    await state.update_data(is_fixed_price=is_fixed)
    if is_fixed: await callback.message.answer("Введіть ціну за 1 квиток (ТІЛЬКИ ЧИСЛО, напр. 150):")
    else: await callback.message.answer("Введіть текст ціни (напр. 'від 100 грн' або 'донат від 50 грн'):")
    await state.set_state(AddEventState.price)
    await callback.answer()

@dp.message(AddEventState.price)
async def add_ev_price(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get('is_fixed_price') and not message.text.isdigit():
        return await message.answer("Помилка! Для фіксованої ціни введіть ТІЛЬКИ ЧИСЛО:")
    await state.update_data(price=message.text)
    await message.answer("Введіть посилання на банку Monobank:")
    await state.set_state(AddEventState.bank_link)

@dp.message(AddEventState.bank_link)
async def add_ev_link(message: Message, state: FSMContext):
    await state.update_data(link=message.text)
    await message.answer("Введіть номер картки (тільки цифри):")
    await state.set_state(AddEventState.card_number)

@dp.message(AddEventState.card_number)
async def add_ev_card(message: Message, state: FSMContext):
    await state.update_data(card=message.text)
    await message.answer("Введіть фінальне повідомлення після підтвердження оплати:")
    await state.set_state(AddEventState.success_message)



@dp.message(AddEventState.success_message)
async def add_ev_final(message: Message, state: FSMContext):
    d = await state.get_data()
    await db.add_event(
        d['title'], d['desc'], d['photo_id'], d['dt'], d['venue_type'], 
        d['location'], d['total_tickets'], d['is_free'], d['price'], 
        d.get('link', ''), d.get('card', ''), message.text, 
    )
    await message.answer("✅ Подію успішно додано!", reply_markup=main_kb(message.from_user.id))
    await state.clear()
    
@dp.callback_query(F.data == "admin_del_list")
async def show_delete_list(callback: CallbackQuery):
    events = await db.get_active_events()
    if not events: return await callback.message.answer("Немає активних подій для видалення.")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{ev['title']}", callback_data=f"del_{ev['id']}")] for ev in events
    ])
    await callback.message.answer("Оберіть подію, яку хочете ВИДАЛИТИ:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("del_"))
async def confirm_delete(callback: CallbackQuery):
    event_id = int(callback.data.split("_")[1])
    await db.delete_event(event_id)
    await callback.message.edit_text("Подію успішно видалено! (Вона більше не показуватиметься студентам).")

@dp.callback_query(F.data == "admin_edit_list")
async def show_edit_list(callback: CallbackQuery, state: FSMContext):
    events = await db.get_active_events()
    if not events: return await callback.message.answer("Немає активних подій для редагування.")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{ev['title']}", callback_data=f"edit_{ev['id']}")] for ev in events])
    await callback.message.answer("Оберіть подію для РЕДАГУВАННЯ:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("edit_"))
async def select_field_to_edit(callback: CallbackQuery, state: FSMContext):
    event_id = int(callback.data.split("_")[1])
    await state.update_data(edit_ev_id=event_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назву", callback_data="field_title"), InlineKeyboardButton(text="Опис", callback_data="field_description")],
        [InlineKeyboardButton(text="Фото афіші", callback_data="field_photo_id"), InlineKeyboardButton(text="Локацію", callback_data="field_location")],
        [InlineKeyboardButton(text="Дату/Час", callback_data="field_date_time"), InlineKeyboardButton(text="Ціну", callback_data="field_price")],
        [InlineKeyboardButton(text="К-сть квитків", callback_data="field_total_tickets"), InlineKeyboardButton(text="Повідомлення", callback_data="field_success_message")]
    ])
    await callback.message.edit_text("Що саме ви хочете змінити?", reply_markup=kb)
    await state.set_state(AdminEdit.select_field)

@dp.callback_query(AdminEdit.select_field, F.data.startswith("field_"))
async def enter_new_value(callback: CallbackQuery, state: FSMContext):
    field_name = callback.data.replace("field_", "")
    data = await state.get_data()
    event = await db.get_event(data['edit_ev_id'])
    
    if field_name == "price" and event['is_free']:
        return await callback.answer("❌ Це безкоштовна подія! Ціну змінити неможливо.", show_alert=True)
        
    await state.update_data(edit_field=field_name)
    names_ua = {"title": "нову НАЗВУ", "description": "новий ОПИС", "photo_id": "нову АФІШУ (надішліть фото)", "date_time": "нову ДАТУ та ЧАС", "location": "нову ЛОКАЦІЮ", "total_tickets": "нову загальну КІЛЬКІСТЬ КВИТКІВ (число)", "price": "нову ЦІНУ", "success_message": "нове ФІНАЛЬНЕ ПОВІДОМЛЕННЯ"}
    await callback.message.edit_text(f"Введіть {names_ua.get(field_name, 'нове значення')}:")
    await state.set_state(AdminEdit.enter_value)

@dp.message(AdminEdit.enter_value)
async def save_new_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field_name = data['edit_field']
    if field_name == 'photo_id':
        if not message.photo: return await message.answer("❌ Будь ласка, надішліть нове фото афіші:")
        new_value = message.photo[-1].file_id 
    else:
        new_value = message.text
        
    event = await db.get_event(data['edit_ev_id'])
    if field_name == 'total_tickets' and (not new_value.isdigit() or int(new_value) <= 0):
        return await message.answer("❌ Помилка! Введіть додатнє число більше нуля:")
    if field_name == 'price' and event.get('is_fixed_price') and (not new_value.isdigit() or int(new_value) < 0):
        return await message.answer("❌ Помилка! Для фіксованої ціни введіть тільки число:")
        
    await db.update_event_field(data['edit_ev_id'], field_name, int(new_value) if field_name == 'total_tickets' else new_value)
    await message.answer("✅ Зміни успішно збережено!")
    await state.clear()

@dp.callback_query(F.data == "admin_upload_tickets")
async def admin_upload_tickets_start(callback: CallbackQuery, state: FSMContext):
    events = await db.get_active_events()
    organ_events = [ev for ev in events if ev.get('venue_type') == 'organ_hall']
    
    if not organ_events:
        return await callback.message.answer("Немає активних подій в Органному залі.")
        
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{ev['title']}", callback_data=f"up_tkt_{ev['id']}")] for ev in organ_events
    ])
    await callback.message.edit_text("Обери подію, до якої хочеш прив'язати квитки:", reply_markup=kb)

@dp.callback_query(F.data.startswith("up_tkt_"))
async def admin_ready_to_upload(callback: CallbackQuery, state: FSMContext):
    event_id = int(callback.data.split("_")[2])
    await state.update_data(upload_event_id=event_id)
    
    await callback.message.edit_text(
        "📤 <b>Режим завантаження квитків увімкнено!</b>\n\n"
        "Надсилай сюди фото або ПДФ файли квитків.\n"
        "❗️ <b>ОБОВ'ЯЗКОВО</b> в підписі до кожного файлу пиши ряд і місце через пробіл (напр: <code>1 12</code> або <code>12Б 5</code>).\n\n"
        "<i>Можеш виділити кілька файлів одразу, головне кожному додати підпис.</i>\n\n"
        "Коли закінчиш, натисни кнопку нижче.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Завершити завантаження", callback_data="finish_upload")]]),
        parse_mode="HTML"
    )
    await state.set_state(AdminTickets.uploading)

@dp.message(AdminTickets.uploading, F.photo | F.document)
async def process_ticket_file(message: Message, state: FSMContext):
    caption = message.caption
    if not caption:
        return await message.answer("❌ Файл проігноровано: ти забув додати підпис (ряд і місце)!")
        
    parts = caption.strip().split()
    if len(parts) != 2:
        return await message.answer(f"❌ Файл проігноровано: неправильний формат підпису '{caption}'. Треба 'Ряд Місце' (напр. '1 12').")
        
    row, seat = parts[0], parts[1]
    data = await state.get_data()
    event_id = data['upload_event_id']
    
    f_id = message.photo[-1].file_id if message.photo else message.document.file_id
    f_type = "photo" if message.photo else "document"
    
    await db.add_seat_ticket(event_id, row, seat, f_id, f_type)
    await message.answer(f"✅ Збережено квиток для: Ряд {row}, Місце {seat}")

@dp.callback_query(AdminTickets.uploading, F.data == "finish_upload")
async def finish_ticket_upload(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("✅ Завантаження квитків завершено! Вони автоматично надсилатимуться покупцям.")
    await state.clear()


# --- МАСОВЕ ЗАВАНТАЖЕННЯ КВИТКІВ ---
@dp.callback_query(F.data == "admin_mass_upload")
async def admin_mass_upload_start(callback: CallbackQuery, state: FSMContext):
    events = await db.get_active_events()
    organ_events = [ev for ev in events if ev.get('venue_type') == 'organ_hall']
    
    if not organ_events:
        return await callback.message.answer("Немає активних подій в Органному залі.")
        
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{ev['title']}", callback_data=f"mass_tkt_{ev['id']}")] for ev in organ_events
    ])
    await callback.message.edit_text("Обери подію для МАСОВОГО завантаження квитків:", reply_markup=kb)

@dp.callback_query(F.data.startswith("mass_tkt_"))
async def admin_ready_to_mass_upload(callback: CallbackQuery, state: FSMContext):
    event_id = int(callback.data.split("_")[2])
    await state.update_data(upload_event_id=event_id, uploaded_count=0)
    
    await callback.message.edit_text(
        "📂 <b>МАСОВЕ ЗАВАНТАЖЕННЯ УВІМКНЕНО!</b>\n\n"
        "Просто виділи всі PDF-файли квитків (можна до 100 шт. за раз) і відправ їх мені.\n\n"
        "⚠️ <b>ВАЖЛИВО:</b> Назви файлів повинні містити ряд і місце після слова 'Партер', наприклад:\n"
        "<code>10895874_Партер_24_1_2025-10-04_1.pdf</code>\n\n"
        "<i>Я сам прочитаю назву і розкладу їх по місцях. Ніяких підписів додавати не треба!</i>\n\n"
        "Коли завантажиш усі файли, натисни кнопку нижче.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Завершити масове завантаження", callback_data="finish_mass_upload")]]),
        parse_mode="HTML"
    )
    await state.set_state(AdminTickets.mass_uploading)

@dp.message(AdminTickets.mass_uploading, F.document)
async def process_mass_ticket_file(message: Message, state: FSMContext):
    file_name = message.document.file_name
    
    # Універсальний парсер: шукає структуру ЯКИЙСЬНОМЕР_СЕКТОР_РЯД_МІСЦЕ_...
    # Ми беремо будь-який текст до другого підкреслення, потім витягуємо РЯД і МІСЦЕ
    match = re.search(r'^[^_]+_[^_]+_([0-9А-Яа-я]+)_(\d+)_', file_name, re.IGNORECASE)
    
    if not match:
        return await message.answer(f"❌ Файл <b>{file_name}</b> проігноровано: назва не відповідає формату 'Номер_Сектор_РЯД_МІСЦЕ_Дата'.", parse_mode="HTML")
        
    row = match.group(1)
    seat = match.group(2)
    
    data = await state.get_data()
    event_id = data['upload_event_id']
    f_id = message.document.file_id
    
    await db.add_seat_ticket(event_id, row, seat, f_id, "document")
    
    # Оновлюємо лічильник
    new_count = data.get('uploaded_count', 0) + 1
    await state.update_data(uploaded_count=new_count)
    
    # Звітуємо
    if new_count <= 3 or new_count % 10 == 0:
        await message.answer(f"✅ Збережено: Ряд {row}, Місце {seat} <i>({file_name})</i>. Всього: {new_count}", parse_mode="HTML")

@dp.callback_query(AdminTickets.mass_uploading, F.data == "finish_mass_upload")
async def finish_mass_upload(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    count = data.get('uploaded_count', 0)
    await callback.message.edit_text(f"✅ <b>Масове завантаження завершено!</b>\nУспішно збережено квитків: <b>{count}</b> шт.", parse_mode="HTML")
    await state.clear()

# --- АДМІН: ПІДТВЕРДЖЕННЯ ОПЛАТИ ---
@dp.callback_query(F.data.startswith("conf_") | F.data.startswith("reje_"))
async def handle_decision(callback: CallbackQuery):
    action = callback.data.split("_")[0]
    order_id = int(callback.data.split("_")[1])
    order = await db.get_order(order_id)
    event = await db.get_event(order['event_id'])
    
    if action == "conf":
        await db.update_order_status(order_id, "confirmed")
        await sheets.update_payment_in_sheet(event['title'], order_id, "Підтверджено")
        await bot.send_message(order['user_id'], f"Твоя оплата підтверджена!\n\n{event['success_message']}")
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("Оплата підтверджена!")
    else:
        await sheets.update_payment_in_sheet(event['title'], order_id, "Відхилено")
        await bot.send_message(order['user_id'], "Оплата не підтверджена. Перевір дані або напиши адміну.")
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.reply("Замовлення відхилено.")

# --- РОЗСИЛКА ---
@dp.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    events = await db.get_active_events()
    kb_buttons = [[InlineKeyboardButton(text="📢 Усім зареєстрованим у боті", callback_data="bcast_all")]]
    for ev in events: kb_buttons.append([InlineKeyboardButton(text=f"🎫 Тільки: {ev['title']}", callback_data=f"bcast_ev_{ev['id']}")])
    kb_buttons.append([InlineKeyboardButton(text="❌ Скасувати", callback_data="bcast_cancel")])
    await callback.message.edit_text("<b>Кому хочеш надіслати повідомлення?</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons), parse_mode="HTML")
    await state.set_state(AdminBroadcast.choose_audience)

@dp.callback_query(AdminBroadcast.choose_audience, F.data.startswith("bcast_"))
async def choose_broadcast_audience(callback: CallbackQuery, state: FSMContext):
    action = callback.data.replace("bcast_", "")
    if action == "cancel":
        await callback.message.edit_text("❌ Розсилку скасовано.")
        return await state.clear()
    await state.update_data(broadcast_target=action)
    await callback.message.edit_text("📢 <b>Режим розсилки</b>\nНадішли мені повідомлення.\n<i>Щоб скасувати, напиши 'Скасувати'.</i>", parse_mode="HTML")
    await state.set_state(AdminBroadcast.waiting_for_message)

@dp.message(AdminBroadcast.waiting_for_message)
async def process_broadcast(message: Message, state: FSMContext):
    if message.text and message.text.lower() == 'скасувати':
        await message.answer("❌ Розсилку скасовано.")
        return await state.clear()

    data = await state.get_data()
    target = data.get('broadcast_target')
    users = await db.get_all_users() if target == "all" else await db.get_users_by_event(int(target.replace("ev_", "")))

    if not users:
        await message.answer("🤷‍♂️ Не знайдено користувачів для цієї розсилки.")
        return await state.clear()

    await message.answer(f"🚀 Починаю розсилку для {len(users)} користувачів...")
    success, blocked = 0, 0
    for user in users:
        try:
            await message.copy_to(user['tg_id'])
            success += 1
            await asyncio.sleep(0.05) 
        except Exception:
            blocked += 1
    
    await message.answer(f"✅ <b>Розсилку завершено!</b>\n\n📨 Успішно: {success}\n🚫 Заблокували: {blocked}", parse_mode="HTML")
    await state.clear()

# --- АДМІН: ЧОРНИЙ СПИСОК ---
@dp.callback_query(F.data == "admin_blacklist")
async def admin_bl_menu(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Додати юзера", callback_data="bl_add")],
        [InlineKeyboardButton(text="Видалити юзера", callback_data="bl_remove")],
        [InlineKeyboardButton(text="Список", callback_data="bl_list")]
    ])
    await callback.message.edit_text("⚫ <b>Керування чорним списком</b>", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "bl_add")
async def bl_add(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введіть @юзернейм людини, яку треба забанити:")
    await state.set_state(AdminBlacklist.add)

@dp.message(AdminBlacklist.add)
async def process_bl_add(message: Message, state: FSMContext):
    await db.add_to_blacklist(message.text)
    await message.answer(f"✅ Користувача {message.text} додано до чорного списку.", reply_markup=admin_kb())
    await state.clear()

@dp.callback_query(F.data == "bl_remove")
async def bl_remove(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введіть @юзернейм людини для розблокування:")
    await state.set_state(AdminBlacklist.remove)

@dp.message(AdminBlacklist.remove)
async def process_bl_remove(message: Message, state: FSMContext):
    await db.remove_from_blacklist(message.text)
    await message.answer(f"✅ Користувача {message.text} розблоковано.", reply_markup=admin_kb())
    await state.clear()

@dp.callback_query(F.data == "bl_list")
async def bl_list(callback: CallbackQuery):
    banned = await db.get_blacklist()
    if not banned:
        await callback.message.edit_text("Чорний список пустий.", reply_markup=admin_kb())
    else:
        text = "⚫ <b>Заблоковані юзери:</b>\n" + "\n".join([f"- @{u}" for u in banned])
        await callback.message.edit_text(text, reply_markup=admin_kb(), parse_mode="HTML")

@dp.message()
async def global_fallback(message: Message, state: FSMContext):
    await message.answer("🤷‍♂️ Я не розумію цю команду або формат. Будь ласка, користуйся кнопками меню!", reply_markup=main_kb(message.from_user.id))

# --- АДМІНСЬКЕ КЕРУВАННЯ МІСЦЯМИ ---
@dp.callback_query(F.data == "admin_manage_hall")
async def admin_manage_hall_list(callback: CallbackQuery):
    events = await db.get_active_events()
    organ_events = [ev for ev in events if ev.get('venue_type') == 'organ_hall']
    if not organ_events: return await callback.message.answer("Немає активних подій в Органному залі.")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{ev['title']}", callback_data=f"adm_hall_{ev['id']}")] for ev in organ_events
    ])
    await callback.message.edit_text("Обери подію для перегляду карти:", reply_markup=kb)

@dp.callback_query(F.data.startswith("adm_hall_"))
async def open_admin_hall(callback: CallbackQuery):
    event_id = int(callback.data.split("_")[2])
    occ_list = await db.get_occupied_seats(event_id)
    occ_str = ",".join(occ_list)
    
    # ПЕРЕДАЄМО admin=true ТА ev_id В URL!
    web_app_url = f"https://telegram-bot-tickets-nulp.vercel.app/?occ={occ_str}&admin=true&ev_id={event_id}&t={int(time.time())}"
    
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🛠 Відкрити карту (Адмін)", web_app=WebAppInfo(url=web_app_url))]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await callback.message.answer("Карта для адміністрування готова 👇", reply_markup=kb)

# У main.py знайди perform_adm_cancel і онови її:

@dp.callback_query(F.data.startswith("adm_cancel_"))
async def perform_adm_cancel(callback: CallbackQuery):
    parts = callback.data.split("_")
    order_id, row, seat = int(parts[2]), parts[3], parts[4]
    
    order = await db.get_order(order_id)
    if not order: return await callback.answer("Замовлення не знайдено", show_alert=True)
    
    event = await db.get_event(order['event_id'])
    
    # 1. Видаляємо з бази даних
    success = await db.remove_seat_from_order(order_id, row, seat)
    
    if success:
        # 2. ОНОВЛЮЄМО GOOGLE ТАБЛИЦЮ 👈
        await sheets.cancel_seat_in_sheet(event['title'], order_id, row, seat)
        
        await callback.message.edit_text(callback.message.text + f"\n\n❌ <b>Квиток (Ряд {row}, Місце {seat}) скасовано в БД та Таблиці!</b>", parse_mode="HTML")
        
        # 3. Сповіщення юзеру
        try:
            await bot.send_message(
                order['user_id'], 
                f"⚠️ <b>Твій квиток скасовано</b>\nАдміністрація скасувала твоє місце (Ряд {row}, Місце {seat}) на подію <b>{event['title']}</b>.\nГроші будуть повернуті (якщо це була платна подія).",
                parse_mode="HTML"
            )
        except:
            pass
    else:
        await callback.answer("Помилка при видаленні", show_alert=True)
        

async def main():
    await db.connect()
    asyncio.create_task(start_webhook()) 
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())