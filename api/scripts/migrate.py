#!/usr/bin/env python
"""
Script helper para migraciones de base de datos con Alembic.

Uso:
    python scripts/migrate.py upgrade          # Aplicar migraciones pendientes
    python scripts/migrate.py downgrade        # Revertir ultima migracion
    python scripts/migrate.py downgrade -2     # Revertir 2 migraciones
    python scripts/migrate.py revision "desc"  # Crear nueva migracion
    python scripts/migrate.py current          # Ver version actual
    python scripts/migrate.py history          # Ver historial de migraciones
    python scripts/migrate.py heads            # Ver migraciones pendientes

Este script es un wrapper conveniente sobre los comandos de Alembic.
"""
import subprocess
import sys
from pathlib import Path


# Directorio raiz del API
API_DIR = Path(__file__).parent.parent


def run_alembic(args: list) -> int:
    """
    Ejecuta un comando de Alembic.
    
    Args:
        args: Lista de argumentos para Alembic
        
    Returns:
        Codigo de salida del comando
    """
    cmd = ["alembic"] + args
    print(f"Ejecutando: {' '.join(cmd)}")
    print("-" * 50)
    result = subprocess.run(cmd, cwd=API_DIR)
    return result.returncode


def upgrade(target: str = "head") -> int:
    """Aplica migraciones hasta el target especificado."""
    return run_alembic(["upgrade", target])


def downgrade(target: str = "-1") -> int:
    """Revierte migraciones hasta el target especificado."""
    return run_alembic(["downgrade", target])


def revision(message: str, autogenerate: bool = True) -> int:
    """Crea una nueva revision de migracion."""
    args = ["revision", "-m", message]
    if autogenerate:
        args.append("--autogenerate")
    return run_alembic(args)


def current() -> int:
    """Muestra la version actual de la base de datos."""
    return run_alembic(["current"])


def history() -> int:
    """Muestra el historial de migraciones."""
    return run_alembic(["history", "--verbose"])


def heads() -> int:
    """Muestra las migraciones pendientes (heads)."""
    return run_alembic(["heads"])


def show_help():
    """Muestra ayuda de uso."""
    print(__doc__)
    print("\nComandos disponibles:")
    print("  upgrade [target]    - Aplicar migraciones (default: head)")
    print("  downgrade [target]  - Revertir migraciones (default: -1)")
    print("  revision <mensaje>  - Crear nueva migracion con autogenerate")
    print("  current             - Ver version actual")
    print("  history             - Ver historial de migraciones")
    print("  heads               - Ver migraciones pendientes")
    print()


def main():
    """Funcion principal del script."""
    if len(sys.argv) < 2:
        show_help()
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "upgrade":
        target = sys.argv[2] if len(sys.argv) > 2 else "head"
        sys.exit(upgrade(target))
        
    elif command == "downgrade":
        target = sys.argv[2] if len(sys.argv) > 2 else "-1"
        sys.exit(downgrade(target))
        
    elif command == "revision":
        if len(sys.argv) < 3:
            print("Error: Falta mensaje para la revision")
            print("Uso: python scripts/migrate.py revision 'descripcion del cambio'")
            sys.exit(1)
        message = sys.argv[2]
        sys.exit(revision(message))
        
    elif command == "current":
        sys.exit(current())
        
    elif command == "history":
        sys.exit(history())
        
    elif command == "heads":
        sys.exit(heads())
        
    elif command in ["help", "-h", "--help"]:
        show_help()
        sys.exit(0)
        
    else:
        print(f"Comando desconocido: {command}")
        show_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
