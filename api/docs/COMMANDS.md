# 🛠️ Comandos Útiles

Referencia rápida de comandos para trabajar con el proyecto.

## 📦 Gestión del Entorno

### Crear y Activar Entorno Virtual

```bash
# Crear entorno virtual
python -m venv venv

# Activar (Windows - PowerShell)
venv\Scripts\Activate.ps1

# Activar (Windows - CMD)
venv\Scripts\activate.bat

# Activar (Linux/Mac)
source venv/bin/activate

# Desactivar
deactivate
```

### Gestión de Dependencias

```bash
# Instalar todas las dependencias
pip install -r requirements.txt

# Instalar una nueva dependencia
pip install nombre-paquete

# Actualizar requirements.txt
pip freeze > requirements.txt

# Actualizar una dependencia específica
pip install --upgrade nombre-paquete

# Ver dependencias instaladas
pip list

# Ver información de un paquete
pip show nombre-paquete
```

## 🚀 Ejecutar el Servidor

### Modo Desarrollo

```bash
# Opción 1: Uvicorn con recarga automática
uvicorn main:app --reload

# Opción 2: Con puerto específico
uvicorn main:app --reload --port 8080

# Opción 3: Con host específico
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Opción 4: Con logs detallados
uvicorn main:app --reload --log-level debug

# Opción 5: Usando el script
python scripts/run_dev.py

# Opción 6: Usando main.py
python main.py
```

### Modo Producción

```bash
# Con múltiples workers
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# Con configuración completa
uvicorn main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --log-level info \
  --access-log
```

## 🗄️ Base de Datos

### Gestión Básica

```bash
# Inicializar base de datos
python scripts/init_db.py

# Eliminar base de datos (Windows)
del app.db

# Eliminar base de datos (Linux/Mac)
rm app.db

# Recrear base de datos
del app.db && python scripts/init_db.py  # Windows
rm app.db && python scripts/init_db.py   # Linux/Mac
```

### Alembic (Migraciones)

```bash
# Inicializar Alembic
alembic init alembic

# Crear nueva migración
alembic revision --autogenerate -m "descripción del cambio"

# Aplicar migraciones
alembic upgrade head

# Revertir última migración
alembic downgrade -1

# Ver historial de migraciones
alembic history

# Ver estado actual
alembic current

# Aplicar migración específica
alembic upgrade <revision_id>
```

## 🧪 Testing

### Ejecutar Tests

```bash
# Todos los tests
pytest

# Tests con salida detallada
pytest -v

# Tests con salida muy detallada
pytest -vv

# Tests mostrando print statements
pytest -s

# Tests específicos por archivo
pytest tests/unit/test_agent_entity.py

# Tests específicos por función
pytest tests/unit/test_agent_entity.py::test_create_agent

# Tests por directorio
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/
```

### Tests con Cobertura

```bash
# Ejecutar con cobertura
pytest --cov=app tests/

# Cobertura con reporte HTML
pytest --cov=app --cov-report=html tests/

# Cobertura con reporte en terminal
pytest --cov=app --cov-report=term-missing tests/

# Cobertura de un módulo específico
pytest --cov=app.domain tests/

# Ver reporte HTML (después de generarlo)
# Windows
start htmlcov/index.html
# Linux
xdg-open htmlcov/index.html
# Mac
open htmlcov/index.html
```

### Tests por Marcadores

```bash
# Solo tests unitarios
pytest -m unit

# Solo tests de integración
pytest -m integration

# Solo tests e2e
pytest -m e2e

# Excluir tests lentos
pytest -m "not slow"
```

### Opciones Avanzadas

```bash
# Detener en el primer fallo
pytest -x

# Detener después de N fallos
pytest --maxfail=3

# Ejecutar tests en paralelo (requiere pytest-xdist)
pytest -n auto

# Ejecutar solo tests que fallaron la última vez
pytest --lf

# Ejecutar tests que fallaron primero
pytest --ff

# Modo watch (requiere pytest-watch)
ptw
```

## 🔍 Linting y Formateo

### Flake8 (Linting)

```bash
# Verificar todo el proyecto
flake8 app/

# Verificar archivo específico
flake8 app/domain/entities/agent.py

# Con configuración personalizada
flake8 --max-line-length=100 app/

# Ignorar errores específicos
flake8 --ignore=E501,W503 app/
```

### Black (Formateo)

```bash
# Formatear todo el proyecto
black app/

# Formatear archivo específico
black app/domain/entities/agent.py

# Ver cambios sin aplicar
black --diff app/

# Verificar sin modificar
black --check app/
```

### isort (Ordenar imports)

```bash
# Ordenar imports en todo el proyecto
isort app/

# Verificar sin modificar
isort --check-only app/

# Ver diferencias
isort --diff app/
```

### mypy (Type Checking)

```bash
# Verificar tipos en todo el proyecto
mypy app/

# Verificar archivo específico
mypy app/domain/entities/agent.py

# Con configuración estricta
mypy --strict app/
```

## 📝 Logs

### Ver Logs

```bash
# Ver logs en tiempo real (Windows)
Get-Content logs/app.log -Wait -Tail 50

# Ver logs en tiempo real (Linux/Mac)
tail -f logs/app.log

# Ver últimas 100 líneas
tail -n 100 logs/app.log  # Linux/Mac
Get-Content logs/app.log -Tail 100  # Windows

# Buscar en logs
grep "ERROR" logs/app.log  # Linux/Mac
Select-String "ERROR" logs/app.log  # Windows

# Limpiar logs (Windows)
del logs\app.log

# Limpiar logs (Linux/Mac)
rm logs/app.log
```

## 🔧 Variables de Entorno

### Gestión de .env

```bash
# Copiar ejemplo
copy .env.example .env  # Windows
cp .env.example .env    # Linux/Mac

# Ver variables de entorno
# Windows
type .env
# Linux/Mac
cat .env

# Editar variables
# Windows
notepad .env
# Linux/Mac
nano .env
# o
vim .env
```

### Cargar Variables

```bash
# Python
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('APP_NAME'))"

# PowerShell (Windows)
Get-Content .env | ForEach-Object {
    $name, $value = $_.split('=')
    Set-Content env:\$name $value
}

# Bash (Linux/Mac)
export $(cat .env | xargs)
```

## 🌐 API Testing

### cURL

```bash
# Health check
curl http://localhost:8000/health

# Crear agente
curl -X POST "http://localhost:8000/api/v1/agents/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Agent",
    "type": "assistant",
    "system_message": "Test"
  }'

# Obtener agente
curl http://localhost:8000/api/v1/agents/1

# Listar agentes
curl http://localhost:8000/api/v1/agents/

# Actualizar agente
curl -X PUT "http://localhost:8000/api/v1/agents/1" \
  -H "Content-Type: application/json" \
  -d '{"status": "running"}'

# Eliminar agente
curl -X DELETE http://localhost:8000/api/v1/agents/1
```

### HTTPie (alternativa más amigable)

```bash
# Instalar
pip install httpie

# Health check
http GET localhost:8000/health

# Crear agente
http POST localhost:8000/api/v1/agents/ \
  name="Test Agent" \
  type="assistant" \
  system_message="Test"

# Obtener agente
http GET localhost:8000/api/v1/agents/1

# Listar agentes
http GET localhost:8000/api/v1/agents/

# Actualizar agente
http PUT localhost:8000/api/v1/agents/1 status="running"

# Eliminar agente
http DELETE localhost:8000/api/v1/agents/1
```

## 🐳 Docker (Futuro)

```bash
# Construir imagen
docker build -t autogen-backend .

# Ejecutar contenedor
docker run -p 8000:8000 autogen-backend

# Con variables de entorno
docker run -p 8000:8000 --env-file .env autogen-backend

# Docker Compose
docker-compose up
docker-compose up -d  # En background
docker-compose down   # Detener
docker-compose logs -f  # Ver logs
```

## 📊 Utilidades

### Información del Sistema

```bash
# Versión de Python
python --version

# Versión de pip
pip --version

# Información del sistema
python -c "import sys; print(sys.version)"

# Información de FastAPI
python -c "import fastapi; print(fastapi.__version__)"

# Listar puertos en uso (Windows)
netstat -ano | findstr :8000

# Listar puertos en uso (Linux/Mac)
lsof -i :8000
```

### Limpieza

```bash
# Eliminar archivos __pycache__ (Windows)
for /d /r . %d in (__pycache__) do @if exist "%d" rd /s /q "%d"

# Eliminar archivos __pycache__ (Linux/Mac)
find . -type d -name "__pycache__" -exec rm -r {} +

# Eliminar archivos .pyc
find . -name "*.pyc" -delete  # Linux/Mac

# Eliminar cobertura
rm -rf htmlcov/ .coverage  # Linux/Mac
rd /s /q htmlcov && del .coverage  # Windows
```

## 🔄 Git (Control de Versiones)

```bash
# Inicializar repositorio
git init

# Ver estado
git status

# Agregar archivos
git add .
git add archivo.py

# Commit
git commit -m "Mensaje descriptivo"

# Ver historial
git log
git log --oneline

# Crear rama
git branch nombre-rama
git checkout -b nombre-rama

# Cambiar de rama
git checkout nombre-rama

# Fusionar rama
git merge nombre-rama

# Ver diferencias
git diff
git diff archivo.py

# Deshacer cambios
git checkout -- archivo.py
git reset HEAD archivo.py
```

## 📦 Construcción y Distribución

```bash
# Crear distribución
python setup.py sdist bdist_wheel

# Instalar en modo desarrollo
pip install -e .

# Generar requirements desde código
pipreqs . --force

# Verificar seguridad de dependencias
pip-audit
# o
safety check
```

## 🎯 Comandos Personalizados

### Scripts Propios

```bash
# Inicializar base de datos
python scripts/init_db.py

# Ejecutar en desarrollo
python scripts/run_dev.py

# Crear usuario admin (ejemplo futuro)
python scripts/create_admin.py

# Seed de datos (ejemplo futuro)
python scripts/seed_data.py
```

## 📱 Monitoreo

```bash
# Ver procesos Python
# Windows
tasklist | findstr python

# Linux/Mac
ps aux | grep python

# Matar proceso por puerto (Windows)
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Matar proceso por puerto (Linux/Mac)
lsof -ti:8000 | xargs kill -9

# Uso de memoria
# Windows
wmic process where name="python.exe" get ProcessId,WorkingSetSize

# Linux/Mac
ps aux | grep python | awk '{print $2, $6}'
```

---

## 🎨 Atajos Útiles

### Desarrollo Rápido

```bash
# Reiniciar servidor rápidamente
# Ctrl+C para detener, luego:
uvicorn main:app --reload

# Limpiar y reiniciar
rm app.db && python scripts/init_db.py && uvicorn main:app --reload

# Tests rápidos
pytest -x -v

# Ver docs
start http://localhost:8000/docs  # Windows
open http://localhost:8000/docs   # Mac
```

### Alias Recomendados (Bash/Zsh)

```bash
# Agregar a ~/.bashrc o ~/.zshrc
alias runserver="uvicorn main:app --reload"
alias test="pytest -v"
alias testcov="pytest --cov=app tests/"
alias initdb="python scripts/init_db.py"
```

### Alias Recomendados (PowerShell)

```powershell
# Agregar a $PROFILE
function runserver { uvicorn main:app --reload }
function test { pytest -v }
function testcov { pytest --cov=app tests/ }
function initdb { python scripts/init_db.py }
```

---

## 💡 Tips

1. **Usa `--reload` solo en desarrollo**: En producción usa workers
2. **Mantén logs limpios**: Rota logs regularmente
3. **Tests antes de commit**: Siempre ejecuta tests antes de hacer commit
4. **Usa virtual env**: Nunca instales paquetes globalmente
5. **Documenta cambios**: Mantén el README actualizado

---

¡Guarda este archivo como referencia rápida! 📚

