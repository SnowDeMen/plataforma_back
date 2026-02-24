# Backend - Sistema de Agentes AutoGen

## Descripción
Backend desarrollado con FastAPI para gestionar agentes de AutoGen en Python. Arquitectura basada en principios SOLID y Clean Architecture.

## Estructura del Proyecto

```
generacion_entrenamientos/
├── app/
│   ├── api/                    # Capa de presentación (API REST)
│   │   ├── v1/                 # Versión 1 de la API
│   │   │   ├── endpoints/      # Endpoints específicos
│   │   │   └── dependencies/   # Dependencias de FastAPI
│   │   └── middlewares/        # Middlewares personalizados
│   ├── core/                   # Configuración central
│   │   ├── config.py           # Configuración de la aplicación
│   │   ├── security.py         # Seguridad y autenticación
│   │   └── events.py           # Eventos de inicio/cierre
│   ├── domain/                 # Capa de dominio (lógica de negocio)
│   │   ├── entities/           # Entidades del dominio
│   │   ├── repositories/       # Interfaces de repositorios
│   │   └── services/           # Servicios de dominio
│   ├── infrastructure/         # Capa de infraestructura
│   │   ├── database/           # Configuración de base de datos
│   │   ├── repositories/       # Implementación de repositorios
│   │   ├── external/           # Servicios externos
│   │   └── autogen/            # Integración con AutoGen
│   ├── application/            # Capa de aplicación (casos de uso)
│   │   ├── use_cases/          # Casos de uso específicos
│   │   ├── dto/                # Data Transfer Objects
│   │   └── interfaces/         # Interfaces de servicios
│   └── shared/                 # Código compartido
│       ├── exceptions/         # Excepciones personalizadas
│       ├── utils/              # Utilidades
│       └── constants/          # Constantes
├── tests/                      # Tests unitarios e integración
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── scripts/                    # Scripts de utilidad
├── docs/                       # Documentación adicional
├── .env.example               # Variables de entorno ejemplo
├── requirements.txt           # Dependencias Python
├── main.py                    # Punto de entrada de la aplicación
└── README.md                  # Este archivo
```

## Principios SOLID Aplicados

### Single Responsibility Principle (SRP)
- Cada módulo tiene una única responsabilidad
- Separación clara entre capas: API, Dominio, Aplicación, Infraestructura

### Open/Closed Principle (OCP)
- Uso de interfaces y abstracciones
- Extensible sin modificar código existente

### Liskov Substitution Principle (LSP)
- Implementaciones intercambiables mediante interfaces
- Repositorios y servicios basados en contratos

### Interface Segregation Principle (ISP)
- Interfaces específicas y pequeñas
- Clientes no dependen de métodos que no usan

### Dependency Inversion Principle (DIP)
- Dependencias hacia abstracciones, no implementaciones
- Inyección de dependencias con FastAPI

## Instalación

```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus configuraciones
```

## Ejecución

```bash
# Desarrollo
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Producción
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Testing

```bash
# Ejecutar todos los tests
pytest

# Tests con cobertura
pytest --cov=app tests/

# Tests específicos
pytest tests/unit/
pytest tests/integration/
```

## Documentación API

Una vez iniciado el servidor, accede a:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Tecnologías

- **FastAPI**: Framework web moderno y rápido
- **AutoGen**: Framework para agentes de IA
- **Pydantic**: Validación de datos
- **SQLAlchemy**: ORM para base de datos
- **Alembic**: Migraciones de base de datos
- **pytest**: Framework de testing

## Contribución

1. Cada nueva funcionalidad debe seguir la estructura de capas
2. Mantener los principios SOLID
3. Documentar el código
4. Escribir tests para nuevas funcionalidades

