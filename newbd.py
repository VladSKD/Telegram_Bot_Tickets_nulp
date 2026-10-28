import json
import psycopg2
from psycopg2.extras import execute_values
import os

# Встав сюди Connection string від нового проєкту Neon
DATABASE_URL = "postgresql://neondb_owner:npg_2anhJm3GbqLN@ep-green-scene-ba8by5iy-pooler.c-8.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# SQL-запити для створення структури бази даних
CREATE_TABLES_SQL = """
-- Створення таблиці blacklist
CREATE TABLE IF NOT EXISTS blacklist (
    username VARCHAR(255) PRIMARY KEY
);

-- Створення таблиці users
CREATE TABLE IF NOT EXISTS users (
    tg_id BIGINT PRIMARY KEY,
    full_name TEXT,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    institute TEXT,
    student_group TEXT
);

-- Створення таблиці events
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    title TEXT,
    description TEXT,
    date_time TEXT,
    price TEXT,
    bank_link TEXT,
    is_active BOOLEAN,
    card_number TEXT,
    is_free BOOLEAN,
    total_tickets INTEGER,
    success_message TEXT,
    is_fixed_price BOOLEAN,
    location TEXT,
    photo_id TEXT,
    venue_type VARCHAR(50),
    requires_confirmation BOOLEAN,
    available_seats_list TEXT
);

-- Створення таблиці orders
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(tg_id),
    event_id INTEGER REFERENCES events(id),
    ticket_count INTEGER,
    file_id TEXT,
    file_type TEXT,
    status TEXT,
    is_ticket_given BOOLEAN,
    paid_amount DOUBLE PRECISION,
    created_at TIMESTAMP
);

-- Створення таблиці seat_tickets
CREATE TABLE IF NOT EXISTS seat_tickets (
    id SERIAL PRIMARY KEY,
    event_id INTEGER REFERENCES events(id),
    row_num VARCHAR(10),
    seat_num VARCHAR(10),
    file_id TEXT,
    file_type TEXT
);

-- Створення таблиці processed_transactions
CREATE TABLE IF NOT EXISTS processed_transactions (
    tx_id VARCHAR(255) PRIMARY KEY
);
"""

def load_json(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def insert_data(cursor, table_name, data):
    if not data:
        print(f"⚠️ Таблиця {table_name} порожня або немає даних у JSON, пропускаємо.")
        return

    # Отримуємо назви колонок з ключів першого словника
    columns = list(data[0].keys())
    
    # Формуємо SQL запит. ON CONFLICT DO NOTHING уникає дублів
    query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES %s ON CONFLICT DO NOTHING"

    # Витягуємо значення для кожного рядка у правильному порядку
    values = [[row.get(col) for col in columns] for row in data]

    execute_values(cursor, query, values)
    print(f"✅ Вставлено {len(data)} записів у таблицю {table_name}")

def main():
    print("🔄 Підключення до бази даних Neon...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        print("🏗️ Створення таблиць (якщо їх ще немає)...")
        cursor.execute(CREATE_TABLES_SQL)
        conn.commit()
        print("✅ Структура бази даних готова!")

        # Порядок файлів КРИТИЧНО важливий через Foreign Keys
        # Використовуємо нові назви файлів із _2.json
        files_to_import = [
            ('blacklist', 'blacklist.json'),
            ('users', 'users.json'),
            ('events', 'events.json'),
            ('orders', 'orders.json'),
            ('seat_tickets', 'seat_tickets.json'),
            ('processed_transactions', 'processed_transactions.json')
        ]

        print("📥 Початок імпорту даних...")
        for table_name, filename in files_to_import:
            if os.path.exists(filename):
                print(f"Читання {filename}...")
                data = load_json(filename)
                insert_data(cursor, table_name, data)
            else:
                print(f"❌ Файл {filename} не знайдено, пропускаємо.")

        # Зберігаємо всі зміни в базу
        conn.commit()
        print("🎉 Всі таблиці створено та дані успішно імпортовано!")

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        print(f"❌ Сталася помилка під час виконання: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()