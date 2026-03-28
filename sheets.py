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
        worksheet = doc.add_worksheet(title=event_title, rows="1000", cols="10")
        worksheet.append_row(["ID Замовлення", "Прізвище", "Ім'я", "Telegram", "Інститут", "Група", "К-сть квитків", "Статус оплати", "Видано квитки"])
    return worksheet

def _add_order(event_title, order_id, last_name, first_name, username, institute, group, qty, status):
    ws = _get_or_create_worksheet(event_title)
    ws.append_row([order_id, last_name, first_name, f"@{username}", institute, group, qty, status, "Ні"])

def _update_cell_in_sheet(event_title, order_id, column_index, new_value):
    ws = _get_or_create_worksheet(event_title)
    cell = ws.find(str(order_id), in_column=1)
    if cell:
        ws.update_cell(cell.row, column_index, new_value)

async def add_order_to_sheet(*args):
    await asyncio.to_thread(_add_order, *args)

async def update_payment_in_sheet(event_title, order_id, status):
    await asyncio.to_thread(_update_cell_in_sheet, event_title, order_id, 8, status)

async def update_ticket_in_sheet(event_title, order_id, status):
    await asyncio.to_thread(_update_cell_in_sheet, event_title, order_id, 9, status)