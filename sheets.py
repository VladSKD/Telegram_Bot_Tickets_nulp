import gspread
from google.oauth2.service_account import Credentials
import asyncio
import os
import json
import re

# --- КОНФІГУРАЦІЯ СЕКТОРІВ ДЛЯ АКТОЇ ЗАЛИ ---
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

def translate_coords_to_id(row, col):
    """Перетворює Excel Row/Col у формат ID: Zone-Row-Seat"""
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
        if "Гала" in event_title or "Весна" in event_title:
            url = os.getenv("SPREADSHEET_GALA_URL")
        else:
            url = os.getenv("SPREADSHEET_ORGAN_URL")
        doc = client.open_by_url(url)
        try:
            worksheet = doc.worksheet(event_title)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = doc.add_worksheet(title=event_title, rows="1000", cols="10")
            worksheet.append_row([
                "ID Замовлення", "Прізвище", "Ім'я", "Telegram", 
                "Інститут", "Сектор", "Ряд", "Місце", "Статус", "Квиток забрано"
            ])
        return worksheet
    except Exception as e:
        print(f"❌ [SHEETS ERROR] Не вдалося відкрити таблицю: {e}")
        return None

# --- ФУНКЦІЇ ЗАПИСУ ДАНИХ ---
def _add_order(event_title, order_id, last_name, first_name, username, institute, group, qty, status):
    """Базова функція для звичайних івентів (Органний зал тощо)"""
    try:
        ws = _get_or_create_worksheet(event_title)
        if ws:
            ws.append_row([order_id, last_name, first_name, f"@{username}" if username != "-" else "-", institute, group, qty, status])
            print(f"✅ [SHEETS] Замовлення #{order_id} записано.")
    except Exception as e:
        print(f"❌ [SHEETS ERROR] Помилка запису замовлення #{order_id}: {e}")

def _add_gala_order(event_title, order_id, user_info, seat_id, status):
    """Спеціалізована функція для Актової зали (Гала-концерт)"""
    try:
        ws = _get_or_create_worksheet(event_title)
        if not ws: return
        parts = seat_id.split('-')
        zone, row, seat = parts[0], parts[1], parts[2]
        row_data = [
            order_id, user_info['last_name'], user_info['first_name'],
            f"@{user_info['username']}", user_info['institute'], zone, row, seat, status, "Ні"
        ]
        ws.append_row(row_data)
    except Exception as e:
        print(f"❌ [SHEETS ERROR] Помилка запису Гала-замовлення: {e}")

async def add_order_to_sheet(*args):
    """Викликає правильну функцію залежно від кількості аргументів"""
    if len(args) == 5: # Для Гала-концерту
        await asyncio.to_thread(_add_gala_order, *args)
    else: # Для Органного залу
        await asyncio.to_thread(_add_order, *args)

def _update_cell_in_sheet(event_title, order_id, column_index, new_value):
    try:
        ws = _get_or_create_worksheet(event_title)
        if not ws: return
        cells = ws.findall(str(order_id), in_column=1)
        if not cells: return
        for cell in cells:
            ws.update_cell(cell.row, column_index, new_value)
    except Exception as e:
        print(f"❌ [SHEETS ERROR] Не вдалося оновити статус: {e}")

async def update_payment_in_sheet(event_title, order_id, status):
    await asyncio.to_thread(_update_cell_in_sheet, event_title, order_id, 9, status) # Статус тепер у 9 колонці

# --- СКАСУВАННЯ ТА РЕЄСТР ---
def _mark_seat_as_cancelled(event_title, order_id, row_num, seat_num):
    try:
        ws = _get_or_create_worksheet(event_title)
        if not ws: return False
        cells = ws.findall(str(order_id), in_column=1)
        for cell in cells:
            ws.update_cell(cell.row, 9, "🔴 СКАСОВАНО")
        return True
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
        try:
            cell = ws.find(user_tag, in_column=3)
            if cell:
                ws.update(f"A{cell.row}:B{cell.row}", [[last_name, first_name]])
                ws.update(f"D{cell.row}:E{cell.row}", [[institute, group]])
                return
        except gspread.exceptions.CellNotFound:
            pass
        ws.append_row([last_name, first_name, user_tag, institute, group])
    except Exception as e:
        print(f"❌ [SHEETS ERROR] Помилка реєстру: {e}")

async def upsert_user_in_registry(*args):
    await asyncio.to_thread(_upsert_user_in_registry, *args)

# --- СИНХРОНІЗАЦІЯ КОЛЬОРІВ ---
def _get_occupied_from_sheet(event_title):
    client = get_client()
    if not client: return []
    try:
        is_gala = "Гала" in event_title or "Весна" in event_title
        url = os.getenv("SPREADSHEET_GALA_URL") if is_gala else os.getenv("SPREADSHEET_ORGAN_URL")
        doc = client.open_by_url(url)
        
        # Назва вкладки змінена на РОЗСАДКА для Актової зали
        sheet_name = "РОЗСАДКА" if is_gala else "Схема залу"
        ws = doc.worksheet(sheet_name)
        
        all_cells = ws.get_all_cells(get_metadata=True)
        occupied = []
        for r_idx, row_data in enumerate(all_cells, 1):
            for c_idx, cell in enumerate(row_data, 1):
                fmt = cell.get('userEnteredFormat', {})
                bg = fmt.get('backgroundColor', {})
                if bg and (bg.get('red', 1) < 1 or bg.get('green', 1) < 1 or bg.get('blue', 1) < 1):
                    seat_id = translate_coords_to_id(r_idx, c_idx)
                    if seat_id: occupied.append(seat_id)
        return occupied
    except Exception as e:
        print(f"❌ [SHEETS ERROR] Помилка читання кольорів: {e}")
        return []

async def get_occupied_from_sheet(event_title):
    return await asyncio.to_thread(_get_occupied_from_sheet, event_title)