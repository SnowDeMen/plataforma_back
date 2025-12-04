# Guía de Inicio Rápido

## 🚀 Configuración Inicial

### 1. Clonar y Preparar el Entorno

```bash
# Navegar al directorio del proyecto
cd generacion_entrenamientos

# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# En Windows:
venv\Scripts\activate
# En Linux/Mac:
source venv/bin/activate
```

### 2. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 3. Configurar Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto:

```bash
# Copiar el ejemplo
copy .env.example .env  # Windows
# o
cp .env.example .env    # Linux/Mac
```

Edita el archivo `.env` y configura al menos:
- `SECRET_KEY`: Una clave secreta segura
- `OPENAI_API_KEY`: Tu clave de API de OpenAI (si usas AutoGen con OpenAI)

### 4. Inicializar la Base de Datos

```bash
python scripts/init_db.py
```

### 5. Ejecutar el Servidor

```bash
# Opción 1: Usando uvicorn directamente
uvicorn main:app --reload

# Opción 2: Usando el script de desarrollo
python scripts/run_dev.py

# Opción 3: Usando el main.py
python main.py
```

El servidor estará disponible en: `http://localhost:8000`

### 6. Verificar la Instalación

Abre tu navegador y visita:
- **API Docs (Swagger)**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## 📝 Primer Uso

### Crear tu Primer Agente

Usando curl:
```bash
curl -X POST "http://localhost:8000/api/v1/agents/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Mi Primer Agente",
    "type": "assistant",
    "system_message": "Eres un asistente útil y amigable.",
    "configuration": {
      "temperature": 0.7
    }
  }'
```

O usando Python:
```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/agents/",
    json={
        "name": "Mi Primer Agente",
        "type": "assistant",
        "system_message": "Eres un asistente útil y amigable.",
        "configuration": {"temperature": 0.7}
    }
)

print(response.json())
```

### Listar Agentes

```bash
curl http://localhost:8000/api/v1/agents/
```

## 🧪 Ejecutar Tests

```bash
# Todos los tests
pytest

# Solo tests unitarios
pytest tests/unit/

# Con cobertura
pytest --cov=app tests/

# Tests específicos
pytest tests/unit/test_agent_entity.py
```

## 📁 Estructura del Proyecto

```
generacion_entrenamientos/
├── app/                      # Código de la aplicación
│   ├── api/                  # Endpoints REST (Presentación)
│   ├── application/          # Casos de uso (Aplicación)
│   ├── domain/               # Lógica de negocio (Dominio)
│   ├── infrastructure/       # Implementaciones técnicas
│   ├── core/                 # Configuración central
│   └── shared/               # Código compartido
├── tests/                    # Tests
├── scripts/                  # Scripts de utilidad
├── docs/                     # Documentación
├── main.py                   # Punto de entrada
└── requirements.txt          # Dependencias
```

## 🔧 Comandos Útiles

### Desarrollo
```bash
# Servidor con recarga automática
uvicorn main:app --reload

# Servidor en puerto específico
uvicorn main:app --reload --port 8080

# Ver logs detallados
uvicorn main:app --reload --log-level debug
```

### Base de Datos
```bash
# Inicializar/Recrear base de datos
python scripts/init_db.py

# Crear migración (si usas Alembic)
alembic revision --autogenerate -m "descripción"

# Aplicar migraciones
alembic upgrade head
```

### Testing
```bash
# Tests con salida detallada
pytest -v

# Tests con print statements
pytest -s

# Tests específicos por marca
pytest -m unit
pytest -m integration
```

## 🐛 Solución de Problemas

### Error: "ModuleNotFoundError"
```bash
# Asegúrate de estar en el entorno virtual
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Reinstala las dependencias
pip install -r requirements.txt
```

### Error: "Database locked"
```bash
# Elimina la base de datos y recréala
rm app.db  # Linux/Mac
del app.db  # Windows
python scripts/init_db.py
```

### Error: "Port already in use"
```bash
# Usa un puerto diferente
uvicorn main:app --reload --port 8001
```

### Error con AutoGen/OpenAI
```bash
# Verifica que tu API key esté configurada
echo $OPENAI_API_KEY  # Linux/Mac
echo %OPENAI_API_KEY%  # Windows

# O verifica el archivo .env
cat .env  # Linux/Mac
type .env  # Windows
```

## 📚 Próximos Pasos

1. **Explora la documentación**:
   - Lee `docs/ARCHITECTURE.md` para entender la arquitectura
   - Revisa `docs/API_EXAMPLES.md` para más ejemplos de API

2. **Personaliza la configuración**:
   - Edita `app/core/config.py` para ajustar configuraciones
   - Modifica `.env` según tus necesidades

3. **Extiende la funcionalidad**:
   - Añade nuevos endpoints en `app/api/v1/endpoints/`
   - Crea nuevas entidades en `app/domain/entities/`
   - Implementa casos de uso en `app/application/use_cases/`

4. **Conecta con tu frontend React**:
   - Configura CORS en `.env` con la URL de tu frontend
   - Usa los ejemplos de JavaScript en `docs/API_EXAMPLES.md`

## 🤝 Contribuir

Para contribuir al proyecto:
1. Sigue los principios SOLID
2. Documenta tu código en español
3. Escribe tests para nuevas funcionalidades
4. Mantén la estructura de capas

## 📞 Soporte

Si tienes problemas:
1. Revisa la documentación en `/docs`
2. Verifica los logs en `logs/app.log`
3. Consulta los tests como ejemplos de uso

¡Feliz desarrollo! 🎉

