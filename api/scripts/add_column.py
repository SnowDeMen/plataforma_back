import asyncio
from sqlalchemy import text
from app.infrastructure.database.session import engine

async def add_column():
    async with engine.begin() as conn:
        try:
            print("Adding athlete_id column to chat_sessions table...")
            await conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS athlete_id VARCHAR(255);"))
            print("Column added successfully.")
        except Exception as e:
            print(f"Error: {e}")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(add_column())
