import re

import gspread
from google.oauth2.service_account import Credentials
import asyncio
import os
import json

# --- КООРДИНАТИ СЕКТОРІВ (БЕЗ ЗМІН) ---
SECTOR_MAP = {
    'A': {'c_start': 18, 'c_end': 25, 'r_start': 10, 'r_end': 31, 'h_off': 8},
    'B': {'c_start': 27, 'c_end': 34, 'r_start': 10, 'r_end': 31, 'h_off': 8},
    'C': {'c_start': 36, 'c_end': 43, 'r_start': 10, 'r_end': 31, 'h_off': 8},
    'D_row24': {'c_start': 18, 'c_end': 43, 'r_start': 36, 'r_end': 36},
    'D_main':  {'c_start': 21, 'c_end': 40, 'r_start': 37, 'r_end': 40, 'h_off': 12},
    'Balcony_main': {'c_start': 14, 'c_end': 39, 'r_start': 53, 'r_end': 58, 'h_off': 52},
    'Balcony_L': {'c_start': 6, 'c_end': 8, 'r_start': 31, 'r_end': 48, 'h_off': 30},
    'Balcony_R': {'c_start': 52, 'c_end': 54, 'r_start': 31, 'r_end': 49, 'h_off': 30}
}

def get_client():
    try:
        creds_json = os.getenv("GOOGLE_CREDS_JSON")
        if not creds_json: return None
        creds_dict = json.loads(creds_json)
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        print(f"❌ [SHEETS ERROR] Помилка авторизації: {e}")
        return None

def translate_coords_to_id(row, col):
    """Мапінг координат Excel у формат Zone-Row-Seat"""
    for zone in ['A', 'B', 'C']:
        m = SECTOR_MAP[zone]
        if m['r_start'] <= row <= m['r_end'] and m['c_start'] <= col <= m['c_end']:
            return f"{zone}-{row - m['h_off']}-{col - (m['c_start'] - 1)}"
    m = SECTOR_MAP['D_row24']
    if row == m['r_start'] and m['c_start'] <= col <= m['c_end']:
        return f"D-24-{col - 17}"
    m = SECTOR_MAP['D_main']
    if m['r_start'] <= row <= m['r_end'] and m['c_start'] <= col <= m['c_end']:
        return f"D-{row - m['h_off']}-{col - 20}"
    if SECTOR_MAP['Balcony_L']['r_start'] <= row <= SECTOR_MAP['Balcony_L']['r_end'] and 6 <= col <= 8:
        return f"ЛБ-{row - 30}-{col - 5}"
    if SECTOR_MAP['Balcony_R']['r_start'] <= row <= SECTOR_MAP['Balcony_R']['r_end'] and 52 <= col <= 54:
        return f"ПБ-{row - 30}-{col - 51}"
    m = SECTOR_MAP['Balcony_main']
    if m['r_start'] <= row <= m['r_end'] and m['c_start'] <= col <= m['c_end']:
        return f"Балкон-{row - m['h_off']}-{col - 13}"
    return None

def _get_or_create_worksheet(event_title):
    client = get_client()
    if not client: return None
    try:
        # 🎯 Надійна логіка вибору URL
        is_gala = "Гала" in event_title or "Весна" in event_title
        url = os.getenv("SPREADSHEET_GALA_URL") if is_gala else os.getenv("SPREADSHEET_ORGAN_URL")
        
        doc = client.open_by_url(url)
        try:
            return doc.worksheet(event_title)
        except gspread.exceptions.WorksheetNotFound:
            # Створюємо вкладку з правильними колонками
            ws = doc.add_worksheet(title=event_title, rows="1000", cols="10")
            ws.append_row([
                "ID Замовлення", "Прізвище", "Ім'я", "Telegram", 
                "Інститут", "Сектор", "Ряд", "Місце", "Статус", "Забрано"
            ])
            return ws
    except Exception as e:
        print(f"❌ [SHEETS ERROR] Помилка відкриття: {e}")
        return None

# --- СИНХРОНІЗАЦІЯ КОЛЬОРІВ ---
def _get_occupied_from_sheet(event_title, venue_type):
    client = get_client()
    if not client: return []
    try:
        # Вибираємо URL ТІЛЬКИ за типом залу з бази даних
        if venue_type == 'assembly_hall':
            url = os.getenv("SPREADSHEET_GALA_URL")
            sheet_name = "РОЗСАДКА"
        else:
            url = os.getenv("SPREADSHEET_ORGAN_URL")
            sheet_name = "Схема залу"
            
        doc = client.open_by_url(url)
        ws = doc.worksheet(sheet_name) # Тепер помилки не буде!
        
        all_cells = ws.get_all_cells(get_metadata=True)
        occupied = []
        for r_idx, row_data in enumerate(all_cells, 1):
            for c_idx, cell in enumerate(row_data, 1):
                bg = cell.get('userEnteredFormat', {}).get('backgroundColor', {})
                if bg and (bg.get('red', 1) < 1 or bg.get('green', 1) < 1 or bg.get('blue', 1) < 1):
                    seat_id = translate_coords_to_id(r_idx, c_idx)
                    if seat_id: occupied.append(seat_id)
        return occupied
    except Exception as e:
        print(f"❌ [SHEETS ERROR] Помилка читання кольорів: {e}")
        return []

# Не забудь оновити і цю обгортку
async def get_occupied_from_sheet(event_title, venue_type):
    return await asyncio.to_thread(_get_occupied_from_sheet, event_title, venue_type)

# --- ЗАПИС ЗАМОВЛЕНЬ ---
def _add_order(event_title, order_id, last_name, first_name, username, institute, group, qty, status):
    """Універсальний запис (враховує нову структуру колонок)"""
    try:
        ws = _get_or_create_worksheet(event_title)
        if not ws: return
        
        # Якщо в статусі є інформація про місце (напр. "Р2М5"), витягуємо її
        sector, row, seat = "-", "-", "-"
        if "Р" in status and "М" in status:
            # Спрощений парсинг для Органного залу
            sector = "Органний"
            res = re.search(r'Р(\d+)М(\d+)', status)
            if res:
                row, seat = res.group(1), res.group(2)
        
        # Записуємо в таблицю
        ws.append_row([order_id, last_name, first_name, f"@{username}", institute, sector, row, seat, status, "Ні"])
    except Exception as e:
        print(f"❌ [SHEETS ERROR] Помилка запису: {e}")

def _add_gala_order(event_title, order_id, user_info, seat_id, status):
    """Спеціальний запис для Актової зали (розбиває Zone-Row-Seat)"""
    try:
        ws = _get_or_create_worksheet(event_title)
        if not ws: return
        parts = seat_id.split('-')
        zone, row, seat = parts[0], parts[1], parts[2]
        
        ws.append_row([
            order_id, user_info['last_name'], user_info['first_name'],
            f"@{user_info['username']}", user_info['institute'], zone, row, seat, status, "Ні"
        ])
    except Exception as e:
        print(f"❌ [SHEETS ERROR] Помилка запису Гала: {e}")

async def add_order_to_sheet(*args):
    if len(args) == 5: # Для Гала-концерту
        await asyncio.to_thread(_add_gala_order, *args)
    else: # Для всіх інших
        await asyncio.to_thread(_add_order, *args)

# --- ОНОВЛЕННЯ СТАТУСУ ---
async def update_payment_in_sheet(event_title, order_id, status):
    # Колонка статусу тепер 9-та
    await asyncio.to_thread(_update_cell_in_sheet, event_title, order_id, 9, status)

def _update_cell_in_sheet(event_title, order_id, column_index, new_value):
    try:
        ws = _get_or_create_worksheet(event_title)
        if not ws: return
        cells = ws.findall(str(order_id), in_column=1)
        for cell in cells:
            ws.update_cell(cell.row, column_index, new_value)
    except Exception as e:
        print(f"❌ [SHEETS ERROR] Помилка оновлення: {e}")

# --- РЕЄСТР ---
async def upsert_user_in_registry(last_name, first_name, username, institute, group):
    await asyncio.to_thread(_upsert_user_in_registry, last_name, first_name, username, institute, group)

def _upsert_user_in_registry(last_name, first_name, username, institute, group):
    try:
        client = get_client()
        if not client: return
        doc = client.open_by_url("https://docs.google.com/spreadsheets/d/1CYx4V7_p7keMeKUy2Q_5Rtzy8OuehsifceVTObFD5cQ/edit")
        ws = doc.sheet1 
        user_tag = f"@{username}" if username else "-"
        try:
            cell = ws.find(user_tag, in_column=3)
            if cell:
                ws.update(f"A{cell.row}:B{cell.row}", [[last_name, first_name]])
                ws.update(f"D{cell.row}:E{cell.row}", [[institute, group]])
                return
        except: pass
        ws.append_row([last_name, first_name, user_tag, institute, group])
    except Exception as e:
        print(f"❌ [SHEETS ERROR] Помилка реєстру: {e}")