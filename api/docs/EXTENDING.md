# Guía para Extender el Proyecto

Esta guía te muestra cómo agregar nuevas funcionalidades manteniendo los principios SOLID y Clean Architecture.

## Tabla de Contenidos

1. [Agregar una Nueva Entidad](#agregar-una-nueva-entidad)
2. [Agregar un Nuevo Endpoint](#agregar-un-nuevo-endpoint)
3. [Agregar un Servicio Externo](#agregar-un-servicio-externo)
4. [Agregar Validaciones Personalizadas](#agregar-validaciones-personalizadas)
5. [Agregar Middleware](#agregar-middleware)
6. [Agregar Tests](#agregar-tests)

---

## Agregar una Nueva Entidad

Ejemplo: Agregar una entidad `Training` para gestionar entrenamientos.

### 1. Crear la Entidad de Dominio

**Archivo**: `app/domain/entities/training.py`

```python
"""
Entidad de dominio: Training (Entrenamiento).
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class Training:
    """
    Entidad que representa un entrenamiento de agentes.
    """
    
    id: Optional[int] = None
    name: str = ""
    description: Optional[str] = None
    conversation_id: Optional[int] = None
    configuration: Dict[str, Any] = field(default_factory=dict)
    results: Optional[Dict[str, Any]] = None
    status: str = "pending"
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Validaciones después de la inicialización."""
        if not self.name:
            raise ValueError("El nombre del entrenamiento no puede estar vacío")
    
    def start(self) -> None:
        """Inicia el entrenamiento."""
        self.status = "running"
    
    def complete(self, results: Dict[str, Any]) -> None:
        """Completa el entrenamiento con resultados."""
        self.status = "completed"
        self.results = results
        self.completed_at = datetime.utcnow()
    
    def fail(self, error: str) -> None:
        """Marca el entrenamiento como fallido."""
        self.status = "failed"
        self.results = {"error": error}
        self.completed_at = datetime.utcnow()
```

### 2. Crear la Interfaz del Repositorio

**Archivo**: `app/domain/repositories/training_repository.py`

```python
"""
Interfaz del repositorio de entrenamientos.
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from app.domain.entities.training import Training


class ITrainingRepository(ABC):
    """Interfaz del repositorio de entrenamientos."""
    
    @abstractmethod
    async def create(self, training: Training) -> Training:
        """Crea un nuevo entrenamiento."""
        pass
    
    @abstractmethod
    async def get_by_id(self, training_id: int) -> Optional[Training]:
        """Obtiene un entrenamiento por ID."""
        pass
    
    @abstractmethod
    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Training]:
        """Lista todos los entrenamientos."""
        pass
    
    @abstractmethod
    async def update(self, training: Training) -> Training:
        """Actualiza un entrenamiento."""
        pass
    
    @abstractmethod
    async def delete(self, training_id: int) -> bool:
        """Elimina un entrenamiento."""
        pass
```

### 3. Implementar el Repositorio

**Archivo**: `app/infrastructure/repositories/training_repository_impl.py`

```python
"""
Implementación del repositorio de entrenamientos.
"""
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories.training_repository import ITrainingRepository
from app.domain.entities.training import Training
from app.infrastructure.database.models import TrainingModel


class TrainingRepositoryImpl(ITrainingRepository):
    """Implementación del repositorio con SQLAlchemy."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, training: Training) -> Training:
        """Crea un nuevo entrenamiento."""
        db_training = TrainingModel(
            name=training.name,
            description=training.description,
            conversation_id=training.conversation_id,
            configuration=training.configuration,
            status=training.status
        )
        
        self.session.add(db_training)
        await self.session.flush()
        await self.session.refresh(db_training)
        
        return self._to_entity(db_training)
    
    # ... implementar otros métodos ...
    
    @staticmethod
    def _to_entity(db_training: TrainingModel) -> Training:
        """Convierte modelo DB a entidad."""
        return Training(
            id=db_training.id,
            name=db_training.name,
            description=db_training.description,
            conversation_id=db_training.conversation_id,
            configuration=db_training.configuration or {},
            results=db_training.results,
            status=db_training.status,
            created_at=db_training.created_at,
            completed_at=db_training.completed_at
        )
```

### 4. Crear DTOs

**Archivo**: `app/application/dto/training_dto.py`

```python
"""
DTOs para entrenamientos.
"""
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class TrainingCreateDTO(BaseModel):
    """DTO para crear un entrenamiento."""
    
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    conversation_id: Optional[int] = None
    configuration: Dict[str, Any] = Field(default_factory=dict)


class TrainingResponseDTO(BaseModel):
    """DTO de respuesta para un entrenamiento."""
    
    id: int
    name: str
    description: Optional[str]
    conversation_id: Optional[int]
    configuration: Dict[str, Any]
    results: Optional[Dict[str, Any]]
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True
```

### 5. Crear Casos de Uso

**Archivo**: `app/application/use_cases/training_use_cases.py`

```python
"""
Casos de uso para entrenamientos.
"""
from typing import List

from app.domain.repositories.training_repository import ITrainingRepository
from app.domain.entities.training import Training
from app.application.dto.training_dto import (
    TrainingCreateDTO,
    TrainingResponseDTO
)
from app.shared.exceptions.domain import EntityNotFoundException


class TrainingUseCases:
    """Casos de uso para entrenamientos."""
    
    def __init__(self, training_repository: ITrainingRepository):
        self.training_repository = training_repository
    
    async def create_training(self, dto: TrainingCreateDTO) -> TrainingResponseDTO:
        """Crea un nuevo entrenamiento."""
        training = Training(
            name=dto.name,
            description=dto.description,
            conversation_id=dto.conversation_id,
            configuration=dto.configuration
        )
        
        created = await self.training_repository.create(training)
        return self._to_response_dto(created)
    
    # ... implementar otros casos de uso ...
    
    @staticmethod
    def _to_response_dto(training: Training) -> TrainingResponseDTO:
        """Convierte entidad a DTO."""
        return TrainingResponseDTO(
            id=training.id,
            name=training.name,
            description=training.description,
            conversation_id=training.conversation_id,
            configuration=training.configuration,
            results=training.results,
            status=training.status,
            created_at=training.created_at,
            completed_at=training.completed_at
        )
```

### 6. Crear Dependencias

**Archivo**: `app/api/v1/dependencies/training_deps.py`

```python
"""
Dependencias para entrenamientos.
"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_db
from app.infrastructure.repositories.training_repository_impl import TrainingRepositoryImpl
from app.application.use_cases.training_use_cases import TrainingUseCases


async def get_training_repository(
    session: AsyncSession = Depends(get_db)
) -> TrainingRepositoryImpl:
    """Obtiene el repositorio de entrenamientos."""
    return TrainingRepositoryImpl(session)


async def get_training_use_cases(
    repository = Depends(get_training_repository)
) -> TrainingUseCases:
    """Obtiene los casos de uso de entrenamientos."""
    return TrainingUseCases(repository)
```

### 7. Crear Endpoints

**Archivo**: `app/api/v1/endpoints/trainings.py`

```python
"""
Endpoints para entrenamientos.
"""
from typing import List
from fastapi import APIRouter, Depends, status

from app.application.use_cases.training_use_cases import TrainingUseCases
from app.application.dto.training_dto import (
    TrainingCreateDTO,
    TrainingResponseDTO
)
from app.api.v1.dependencies.training_deps import get_training_use_cases


router = APIRouter(prefix="/trainings", tags=["Trainings"])


@router.post(
    "/",
    response_model=TrainingResponseDTO,
    status_code=status.HTTP_201_CREATED
)
async def create_training(
    dto: TrainingCreateDTO,
    use_cases: TrainingUseCases = Depends(get_training_use_cases)
) -> TrainingResponseDTO:
    """Crea un nuevo entrenamiento."""
    return await use_cases.create_training(dto)


@router.get("/{training_id}", response_model=TrainingResponseDTO)
async def get_training(
    training_id: int,
    use_cases: TrainingUseCases = Depends(get_training_use_cases)
) -> TrainingResponseDTO:
    """Obtiene un entrenamiento por ID."""
    return await use_cases.get_training(training_id)
```

### 8. Registrar el Router

**Archivo**: `app/api/v1/router.py`

```python
from app.api.v1.endpoints import agents, trainings  # Agregar import

api_router = APIRouter(prefix="/v1")

api_router.include_router(agents.router)
api_router.include_router(trainings.router)  # Agregar esta línea
```

---

## Agregar un Nuevo Endpoint

Para agregar un endpoint a un recurso existente:

### Ejemplo: Endpoint para activar un agente

**Archivo**: `app/api/v1/endpoints/agents.py`

```python
@router.post(
    "/{agent_id}/activate",
    response_model=AgentResponseDTO,
    summary="Activar un agente"
)
async def activate_agent(
    agent_id: int,
    use_cases: AgentUseCases = Depends(get_agent_use_cases)
) -> AgentResponseDTO:
    """Activa un agente cambiando su estado a RUNNING."""
    return await use_cases.activate_agent(agent_id)
```

**Agregar el caso de uso en**: `app/application/use_cases/agent_use_cases.py`

```python
async def activate_agent(self, agent_id: int) -> AgentResponseDTO:
    """Activa un agente."""
    agent = await self.agent_repository.get_by_id(agent_id)
    
    if agent is None:
        raise EntityNotFoundException("Agent", agent_id)
    
    agent.activate()  # Método de la entidad
    updated = await self.agent_repository.update(agent)
    
    return self._to_response_dto(updated)
```

---

## Agregar un Servicio Externo

### Ejemplo: Integración con servicio de email

**Archivo**: `app/infrastructure/external/email_service.py`

```python
"""
Servicio para envío de emails.
"""
from typing import List
from abc import ABC, abstractmethod


class IEmailService(ABC):
    """Interfaz del servicio de email."""
    
    @abstractmethod
    async def send_email(
        self,
        to: List[str],
        subject: str,
        body: str
    ) -> bool:
        """Envía un email."""
        pass


class EmailService(IEmailService):
    """Implementación del servicio de email."""
    
    def __init__(self, smtp_host: str, smtp_port: int):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
    
    async def send_email(
        self,
        to: List[str],
        subject: str,
        body: str
    ) -> bool:
        """Envía un email usando SMTP."""
        # Implementación real aquí
        print(f"Enviando email a {to}: {subject}")
        return True
```

**Usar en casos de uso**:

```python
class TrainingUseCases:
    def __init__(
        self,
        training_repository: ITrainingRepository,
        email_service: IEmailService
    ):
        self.training_repository = training_repository
        self.email_service = email_service
    
    async def complete_training(self, training_id: int):
        """Completa un entrenamiento y notifica por email."""
        training = await self.training_repository.get_by_id(training_id)
        training.complete(results={})
        
        await self.training_repository.update(training)
        
        # Enviar notificación
        await self.email_service.send_email(
            to=["admin@example.com"],
            subject=f"Entrenamiento {training.name} completado",
            body="El entrenamiento ha finalizado exitosamente."
        )
```

---

## Agregar Validaciones Personalizadas

### Ejemplo: Validador personalizado para configuración de agente

**Archivo**: `app/shared/utils/validators.py`

```python
"""
Validadores personalizados.
"""
from typing import Dict, Any


class AgentConfigValidator:
    """Validador de configuración de agentes."""
    
    @staticmethod
    def validate(config: Dict[str, Any]) -> bool:
        """
        Valida la configuración de un agente.
        
        Raises:
            ValueError: Si la configuración es inválida
        """
        if "temperature" in config:
            temp = config["temperature"]
            if not isinstance(temp, (int, float)) or temp < 0 or temp > 2:
                raise ValueError("Temperature debe estar entre 0 y 2")
        
        if "max_tokens" in config:
            tokens = config["max_tokens"]
            if not isinstance(tokens, int) or tokens < 1:
                raise ValueError("max_tokens debe ser un entero positivo")
        
        return True
```

**Usar en casos de uso**:

```python
from app.shared.utils.validators import AgentConfigValidator

async def create_agent(self, dto: AgentCreateDTO) -> AgentResponseDTO:
    """Crea un nuevo agente con validación."""
    # Validar configuración
    AgentConfigValidator.validate(dto.configuration)
    
    # Continuar con la creación...
```

---

## Agregar Middleware

### Ejemplo: Middleware de logging de requests

**Archivo**: `app/api/middlewares/request_logger.py`

```python
"""
Middleware para logging de requests.
"""
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """Middleware que registra todas las peticiones."""
    
    async def dispatch(self, request: Request, call_next):
        """Procesa y registra la petición."""
        start_time = time.time()
        
        # Log de la petición entrante
        logger.info(f"Request: {request.method} {request.url.path}")
        
        # Procesar petición
        response = await call_next(request)
        
        # Calcular tiempo de procesamiento
        process_time = time.time() - start_time
        
        # Log de la respuesta
        logger.info(
            f"Response: {response.status_code} "
            f"Time: {process_time:.3f}s"
        )
        
        return response
```

**Registrar en**: `main.py`

```python
from app.api.middlewares.request_logger import RequestLoggerMiddleware

application.add_middleware(RequestLoggerMiddleware)
```

---

## Agregar Tests

### Test Unitario para Entidad

**Archivo**: `tests/unit/test_training_entity.py`

```python
"""
Tests unitarios para la entidad Training.
"""
import pytest
from app.domain.entities.training import Training


def test_create_training():
    """Test de creación de un entrenamiento."""
    training = Training(
        name="Test Training",
        description="Test description"
    )
    
    assert training.name == "Test Training"
    assert training.status == "pending"


def test_training_start():
    """Test de inicio de entrenamiento."""
    training = Training(name="Test")
    training.start()
    
    assert training.status == "running"


def test_training_complete():
    """Test de completar entrenamiento."""
    training = Training(name="Test")
    results = {"accuracy": 0.95}
    training.complete(results)
    
    assert training.status == "completed"
    assert training.results == results
    assert training.completed_at is not None
```

### Test de Integración

**Archivo**: `tests/integration/test_training_repository.py`

```python
"""
Tests de integración para TrainingRepository.
"""
import pytest
from app.domain.entities.training import Training
from app.infrastructure.repositories.training_repository_impl import TrainingRepositoryImpl


@pytest.mark.asyncio
async def test_create_training(db_session):
    """Test de creación en base de datos."""
    repository = TrainingRepositoryImpl(db_session)
    
    training = Training(
        name="Test Training",
        description="Test"
    )
    
    created = await repository.create(training)
    
    assert created.id is not None
    assert created.name == "Test Training"


@pytest.mark.asyncio
async def test_get_training_by_id(db_session):
    """Test de obtención por ID."""
    repository = TrainingRepositoryImpl(db_session)
    
    # Crear
    training = Training(name="Test")
    created = await repository.create(training)
    
    # Obtener
    found = await repository.get_by_id(created.id)
    
    assert found is not None
    assert found.id == created.id
```

### Test E2E para API

**Archivo**: `tests/e2e/test_trainings_api.py`

```python
"""
Tests E2E para endpoints de trainings.
"""
import pytest
from httpx import AsyncClient
from main import app


@pytest.mark.asyncio
async def test_create_training_endpoint():
    """Test del endpoint de creación."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/trainings/",
            json={
                "name": "Test Training",
                "description": "Test",
                "configuration": {}
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Training"
        assert "id" in data
```

---

## Mejores Prácticas

1. **Siempre sigue el flujo de capas**: API → Aplicación → Dominio → Infraestructura
2. **Mantén el dominio puro**: Sin dependencias externas
3. **Usa inyección de dependencias**: Para facilitar testing
4. **Documenta tu código**: Docstrings en español
5. **Escribe tests**: Para cada nueva funcionalidad
6. **Valida en múltiples capas**: Presentación y dominio
7. **Usa tipos**: Type hints en Python
8. **Maneja errores apropiadamente**: Excepciones personalizadas

---

## Checklist para Nueva Funcionalidad

- [ ] Entidad de dominio creada
- [ ] Interfaz de repositorio definida
- [ ] Repositorio implementado
- [ ] Modelo de base de datos creado (si aplica)
- [ ] DTOs creados
- [ ] Casos de uso implementados
- [ ] Dependencias configuradas
- [ ] Endpoints creados
- [ ] Router registrado
- [ ] Tests unitarios escritos
- [ ] Tests de integración escritos
- [ ] Tests E2E escritos
- [ ] Documentación actualizada
- [ ] Validaciones implementadas
- [ ] Manejo de errores implementado

---

¡Feliz desarrollo! 🚀

