# Ejemplos de Uso de la API

## Índice
- [Crear un Agente](#crear-un-agente)
- [Obtener un Agente](#obtener-un-agente)
- [Listar Agentes](#listar-agentes)
- [Actualizar un Agente](#actualizar-un-agente)
- [Eliminar un Agente](#eliminar-un-agente)

## Crear un Agente

### Request
```bash
curl -X POST "http://localhost:8000/api/v1/agents/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Asistente de Matemáticas",
    "type": "assistant",
    "system_message": "Eres un experto en matemáticas que ayuda a resolver problemas.",
    "configuration": {
      "temperature": 0.5,
      "max_tokens": 1500
    }
  }'
```

### Response
```json
{
  "id": 1,
  "name": "Asistente de Matemáticas",
  "type": "assistant",
  "status": "idle",
  "configuration": {
    "temperature": 0.5,
    "max_tokens": 1500
  },
  "system_message": "Eres un experto en matemáticas que ayuda a resolver problemas.",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": null
}
```

## Obtener un Agente

### Request
```bash
curl -X GET "http://localhost:8000/api/v1/agents/1"
```

### Response
```json
{
  "id": 1,
  "name": "Asistente de Matemáticas",
  "type": "assistant",
  "status": "idle",
  "configuration": {
    "temperature": 0.5,
    "max_tokens": 1500
  },
  "system_message": "Eres un experto en matemáticas que ayuda a resolver problemas.",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": null
}
```

## Listar Agentes

### Request
```bash
curl -X GET "http://localhost:8000/api/v1/agents/?skip=0&limit=10"
```

### Response
```json
[
  {
    "id": 1,
    "name": "Asistente de Matemáticas",
    "type": "assistant",
    "status": "idle",
    "configuration": {
      "temperature": 0.5,
      "max_tokens": 1500
    },
    "system_message": "Eres un experto en matemáticas que ayuda a resolver problemas.",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": null
  },
  {
    "id": 2,
    "name": "Proxy Usuario",
    "type": "user_proxy",
    "status": "idle",
    "configuration": {},
    "system_message": null,
    "created_at": "2024-01-15T11:00:00Z",
    "updated_at": null
  }
]
```

## Actualizar un Agente

### Request
```bash
curl -X PUT "http://localhost:8000/api/v1/agents/1" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Asistente Avanzado de Matemáticas",
    "status": "running",
    "configuration": {
      "temperature": 0.7,
      "max_tokens": 2000
    }
  }'
```

### Response
```json
{
  "id": 1,
  "name": "Asistente Avanzado de Matemáticas",
  "type": "assistant",
  "status": "running",
  "configuration": {
    "temperature": 0.7,
    "max_tokens": 2000
  },
  "system_message": "Eres un experto en matemáticas que ayuda a resolver problemas.",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T12:00:00Z"
}
```

## Eliminar un Agente

### Request
```bash
curl -X DELETE "http://localhost:8000/api/v1/agents/1"
```

### Response
```
Status: 204 No Content
```

## Health Check

### Request
```bash
curl -X GET "http://localhost:8000/health"
```

### Response
```json
{
  "status": "healthy",
  "app_name": "Sistema de Agentes AutoGen",
  "version": "1.0.0",
  "environment": "development"
}
```

## Manejo de Errores

### Agente No Encontrado
```json
{
  "error": "ENTITY_NOT_FOUND",
  "message": "Agent con ID 999 no encontrado",
  "details": {
    "entity": "Agent",
    "id": "999"
  }
}
```

### Agente Ya Existe
```json
{
  "error": "ENTITY_ALREADY_EXISTS",
  "message": "Agent con name=Asistente de Matemáticas ya existe",
  "details": {
    "entity": "Agent",
    "field": "name",
    "value": "Asistente de Matemáticas"
  }
}
```

### Error de Validación
```json
{
  "detail": [
    {
      "loc": ["body", "name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

## Usando Python Requests

```python
import requests

# Configuración
BASE_URL = "http://localhost:8000/api/v1"

# Crear un agente
response = requests.post(
    f"{BASE_URL}/agents/",
    json={
        "name": "Mi Agente",
        "type": "assistant",
        "system_message": "Eres un asistente útil.",
        "configuration": {"temperature": 0.7}
    }
)
agent = response.json()
print(f"Agente creado: {agent['id']}")

# Obtener el agente
response = requests.get(f"{BASE_URL}/agents/{agent['id']}")
print(response.json())

# Listar todos los agentes
response = requests.get(f"{BASE_URL}/agents/")
agents = response.json()
print(f"Total de agentes: {len(agents)}")

# Actualizar el agente
response = requests.put(
    f"{BASE_URL}/agents/{agent['id']}",
    json={"status": "running"}
)
print(response.json())

# Eliminar el agente
response = requests.delete(f"{BASE_URL}/agents/{agent['id']}")
print(f"Status: {response.status_code}")
```

## Usando JavaScript/TypeScript (Fetch)

```javascript
const BASE_URL = 'http://localhost:8000/api/v1';

// Crear un agente
const createAgent = async () => {
  const response = await fetch(`${BASE_URL}/agents/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      name: 'Mi Agente',
      type: 'assistant',
      system_message: 'Eres un asistente útil.',
      configuration: { temperature: 0.7 }
    })
  });
  
  const agent = await response.json();
  console.log('Agente creado:', agent.id);
  return agent;
};

// Obtener un agente
const getAgent = async (agentId) => {
  const response = await fetch(`${BASE_URL}/agents/${agentId}`);
  const agent = await response.json();
  console.log(agent);
  return agent;
};

// Listar agentes
const listAgents = async () => {
  const response = await fetch(`${BASE_URL}/agents/`);
  const agents = await response.json();
  console.log('Total de agentes:', agents.length);
  return agents;
};

// Actualizar un agente
const updateAgent = async (agentId, updates) => {
  const response = await fetch(`${BASE_URL}/agents/${agentId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(updates)
  });
  
  const agent = await response.json();
  return agent;
};

// Eliminar un agente
const deleteAgent = async (agentId) => {
  const response = await fetch(`${BASE_URL}/agents/${agentId}`, {
    method: 'DELETE'
  });
  
  console.log('Status:', response.status);
};
```

