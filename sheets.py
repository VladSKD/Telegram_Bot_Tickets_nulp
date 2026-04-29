import gspread
from google.oauth2.service_account import Credentials
import asyncio
import os
import json

def get_client():
    try:
        creds_json = os.getenv("GOOGLE_CREDS_JSON")
        if not creds_json:
            print("❌ [SHEETS ERROR] Змінна GOOGLE_CREDS_JSON порожня або не знайдена!")
            return None
        creds_dict = json.loads(creds_json)
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        print(f"❌ [SHEETS ERROR] Помилка авторизації Google API: {e}")
        return None

def _get_or_create_worksheet(event_title):
    client = get_client()
    if not client: return None
    
    try:
        doc = client.open_by_url(os.getenv("SPREADSHEET_URL"))
        try:
            worksheet = doc.worksheet(event_title)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = doc.add_worksheet(title=event_title, rows="1000", cols="8")
            worksheet.append_row(["ID Замовлення", "Прізвище", "Ім'я", "Telegram", "Інститут", "Група", "К-сть квитків", "Статус"])
        return worksheet
    except Exception as e:
        print(f"❌ [SHEETS ERROR] Не вдалося відкрити таблицю: {e}")
        return None

def _add_order(event_title, order_id, last_name, first_name, username, institute, group, qty, status):
    try:
        ws = _get_or_create_worksheet(event_title)
        if ws:
            ws.append_row([order_id, last_name, first_name, f"@{username}" if username != "-" else "-", institute, group, qty, status])
            print(f"✅ [SHEETS] Замовлення #{order_id} успішно записано.")
    except Exception as e:
        print(f"❌ [SHEETS ERROR] Помилка запису замовлення #{order_id}: {e}")

def _update_cell_in_sheet(event_title, order_id, column_index, new_value):
    try:
        ws = _get_or_create_worksheet(event_title)
        if not ws: return
        
        cells = ws.findall(str(order_id), in_column=1)
        if not cells:
            print(f"⚠️ [SHEETS] Рядок з ID {order_id} не знайдено для оновлення.")
            return
            
        for cell in cells:
            ws.update_cell(cell.row, column_index, new_value)
        print(f"✅ [SHEETS] Статус замовлення #{order_id} оновлено на: {new_value}")
    except Exception as e:
        print(f"❌ [SHEETS ERROR] Не вдалося оновити статус: {e}")

async def add_order_to_sheet(*args):
    await asyncio.to_thread(_add_order, *args)

async def update_payment_in_sheet(event_title, order_id, status):
    await asyncio.to_thread(_update_cell_in_sheet, event_title, order_id, 8, status)

def _mark_seat_as_cancelled(event_title, order_id, row_num, seat_num):
    try:
        ws = _get_or_create_worksheet(event_title)
        if not ws: return False
        
        cells = ws.findall(str(order_id), in_column=1)
        seat_marker = f"Р{row_num}М{seat_num}"
        
        for cell in cells:
            status_val = ws.cell(cell.row, 8).value
            if seat_marker in status_val:
                ws.update_cell(cell.row, 8, "🔴 СКАСОВАНО")
                return True
        return False
    except Exception as e:
        print(f"❌ [SHEETS ERROR] Помилка скасування місця: {e}")
        return False

async def cancel_seat_in_sheet(*args):
    await asyncio.to_thread(_mark_seat_as_cancelled, *args)
    
def _upsert_user_in_registry(last_name, first_name, username, institute, group):
    try:
        client = get_client()
        if not client: return
        
        doc = client.open_by_url("https://docs.google.com/spreadsheets/d/1CYx4V7_p7keMeKUy2Q_5Rtzy8OuehsifceVTObFD5cQ/edit")
        ws = doc.sheet1 
        
        user_tag = f"@{username}" if username else "-"
        
        # 1. Шукаємо, чи є вже такий юзер у колонці Telegram (стовпчик 3)
        try:
            cell = ws.find(user_tag, in_column=3)
            if cell:
                # 2. Якщо знайшли — оновлюємо весь рядок (стовпчики 1, 2, 4, 5)
                # Оновлюємо Прізвище (A), Ім'я (B), Інститут (D), Групу (E)
                ws.update(f"A{cell.row}:B{cell.row}", [[last_name, first_name]])
                ws.update(f"D{cell.row}:E{cell.row}", [[institute, group]])
                print(f"✅ [SHEETS] Дані користувача {user_tag} оновлено в реєстрі.")
                return
        except gspread.exceptions.CellNotFound:
            pass # Юзера не знайдено, переходимо до додавання

        # 3. Якщо не знайшли — просто додаємо новий рядок
        ws.append_row([last_name, first_name, user_tag, institute, group])
        print(f"✅ [SHEETS] Нового користувача {last_name} додано в реєстр.")
        
    except Exception as e:
        print(f"❌ [SHEETS ERROR] Помилка синхронізації профілю: {e}")

async def upsert_user_in_registry(*args):
    await asyncio.to_thread(_upsert_user_in_registry, *args)