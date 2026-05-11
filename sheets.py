import gspread
from google.oauth2.service_account import Credentials
import asyncio
import os
import json
import re

# --- МАПІНГ СЕКТОРІВ (ДЛЯ ОРГАННОГО ЗАЛУ) ---
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

def _get_or_create_worksheet(event_title, venue_type):
    client = get_client()
    if not client: return None
    try:
        url = "https://docs.google.com/spreadsheets/d/1CYx4V7_p7keMeKUy2Q_5Rtzy8OuehsifceVTObFD5cQ/edit"
        doc = client.open_by_url(url)
        try:
            worksheet = doc.worksheet(event_title)
        except gspread.exceptions.WorksheetNotFound:
            # Чіткий поділ структури
            if venue_type in ['organ_hall', 'assembly_hall']:
                headers = ["ID Замовлення", "Прізвище", "Ім'я", "Telegram", "Інститут", "Сектор", "Ряд", "Місце", "Статус", "Квиток забрано"]
                cols = 10
            else:
                headers = ["ID Замовлення", "Прізвище", "Ім'я", "Telegram", "Інститут", "Група", "К-сть квитків", "Статус"]
                cols = 8
            
            worksheet = doc.add_worksheet(title=event_title, rows="1000", cols=str(cols))
            worksheet.append_row(headers)
        return worksheet
    except Exception as e:
        print(f"❌ [SHEETS ERROR] Не вдалося відкрити таблицю: {e}")
        return None

def _add_order(event_title, order_id, last_name, first_name, username, institute, group, qty, status, venue_type):
    try:
        ws = _get_or_create_worksheet(event_title, venue_type)
        if not ws: return

        tg = f"@{username}" if username != "-" else "-"
        
        if venue_type in ['organ_hall', 'assembly_hall']:
            row_v, seat_v = "-", "-"
            # 🌟 ОНОВЛЕНИЙ REGEX: додано [0-9А-Яа-я], щоб розуміти ряди 12А, 5Б тощо
            match = re.search(r'Р([0-9А-Яа-я]+)М(\d+)', status)
            if match:
                row_v, seat_v = match.group(1), match.group(2)
            
            # 🌟 ЗАМІСТЬ "-" СТАВИМО group (це буде наш сектор)
            ws.append_row([order_id, last_name, first_name, tg, institute, group, row_v, seat_v, status, "Ні"])
        else:
            ws.append_row([order_id, last_name, first_name, tg, institute, group, qty, status])
    except Exception as e:
        print(f"❌ Помилка запису замовлення: {e}")

async def add_order_to_sheet(*args):
    await asyncio.to_thread(_add_order, *args)

def _update_cell_in_sheet(event_title, order_id, status, venue_type):
    try:
        ws = _get_or_create_worksheet(event_title, venue_type)
        if not ws: return
        
        cells = ws.findall(str(order_id), in_column=1)
        if not cells: return

        # Визначаємо колонку статусу: 9-та для залів, 8-ма для звичайних
        status_col = 9 if venue_type in ['organ_hall', 'assembly_hall'] else 8

        for cell in cells:
            ws.update_cell(cell.row, status_col, status)
    except Exception as e:
        print(f"❌ [SHEETS ERROR] Помилка оновлення: {e}")

async def update_payment_in_sheet(event_title, order_id, status, venue_type):
    await asyncio.to_thread(_update_cell_in_sheet, event_title, order_id, status, venue_type)

async def cancel_seat_in_sheet(event_title, order_id, row, seat, venue_type):
    await asyncio.to_thread(_update_cell_in_sheet, event_title, order_id, "🔴 СКАСОВАНО", venue_type)

def _get_occupied_from_sheet(event_title, venue_type):
    client = get_client()
    if not client: return []
    try:
        url = "https://docs.google.com/spreadsheets/d/1CYx4V7_p7keMeKUy2Q_5Rtzy8OuehsifceVTObFD5cQ/edit"
        sheet_name = "РОЗСАДКА" if venue_type == 'assembly_hall' else "Схема залу"
        doc = client.open_by_url(url)
        ws = doc.worksheet(sheet_name)
        res = doc.fetch_sheet_metadata({'includeGridData': True})
        sheet_data = next(s for s in res['sheets'] if s['properties']['title'] == sheet_name)
        row_data = sheet_data['data'][0].get('rowData', [])
        occupied = []
        for r_idx, row in enumerate(row_data, 1):
            values = row.get('values', [])
            for c_idx, cell in enumerate(values, 1):
                bg = cell.get('userEnteredFormat', {}).get('backgroundColor', {})
                if bg and (bg.get('red', 1) < 1 or bg.get('green', 1) < 1 or bg.get('blue', 1) < 1):
                    seat_id = translate_coords_to_id(r_idx, c_idx)
                    if seat_id: occupied.append(seat_id)
        return occupied
    except: return []

async def get_occupied_from_sheet(event_title, venue_type):
    return await asyncio.to_thread(_get_occupied_from_sheet, event_title, venue_type)

async def upsert_user_in_registry(last_name, first_name, username, institute, group):
    await asyncio.to_thread(_upsert_user_in_registry, last_name, first_name, username, institute, group)

def _upsert_user_in_registry(last_name, first_name, username, institute, group):
    try:
        client = get_client()
        if not client: return
        doc = client.open_by_url("https://docs.google.com/spreadsheets/d/1CYx4V7_p7keMeKUy2Q_5Rtzy8OuehsifceVTObFD5cQ/edit")
        ws = doc.sheet1 
        tag = f"@{username}" if username else "-"
        try:
            cell = ws.find(tag, in_column=3)
            if cell:
                ws.update(f"A{cell.row}:B{cell.row}", [[last_name, first_name]])
                ws.update(f"D{cell.row}:E{cell.row}", [[institute, group]])
                return
        except: pass
        ws.append_row([last_name, first_name, tag, institute, group])
    except: pass