import asyncio
import sys
import os

# Ajustar path para importar app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.infrastructure.database.session import engine, init_db
# Importar modelos para que se registren en Base
from app.infrastructure.database.models import Base

async def reset_tables():
    print("Iniciando reset de tablas de atletas...")
    async with engine.begin() as conn:
        print("Eliminando tablas antiguas...")
        await conn.execute(text("DROP TABLE IF EXISTS public.athletes CASCADE;"))
        await conn.execute(text("DROP TABLE IF EXISTS airtable.athletes CASCADE;"))
        # Tambien limpiar el estado de sync para forzar una sincronizacion fresca
        await conn.execute(text("DELETE FROM public.sync_state WHERE target_table = 'athletes';"))
        
    print("Recreando tablas...")
    await init_db()
    print("Tablas recreadas exitosamente.")

if __name__ == "__main__":
    asyncio.run(reset_tables())
