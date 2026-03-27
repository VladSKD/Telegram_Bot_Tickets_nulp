import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        # Підключення до твого Neon
        self.pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))

    # --- Секція Подій ---
    async def add_event(self, title, desc, dt, price, link):
        query = "INSERT INTO events (title, description, date_time, price, bank_link) VALUES ($1, $2, $3, $4, $5)"
        await self.pool.execute(query, title, desc, dt, price, link)

    async def get_active_events(self):
        return await self.pool.fetch("SELECT * FROM events WHERE is_active = TRUE")

    async def delete_event(self, event_id):
        await self.pool.execute("UPDATE events SET is_active = FALSE WHERE id = $1", event_id)

    # --- Секція Замовлень ---
    async def add_order(self, user_id, event_id, count, file_id, f_type):
        return await self.pool.fetchval(
            "INSERT INTO orders (user_id, event_id, ticket_count, file_id, file_type) VALUES ($1, $2, $3, $4, $5) RETURNING id",
            user_id, event_id, count, file_id, f_type
        )

    async def update_order_status(self, order_id, status):
        await self.pool.execute("UPDATE orders SET status = $1 WHERE id = $2", status, order_id)

    async def get_order(self, order_id):
        return await self.pool.fetchrow("SELECT * FROM orders WHERE id = $1", order_id)