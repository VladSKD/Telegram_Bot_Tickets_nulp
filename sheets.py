import gspread
from google.oauth2.service_account import Credentials
import asyncio
import os
import json

def get_client():
    creds_dict = json.loads(os.getenv("GOOGLE_CREDS_JSON"))
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

def _get_or_create_worksheet(event_title):
    client = get_client()
    doc = client.open_by_url(os.getenv("SPREADSHEET_URL"))
    try:
        worksheet = doc.worksheet(event_title)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = doc.add_worksheet(title=event_title, rows="1000", cols="8")
        worksheet.append_row(["ID Замовлення", "Прізвище", "Ім'я", "Telegram", "Інститут", "Група", "К-сть квитків", "Статус"])
    return worksheet

def _add_order(event_title, order_id, last_name, first_name, username, institute, group, qty, status):
    ws = _get_or_create_worksheet(event_title)
    ws.append_row([order_id, last_name, first_name, f"@{username}" if username != "-" else "-", institute, group, qty, status])

def _update_cell_in_sheet(event_title, order_id, column_index, new_value):
    ws = _get_or_create_worksheet(event_title)
    # Знаходимо ВСІ рядки з цим ID (бо тепер там є ще й друзі)
    cells = ws.findall(str(order_id), in_column=1)
    for cell in cells:
        ws.update_cell(cell.row, column_index, new_value)

async def add_order_to_sheet(*args):
    await asyncio.to_thread(_add_order, *args)

async def update_payment_in_sheet(event_title, order_id, status):
    await asyncio.to_thread(_update_cell_in_sheet, event_title, order_id, 8, status)
    
def _mark_seat_as_cancelled(event_title, order_id, row_num, seat_num):
    ws = _get_or_create_worksheet(event_title)
    # Знаходимо всі рядки з цим ID замовлення
    cells = ws.findall(str(order_id), in_column=1)
    
    # Шукаємо саме той рядок, де в статусі вказано наше місце
    seat_marker = f"Р{row_num}М{seat_num}"
    
    for cell in cells:
        status_val = ws.cell(cell.row, 8).value # 8 колонка — це Статус
        if seat_marker in status_val:
            ws.update_cell(cell.row, 8, "🔴 СКАСОВАНО")
            return True
    return False

async def cancel_seat_in_sheet(*args):
    await asyncio.to_thread(_mark_seat_as_cancelled, *args)