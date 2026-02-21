#!/bin/bash
set -e

# Esperar a que la base de datos esté lista (opcional pero recomendado)
# Aquí podrías añadir un ping a la DB si fuera necesario

echo "Ejecutando migraciones de base de datos..."
alembic upgrade head

echo "Iniciando servidor de aplicaciones..."
exec python main.py
