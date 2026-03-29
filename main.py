import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv
from database import Database
from states import AdminEdit, EditProfile, OrderState, AddEventState, Registration
from aiohttp import web
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
        [InlineKeyboardButton(text="Видалити подію", callback_data="admin_del_list")]
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
    await db.register_full_user(
        tg_id=message.from_user.id, username=message.from_user.username,
        first_name=user_data['first_name'], last_name=user_data['last_name'],
        institute=user_data['institute'], group=group
    )
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
    if not user:
        return await message.answer("❌ Профіль не знайдено. Напиши /start для реєстрації.")

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
        "last_name": "нове Прізвище",
        "first_name": "нове Ім'я",
        "institute": "свій Інститут (напр. ІКНІ, ІАРХ)",
        "group": "свою Групу (напр. КН-201)"
    }
    
    text_prompt = prompts.get(field_to_edit, "нове значення")
    
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(f"✍️ <b>Введи {text_prompt}:</b>", parse_mode="HTML")
    await state.set_state(EditProfile.enter_value)
    await callback.answer()

# --- Збереження нових даних ---
@dp.message(EditProfile.enter_value)
async def save_new_profile_value(message: Message, state: FSMContext):
    if message.text in ["Доступні події", "Мій профіль", "Адмін-панель"]:
        await state.clear()
        if message.text == "Доступні події": return await list_events(message)
        elif message.text == "Мій профіль": return await show_profile(message, state)
        else: return await admin_panel(message)

    data = await state.get_data()
    field_name = data['edit_field']
    new_value = message.text
    
    await db.update_user_field(message.from_user.id, field_name, new_value)
    
    await message.answer("✅ <b>Дані успішно оновлено!</b>", parse_mode="HTML")
    await state.clear()
    
    await show_profile(message, state)

@dp.message(F.text == "Доступні події")
async def list_events(message: Message):
    events = await db.get_active_events()
    if not events:
        return await message.answer("📭 <b>Наразі активних подій немає.</b> Слідкуй за анонсами!", parse_mode="HTML")
    
    for ev in events:
        rem = ev['remaining_tickets']
        if rem <= 0:
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Квитків немає", callback_data="sold_out")]])
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎟 Купити квиток", callback_data=f"buy_{ev['id']}")]])
        
        type_str = "🎁 <i>Безкоштовно</i>" if ev['is_free'] else f"💰 <b>{ev['price']}</b>"
        
        event_text = (
            f"🎉 <b>{ev['title']}</b>\n\n"
            f"📅 <b>Коли:</b> {ev['date_time']}\n"
            f"💵 <b>Вартість:</b> {type_str}\n"
            f"📊 <b>Залишилось квитків:</b> {rem} з {ev['total_tickets']}\n\n"
            f"📝 <b>Опис:</b>\n<i>{ev['description']}</i>"
        )
        await message.answer(event_text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "sold_out")
async def handle_sold_out(callback: CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("🥺 На жаль, усі квитки на цю подію вже розібрали!", parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_"))
async def start_buy(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    
    await state.update_data(ev_id=int(callback.data.split("_")[1]))
    await callback.message.answer("🛒 <b>Скільки квитків беремо?</b>\n<i>Напиши просто число (наприклад: 1, 2):</i>", parse_mode="HTML")
    await state.set_state(OrderState.waiting_for_quantity)

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
    
    await state.update_data(qty=qty)
    user = await db.get_user(message.from_user.id)
    username = user['username'] if user['username'] else "Без_юзернейму"
    
    if event['is_free']:
        order_id = await db.add_order(message.from_user.id, data['ev_id'], qty, None, "free")
        await db.update_order_status(order_id, "confirmed")
        await sheets.add_order_to_sheet(event['title'], order_id, user['last_name'], user['first_name'], username, user['institute'], user['student_group'], qty, "Безкоштовно")
        
        await message.answer(
            f"✅ <b>Бронювання успішне!</b>\n\n"
            f"🎟 <b>Кількість:</b> {qty} шт.\n\n"
            f"📌 {event['success_message']}",
            parse_mode="HTML"
        )
        await state.clear()
    else:
        if event['is_fixed_price']:
            total_price = int(event['price']) * qty
            text = (
                f"📝 <b>Твоє замовлення:</b> {qty} шт.\n"
                f"💳 <b>До оплати:</b> {total_price} грн <i>(по {event['price']} грн/шт)</i>\n\n"
                f"🔗 <b>Банка:</b> {event['bank_link']}\n"
                f"🏦 <b>Картка:</b> <code>{event['card_number']}</code>\n\n"
                f"📸 <b>Наступний крок:</b>\nОплати та надішли сюди скріншот або PDF-квитанцію 👇"
            )
        else:
            text = (
                f"📝 <b>Твоє замовлення:</b> {qty} шт.\n"
                f"💵 <b>Вартість:</b> {event['price']}\n\n"
                f"⚠️ <i>Уважно розрахуй загальну суму та здійсни оплату!</i>\n\n"
                f"🔗 <b>Банка:</b> {event['bank_link']}\n"
                f"🏦 <b>Картка:</b> <code>{event['card_number']}</code>\n\n"
                f"📸 <b>Наступний крок:</b>\nНадішли скріншот або PDF-квитанцію 👇"
            )
                    
        await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)
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
    
    await sheets.add_order_to_sheet(event['title'], order_id, user['last_name'], user['first_name'], username, user['institute'], user['student_group'], data['qty'], "Очікує")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Підтвердити", callback_data=f"conf_{order_id}")],
        [InlineKeyboardButton(text="Відхилити", callback_data=f"reje_{order_id}")]
    ])
    
    caption = (
        f"🚨 <b>Нова оплата #{order_id}!</b>\n\n"
        f"👤 <b>Студент:</b> {user['last_name']} {user['first_name']} (@{username})\n"
        f"📚 <b>Група:</b> {user['institute']}, {user['student_group']}\n"
        f"🎟 <b>Кількість квитків:</b> {data['qty']} шт."
    )
               
    for admin in ADMIN_IDS:
        try:
            if f_type == "photo": await bot.send_photo(admin, f_id, caption=caption, reply_markup=kb)
            else: await bot.send_document(admin, f_id, caption=caption, reply_markup=kb)
        except Exception:
            pass
            
    await message.answer("⏳ <b>Квитанцію прийнято!</b>\nОчікуй на підтвердження адміністратором. Ми надішлемо тобі повідомлення.", parse_mode="HTML")
    await state.clear()


@dp.message(OrderState.waiting_for_proof)
async def wrong_proof_format(message: Message, state: FSMContext):
    if message.text in ["Доступні події", "Адмін-панель"]:
        await state.clear()
        if message.text == "Доступні події": return await list_events(message)
        else: return await admin_panel(message)
        
    await message.answer("❌ <b>Неправильний формат!</b>\nБудь ласка, надішли скріншот (фото) або PDF-файл квитанції. Текст чи стікери не приймаються.", parse_mode="HTML")


# --- ЛОГІКА АДМІНА ---
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
    
    if is_fixed:
        await callback.message.answer("Введіть ціну за 1 квиток (ТІЛЬКИ ЧИСЛО, напр. 150):")
    else:
        await callback.message.answer("Введіть текст ціни (напр. 'від 100 грн' або 'донат від 50 грн'):")
    
    await state.set_state(AddEventState.price)
    await callback.answer()

@dp.message(AddEventState.price)
async def add_ev_price(message: Message, state: FSMContext):
    data = await state.get_data()
    # Якщо вибрали фіксовану ціну, не даємо ввести букви
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
    await message.answer("Введіть фінальне повідомлення після підтвердження оплати (напр. 'Забирай квиток в 218 кабінеті'):")
    await state.set_state(AddEventState.success_message)

@dp.message(AddEventState.success_message)
async def add_ev_final(message: Message, state: FSMContext):
    d = await state.get_data()
    await db.add_event(d['title'], d['desc'], d['dt'], d['total_tickets'], d['is_free'], d['is_fixed_price'], d['price'], d.get('link', ''), d.get('card', ''), message.text)
    await message.answer("✅ Подію успішно додано!", reply_markup=main_kb(message.from_user.id))
    await state.clear()

@dp.callback_query(F.data == "admin_del_list")
async def show_delete_list(callback: CallbackQuery):
    events = await db.get_active_events()
    if not events:
        return await callback.message.answer("Немає активних подій для видалення.")
    
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
    await callback.answer("Видалено")

# --- РЕДАГУВАННЯ ПОДІЇ ---
@dp.callback_query(F.data == "admin_edit_list")
async def show_edit_list(callback: CallbackQuery, state: FSMContext):
    events = await db.get_active_events()
    if not events:
        return await callback.message.answer("Немає активних подій для редагування.")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{ev['title']}", callback_data=f"edit_{ev['id']}")] for ev in events
    ])
    await callback.message.answer("Оберіть подію для РЕДАГУВАННЯ:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("edit_"))
async def select_field_to_edit(callback: CallbackQuery, state: FSMContext):
    event_id = int(callback.data.split("_")[1])
    await state.update_data(edit_ev_id=event_id)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назву", callback_data="field_title"), InlineKeyboardButton(text="Опис", callback_data="field_description")],
        [InlineKeyboardButton(text="Дату/Час", callback_data="field_date_time"), InlineKeyboardButton(text="К-сть квитків", callback_data="field_total_tickets")],
        [InlineKeyboardButton(text="Ціну", callback_data="field_price"), InlineKeyboardButton(text="Повідомлення", callback_data="field_success_message")]
    ])
    await callback.message.edit_text("Що саме ви хочете змінити?", reply_markup=kb)
    await state.set_state(AdminEdit.select_field)

@dp.callback_query(AdminEdit.select_field, F.data.startswith("field_"))
async def enter_new_value(callback: CallbackQuery, state: FSMContext):
    field_name = callback.data.replace("field_", "")
    data = await state.get_data()
    event_id = data['edit_ev_id']
    
    event = await db.get_event(event_id)
    
    if field_name == "price" and event['is_free']:
        return await callback.answer("❌ Це безкоштовна подія! Змінити ціну неможливо.", show_alert=True)
        
    await state.update_data(edit_field=field_name)
    
    names_ua = {
        "title": "нову НАЗВУ", "description": "новий ОПИС", 
        "date_time": "нову ДАТУ та ЧАС", "total_tickets": "нову загальну КІЛЬКІСТЬ КВИТКІВ (число)",
        "price": "нову ЦІНУ", "success_message": "нове ФІНАЛЬНЕ ПОВІДОМЛЕННЯ"
    }
    
    await callback.message.edit_text(f"Введіть {names_ua.get(field_name, 'нове значення')}:")
    await state.set_state(AdminEdit.enter_value)

@dp.message(AdminEdit.enter_value)
async def save_new_value(message: Message, state: FSMContext):
    data = await state.get_data()
    event_id = data['edit_ev_id']
    field_name = data['edit_field']
    new_value = message.text
    
    event = await db.get_event(event_id)
    
    if field_name == 'price' and event['is_free']:
        await state.clear()
        return await message.answer("❌ Помилка! Ця подія безкоштовна. Зміна ціни скасована.")
    
    if field_name == 'total_tickets':
        if not new_value.isdigit() or int(new_value) <= 0:
            return await message.answer("❌ Помилка! Введіть додатнє число більше нуля:")
        new_value = int(new_value)
        
    if field_name == 'price' and event.get('is_fixed_price'):
        if not new_value.isdigit() or int(new_value) < 0:
            return await message.answer("❌ Помилка! Для фіксованої ціни введіть тільки число (0 або більше):")
        
    await db.update_event_field(event_id, field_name, new_value)
    
    await message.answer("✅ Зміни успішно збережено!")
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
        await bot.send_message(order['user_id'], f"Твоя оплата підтверджена!\n\n{event['success_message']}")
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("Оплата підтверджена!")
    else:
        await sheets.update_payment_in_sheet(event['title'], order_id, "Відхилено")
        await bot.send_message(order['user_id'], "Оплата не підтверджена. Перевір дані або напиши адміну.")
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.reply("Замовлення відхилено.")

@dp.message()
async def global_fallback(message: Message, state: FSMContext):
    await message.answer("🤷‍♂️ Я не розумію цю команду або формат. Будь ласка, користуйся кнопками меню!", reply_markup=main_kb(message.from_user.id))

async def main():
    await db.connect()
    asyncio.create_task(start_webhook()) 
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())