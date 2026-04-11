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

    async def add_event(self, title, desc, photo_id, dt, venue_type, location, total_tickets, is_free, price, link, card, success_message):
        query = """
        INSERT INTO events (title, description, photo_id, date_time, venue_type, location, total_tickets, is_free, price, bank_link, card_number, success_message) 
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        """
        await self.pool.execute(query, title, desc, photo_id, dt, venue_type, location, total_tickets, is_free, price, link, card, success_message)

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