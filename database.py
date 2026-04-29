import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))
        # Автоматичне створення таблиці для чорного списку
        await self.pool.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                username VARCHAR(255) PRIMARY KEY
            )
        """)
        await self.pool.execute("""
            CREATE TABLE IF NOT EXISTS seat_tickets (
                id SERIAL PRIMARY KEY,
                event_id INT,
                row_num VARCHAR(10),
                seat_num VARCHAR(10),
                file_id TEXT,
                file_type TEXT,
                UNIQUE(event_id, row_num, seat_num)
            )
        """)
        
        # --- ДОДАЄМО КОЛОНКУ ДЛЯ АВТОПІДТВЕРДЖЕННЯ ---
        try:
            await self.pool.execute("ALTER TABLE events ADD COLUMN requires_confirmation BOOLEAN DEFAULT TRUE;")
        except Exception:
            pass # Якщо колонка вже є, ігноруємо помилку
        
        
        
        try:
            await self.pool.execute("ALTER TABLE orders ADD COLUMN paid_amount FLOAT DEFAULT 0.0;")
        except Exception:
            # Якщо колонка вже є, примусово міняємо її тип на FLOAT (щоб підтримувала копійки)
            try:
                await self.pool.execute("ALTER TABLE orders ALTER COLUMN paid_amount TYPE FLOAT;")
            except:
                pass
        
        await self.pool.execute("""
            CREATE TABLE IF NOT EXISTS processed_transactions (
                tx_id VARCHAR(255) PRIMARY KEY
            )
        """)

    async def update_order_paid_amount(self, order_id, amount_uah):
        # Тепер зберігаємо суму з копійками
        await self.pool.execute(
            "UPDATE orders SET paid_amount = paid_amount + $1 WHERE id = $2",
            float(amount_uah), order_id
        )


    # --- ЧОРНИЙ СПИСОК ---
    async def add_to_blacklist(self, username: str):
        username = username.replace("@", "").strip()
        await self.pool.execute("INSERT INTO blacklist (username) VALUES ($1) ON CONFLICT DO NOTHING", username)

    async def remove_from_blacklist(self, username: str):
        username = username.replace("@", "").strip()
        await self.pool.execute("DELETE FROM blacklist WHERE username = $1", username)

    async def is_blacklisted(self, username: str):
        if not username: return False
        username = username.replace("@", "").strip()
        val = await self.pool.fetchval("SELECT 1 FROM blacklist WHERE username = $1", username)
        return bool(val)

    async def get_blacklist(self):
        rows = await self.pool.fetch("SELECT username FROM blacklist")
        return [row['username'] for row in rows]
    # ---------------------
    
    async def add_seat_ticket(self, event_id, row, seat, file_id, file_type):
        await self.pool.execute("""
            INSERT INTO seat_tickets (event_id, row_num, seat_num, file_id, file_type)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (event_id, row_num, seat_num) 
            DO UPDATE SET file_id = EXCLUDED.file_id, file_type = EXCLUDED.file_type
        """, event_id, str(row), str(seat), file_id, file_type)

    async def get_seat_ticket(self, event_id, row, seat):
        return await self.pool.fetchrow(
            "SELECT file_id, file_type FROM seat_tickets WHERE event_id = $1 AND row_num = $2 AND seat_num = $3", 
            event_id, str(row), str(seat)
        )
        
    async def register_full_user(self, tg_id, username, first_name, last_name, institute, group):
        query = """
        INSERT INTO users (tg_id, username, first_name, last_name, institute, student_group) 
        VALUES ($1, $2, $3, $4, $5, $6) 
        ON CONFLICT (tg_id) DO UPDATE SET 
            first_name = EXCLUDED.first_name, 
            last_name = EXCLUDED.last_name, 
            institute = EXCLUDED.institute, 
            student_group = EXCLUDED.student_group
        """
        await self.pool.execute(query, tg_id, username, first_name, last_name, institute, group)

    async def add_event(self, title, desc, photo_id, dt, venue_type, location, total_tickets, is_free, price, link, card, success_message, requires_confirmation=True):
        query = """
        INSERT INTO events (title, description, photo_id, date_time, venue_type, location, total_tickets, is_free, price, bank_link, card_number, success_message, requires_confirmation) 
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        """
        await self.pool.execute(query, title, desc, photo_id, dt, venue_type, location, total_tickets, is_free, price, link, card, success_message, requires_confirmation)
        
    async def get_event(self, event_id):
        query = """
        SELECT e.*, 
        (e.total_tickets - COALESCE((SELECT SUM(ticket_count) FROM orders WHERE event_id = e.id AND status = 'confirmed'), 0)) AS remaining_tickets
        FROM events e WHERE e.id = $1
        """
        return await self.pool.fetchrow(query, event_id)

    async def get_user(self, tg_id):
        return await self.pool.fetchrow("SELECT * FROM users WHERE tg_id = $1", tg_id)

    async def get_active_events(self):
        query = """
        SELECT e.*, 
        (e.total_tickets - COALESCE((SELECT SUM(ticket_count) FROM orders WHERE event_id = e.id AND status = 'confirmed'), 0)) AS remaining_tickets
        FROM events e WHERE e.is_active = TRUE
        """
        return await self.pool.fetch(query)

    async def delete_event(self, event_id):
        await self.pool.execute("UPDATE events SET is_active = FALSE WHERE id = $1", event_id)
        
    async def update_event_field(self, event_id, field_name, new_value):
        allowed_fields = ['title', 'description', 'photo_id', 'date_time', 'location', 'total_tickets', 'price', 'bank_link', 'card_number', 'success_message']
        if field_name in allowed_fields:
            query = f"UPDATE events SET {field_name} = $1 WHERE id = $2"
            await self.pool.execute(query, new_value, event_id)

    async def add_order(self, user_id, event_id, count, file_id, f_type):
        return await self.pool.fetchval(
            "INSERT INTO orders (user_id, event_id, ticket_count, file_id, file_type) VALUES ($1, $2, $3, $4, $5) RETURNING id",
            user_id, event_id, count, file_id, f_type
        )

    async def update_order_status(self, order_id, status):
        await self.pool.execute("UPDATE orders SET status = $1 WHERE id = $2", status, order_id)

    async def get_order(self, order_id):
        return await self.pool.fetchrow("SELECT * FROM orders WHERE id = $1", order_id)
    
    # --- НОВА ФУНКЦІЯ ДЛЯ МІСЦЬ ---
    async def get_occupied_seats(self, event_id):
        # Дістаємо всі збережені місця для конкретної події
        query = "SELECT file_id FROM orders WHERE event_id = $1 AND file_type = 'organ_seats' AND status = 'confirmed'"
        rows = await self.pool.fetch(query, event_id)
        seats = []
        for row in rows:
            if row['file_id']:
                seats.extend(row['file_id'].split(','))
        return seats
    
    async def get_seat_info(self, event_id, row, seat):
        query = """
        SELECT o.id as order_id, o.user_id, u.first_name, u.last_name, u.username, u.institute, u.student_group, o.file_id
        FROM orders o
        JOIN users u ON o.user_id = u.tg_id
        WHERE o.event_id = $1 AND o.file_type = 'organ_seats' AND o.status = 'confirmed'
        """
        rows = await self.pool.fetch(query, event_id)
        target_seat = f"{row}-{seat}"
        for r in rows:
            if r['file_id'] and target_seat in r['file_id'].split(','):
                return r
        return None

    # --- ВИДАЛЕННЯ КВИТКА ДЛЯ АДМІНА ---
    async def remove_seat_from_order(self, order_id, row, seat):
        order = await self.get_order(order_id)
        if not order or not order['file_id']: return False
        
        seats = order['file_id'].split(',')
        target_seat = f"{row}-{seat}"
        
        if target_seat in seats:
            seats.remove(target_seat)
            new_file_id = ",".join(seats) if seats else None
            new_count = order['ticket_count'] - 1

            if new_count == 0:
                # Якщо це був останній/єдиний квиток, скасовуємо все замовлення
                await self.pool.execute("UPDATE orders SET status = 'cancelled', file_id = NULL, ticket_count = 0 WHERE id = $1", order_id)
            else:
                # Якщо там ще є квитки друзів, оновлюємо рядок
                await self.pool.execute("UPDATE orders SET file_id = $1, ticket_count = $2 WHERE id = $3", new_file_id, new_count, order_id)
            return True
        return False
    
    
    async def update_user_field(self, tg_id: int, field_name: str, new_value: str):
        db_columns = {
            "last_name": "last_name",
            "first_name": "first_name",
            "institute": "institute",
            "group": "student_group"
        }
        column = db_columns.get(field_name)
        if not column: return  
        query = f"UPDATE users SET {column} = $1 WHERE tg_id = $2"
        await self.pool.execute(query, new_value, tg_id)
        
    async def get_all_users(self):
        return await self.pool.fetch("SELECT tg_id FROM users")

    async def get_users_by_event(self, event_id):
        query = """
        SELECT DISTINCT user_tg_id as tg_id 
        FROM orders 
        WHERE event_id = $1 AND status = 'confirmed'
        """
        return await self.pool.fetch(query, event_id)
    
    async def attach_proof_to_order(self, order_id, file_id, f_type):
        # Оновлюємо замовлення, додаючи файл і міняючи статус на "pending_manual"
        await self.pool.execute(
            "UPDATE orders SET file_id = $1, file_type = $2, status = 'pending_manual' WHERE id = $3",
            file_id, f_type, order_id
        )
        
    async def is_transaction_processed(self, tx_id: str):
        val = await self.pool.fetchval("SELECT 1 FROM processed_transactions WHERE tx_id = $1", tx_id)
        return bool(val)

    async def mark_transaction_processed(self, tx_id: str):
        await self.pool.execute("INSERT INTO processed_transactions (tx_id) VALUES ($1) ON CONFLICT DO NOTHING", tx_id)