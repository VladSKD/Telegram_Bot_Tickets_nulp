import gspread
from google.oauth2.service_account import Credentials
import asyncio
import os
import json
import gspread
from google.oauth2.service_account import Credentials
import os, json, asyncio



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
    if not client: 
        return None
    
    try:
        # Логіка вибору таблиці залежно від назви події
        if "Гала" in event_title or "Весна" in event_title:
            url = os.getenv("SPREADSHEET_GALA_URL")
        else:
            url = os.getenv("SPREADSHEET_ORGAN_URL")
            
        doc = client.open_by_url(url)
        
        try:
            worksheet = doc.worksheet(event_title)
        except gspread.exceptions.WorksheetNotFound:
            # Створюємо нову вкладку для конкретного івенту, якщо її немає
            # Додаємо 10 стовпців (з урахуванням "Інституту" для балів)
            worksheet = doc.add_worksheet(title=event_title, rows="1000", cols="10")
            worksheet.append_row([
                "ID Замовлення", "Прізвище", "Ім'я", "Telegram", 
                "Інститут", "Сектор", "Ряд", "Місце", "Статус", "Квиток забрано"
            ])
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
    
def _get_occupied_from_sheet(event_title):
    client = get_client()
    if not client: return []
    try:
        # Використовуємо ту саму логіку вибору URL
        url = os.getenv("SPREADSHEET_GALA_URL") if "Гала" in event_title else os.getenv("SPREADSHEET_ORGAN_URL")
        doc = client.open_by_url(url)
        
        # Для Гали шукаємо вкладку "Схема залу"
        ws = doc.worksheet("Схема залу")
        
        all_cells = ws.get_all_cells(get_metadata=True)
        
        # Отримуємо всі формати клітинок (кольори) одним запитом
        # Це важливо для швидкодії, щоб не смикати API для кожної клітинки
        all_formats = ws.get_all_cells(get_metadata=True)
        
        occupied = []
        
        # Співвідношення координат Google Таблиці до твоїх Секторів
        # (Це приклад логіки, її треба підправити під точні стовпці твого Excel)
        for row_idx, row_data in enumerate(all_formats):
            for col_idx, cell in enumerate(row_data):
                color = cell.get('userEnteredFormat', {}).get('backgroundColor', {})
                
                # Якщо клітинка не біла (R:1, G:1, B:1) — вона зайнята
                if color and (color.get('red', 1) < 1 or color.get('green', 1) < 1 or color.get('blue', 1) < 1):
                    # Логіка визначення місця за координатами (row_idx, col_idx)
                    # Наприклад, якщо це Сектор B:
                    seat_id = translate_coords_to_id(row_idx, col_idx)
                    if seat_id:
                        occupied.append(seat_id)
        
        return occupied
    except Exception as e:
        print(f"❌ [SHEETS ERROR] Помилка читання кольорів: {e}")
        return []

SECTOR_MAP = {
    'A': {'c_start': 18, 'c_end': 25, 'r_start': 10, 'r_end': 31, 'h_off': 8},   # R-Y
    'B': {'c_start': 27, 'c_end': 34, 'r_start': 10, 'r_end': 31, 'h_off': 8},   # AA-AH
    'C': {'c_start': 36, 'c_end': 43, 'r_start': 10, 'r_end': 31, 'h_off': 8},   # AJ-AQ
    'D_row24': {'c_start': 18, 'c_end': 43, 'r_start': 36, 'r_end': 36},         # R-AQ (Row 36)
    'D_main':  {'c_start': 21, 'c_end': 40, 'r_start': 37, 'r_end': 40, 'h_off': 12}, # U-AN (Row 37-40)
    'Balcony_main': {'c_start': 14, 'c_end': 39, 'r_start': 53, 'r_end': 58, 'h_off': 52}, # N-AM
    'Balcony_L': {'c_start': 6, 'c_end': 8, 'r_start': 31, 'r_end': 48, 'h_off': 30},   # F-H
    'Balcony_R': {'c_start': 52, 'c_end': 54, 'r_start': 31, 'r_end': 49, 'h_off': 30}   # AZ-BB
}

def translate_coords_to_id(row, col):
    """Перетворює Excel Row/Col у формат ID: Zone-Row-Seat"""
    # Сектори A, B, C
    for zone in ['A', 'B', 'C']:
        m = SECTOR_MAP[zone]
        if m['r_start'] <= row <= m['r_end'] and m['c_start'] <= col <= m['c_end']:
            return f"{zone}-{row - m['h_off']}-{col - (m['c_start'] - 1)}"

    # Сектор D (Ряд 24)
    m = SECTOR_MAP['D_row24']
    if row == m['r_start'] and m['c_start'] <= col <= m['c_end']:
        return f"D-24-{col - 17}"

    # Сектор D (Ряди 25-28)
    m = SECTOR_MAP['D_main']
    if m['r_start'] <= row <= m['r_end'] and m['c_start'] <= col <= m['c_end']:
        return f"D-{row - m['h_off']}-{col - 20}"

    # Бічні балкони
    if SECTOR_MAP['Balcony_L']['r_start'] <= row <= SECTOR_MAP['Balcony_L']['r_end'] and 6 <= col <= 8:
        return f"ЛБ-{row - 30}-{col - 5}"
    if SECTOR_MAP['Balcony_R']['r_start'] <= row <= SECTOR_MAP['Balcony_R']['r_end'] and 52 <= col <= 54:
        return f"ПБ-{row - 30}-{col - 51}"

    # Головний балкон
    m = SECTOR_MAP['Balcony_main']
    if m['r_start'] <= row <= m['r_end'] and m['c_start'] <= col <= m['c_end']:
        return f"Балкон-{row - m['h_off']}-{col - 13}"

    return None

def _get_occupied_from_sheet(event_title):
    client = get_client()
    if not client: return []
    try:
        doc = client.open_by_url(os.getenv("SPREADSHEET_URL"))
        ws = doc.worksheet("Схема залу")
        
        # Отримуємо всі клітинки з інформацією про формат
        all_cells = ws.get_all_cells(get_metadata=True)
        occupied = []
        
        for r_idx, row_cells in enumerate(all_cells, 1):
            for c_idx, cell in enumerate(row_cells, 1):
                fmt = cell.get('userEnteredFormat', {})
                bg = fmt.get('backgroundColor', {})
                
                # Перевіряємо, чи колір НЕ білий (якщо R, G або B < 1)
                if bg and (bg.get('red', 1) < 1 or bg.get('green', 1) < 1 or bg.get('blue', 1) < 1):
                    seat_id = translate_coords_to_id(r_idx, c_idx)
                    if seat_id:
                        occupied.append(seat_id)
        return occupied
    except Exception as e:
        print(f"❌ Помилка синхронізації кольорів: {e}")
        return []
    
def _add_order(event_title, order_id, user_info, seat_id, status):
    """
    seat_id приходить у форматі "A-2-5"
    """
    try:
        ws = _get_or_create_worksheet(event_title) # Вкладка з назвою івенту
        zone, row, seat = seat_id.split('-')
        
        # ID, Прізвище, Ім'я, ТГ, Сектор, Ряд, Місце, Статус, Забрав квиток
        row_data = [
            order_id, user_info['last_name'], user_info['first_name'],
            f"@{user_info['username']}", zone, row, seat, status, "Ні"
        ]
        ws.append_row(row_data)
    except Exception as e:
        print(f"❌ Помилка запису в таблицю замовлень: {e}")