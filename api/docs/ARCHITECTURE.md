# Arquitectura del Sistema

## Visión General

Este backend está diseñado siguiendo los principios de **Clean Architecture** y **SOLID**, proporcionando una estructura modular, testeable y mantenible para gestionar agentes de AutoGen.

## Capas de la Arquitectura

### 1. Capa de Dominio (`app/domain/`)

Es el corazón de la aplicación, contiene la lógica de negocio pura.

- **Entidades (`entities/`)**: Objetos de negocio con lógica de dominio
- **Repositorios (`repositories/`)**: Interfaces (contratos) para persistencia
- **Servicios (`services/`)**: Lógica de negocio compleja

**Características:**
- No depende de ninguna otra capa
- Contiene las reglas de negocio fundamentales
- Independiente de frameworks y tecnologías

### 2. Capa de Aplicación (`app/application/`)

Orquesta el flujo de datos entre capas.

- **Casos de Uso (`use_cases/`)**: Implementan las operaciones del sistema
- **DTOs (`dto/`)**: Objetos de transferencia de datos
- **Interfaces (`interfaces/`)**: Contratos de servicios de aplicación

**Características:**
- Coordina entidades y servicios de dominio
- Implementa casos de uso específicos
- Transforma datos entre capas

### 3. Capa de Infraestructura (`app/infrastructure/`)

Implementa detalles técnicos y conexiones externas.

- **Base de Datos (`database/`)**: Configuración y modelos ORM
- **Repositorios (`repositories/`)**: Implementaciones concretas
- **AutoGen (`autogen/`)**: Integración con AutoGen
- **Externos (`external/`)**: APIs y servicios externos

**Características:**
- Implementa interfaces del dominio
- Gestiona persistencia y servicios externos
- Puede ser reemplazada sin afectar el dominio

### 4. Capa de Presentación (`app/api/`)

Expone la funcionalidad a través de una API REST.

- **Endpoints (`v1/endpoints/`)**: Controladores REST
- **Middlewares (`middlewares/`)**: Procesamiento de peticiones
- **Dependencias (`v1/dependencies/`)**: Inyección de dependencias

**Características:**
- Define la interfaz HTTP
- Valida entrada de datos
- Formatea respuestas

### 5. Capa Compartida (`app/shared/`)

Código reutilizable entre capas.

- **Excepciones (`exceptions/`)**: Excepciones personalizadas
- **Utilidades (`utils/`)**: Funciones auxiliares
- **Constantes (`constants/`)**: Valores constantes

## Flujo de Datos

```
Cliente HTTP
    ↓
API Endpoint (Presentación)
    ↓
Caso de Uso (Aplicación)
    ↓
Entidad + Repositorio (Dominio)
    ↓
Implementación Repositorio (Infraestructura)
    ↓
Base de Datos
```

## Principios SOLID Aplicados

### Single Responsibility Principle (SRP)
Cada clase tiene una única razón para cambiar:
- `AgentEntity`: Lógica de negocio de agentes
- `AgentRepository`: Persistencia de agentes
- `AgentUseCases`: Orquestación de operaciones

### Open/Closed Principle (OCP)
Abierto para extensión, cerrado para modificación:
- Interfaces de repositorios permiten nuevas implementaciones
- Nuevos casos de uso sin modificar existentes

### Liskov Substitution Principle (LSP)
Las implementaciones son intercambiables:
- Cualquier implementación de `IAgentRepository` funciona
- Se puede cambiar de SQLite a PostgreSQL sin cambiar lógica

### Interface Segregation Principle (ISP)
Interfaces específicas y pequeñas:
- Repositorios con métodos específicos
- No se fuerza a implementar métodos innecesarios

### Dependency Inversion Principle (DIP)
Dependencias hacia abstracciones:
- Casos de uso dependen de interfaces, no implementaciones
- Inyección de dependencias con FastAPI

## Patrones de Diseño

### Repository Pattern
Abstrae la persistencia de datos.

### Factory Pattern
`AutoGenAgentFactory` para crear agentes.

### Dependency Injection
FastAPI `Depends()` para inyectar dependencias.

### DTO Pattern
Separación entre entidades de dominio y objetos de transferencia.

## Testing

### Tests Unitarios
- Prueban entidades y lógica de dominio
- Sin dependencias externas
- Rápidos y aislados

### Tests de Integración
- Prueban interacción entre capas
- Usan base de datos en memoria
- Verifican flujo completo

### Tests E2E
- Prueban API completa
- Simulan cliente real
- Verifican sistema completo

## Extensibilidad

### Agregar Nueva Entidad

1. Crear entidad en `domain/entities/`
2. Definir interfaz de repositorio en `domain/repositories/`
3. Implementar repositorio en `infrastructure/repositories/`
4. Crear DTOs en `application/dto/`
5. Implementar casos de uso en `application/use_cases/`
6. Crear endpoints en `api/v1/endpoints/`

### Agregar Nuevo Servicio Externo

1. Crear módulo en `infrastructure/external/`
2. Definir interfaz si es necesario
3. Implementar servicio
4. Inyectar en casos de uso

## Mejores Prácticas

1. **Mantener el dominio puro**: Sin dependencias externas
2. **Usar inyección de dependencias**: Facilita testing y mantenimiento
3. **Documentar código**: Docstrings en español
4. **Escribir tests**: Para cada nueva funcionalidad
5. **Seguir convenciones**: Nombres descriptivos y consistentes
6. **Validar datos**: En la capa de presentación y dominio
7. **Manejar errores**: Con excepciones personalizadas
8. **Logging apropiado**: Para debugging y monitoreo

## Configuración

La configuración se gestiona mediante:
- Variables de entorno (`.env`)
- Clase `Settings` con Pydantic
- Valores por defecto seguros

## Seguridad

- Autenticación JWT
- Hashing de contraseñas con bcrypt
- Validación de entrada con Pydantic
- CORS configurado
- Rate limiting (preparado)

## Escalabilidad

La arquitectura permite:
- Escalar horizontalmente (múltiples instancias)
- Cambiar base de datos sin cambiar lógica
- Agregar caché fácilmente
- Implementar message queues
- Microservicios (separar por dominio)

