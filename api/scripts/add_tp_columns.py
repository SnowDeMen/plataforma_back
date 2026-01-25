"""
Migracion: Agregar columnas de TrainingPeaks a la tabla athletes.

Agrega las columnas:
- tp_username: Cuenta TrainingPeaks (sincronizada desde Airtable)
- tp_name: Nombre del atleta validado en TrainingPeaks

Uso:
    python scripts/add_tp_columns.py
"""
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.infrastructure.database.session import engine


async def add_tp_columns():
    """Agrega columnas tp_username y tp_name a la tabla athletes."""
    async with engine.begin() as conn:
        try:
            print("Agregando columna tp_username a athletes...")
            await conn.execute(text(
                "ALTER TABLE athletes ADD COLUMN IF NOT EXISTS tp_username VARCHAR;"
            ))
            print("  -> tp_username agregada.")
            
            print("Agregando columna tp_name a athletes...")
            await conn.execute(text(
                "ALTER TABLE athletes ADD COLUMN IF NOT EXISTS tp_name VARCHAR;"
            ))
            print("  -> tp_name agregada.")
            
            print("\nMigracion completada exitosamente.")
            print("Ahora ejecuta el sync de Airtable para poblar tp_username:")
            print("  python scripts/airtable_to_postgres_sync.py")
            
        except Exception as e:
            print(f"Error en migracion: {e}")
            raise
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(add_tp_columns())
