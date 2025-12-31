"""
WebSocket endpoint para progreso de generacion de planes.
Permite recibir actualizaciones en tiempo real durante la generacion.
"""
import asyncio
from typing import Dict, Set
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.infrastructure.database.session import get_db
from app.infrastructure.repositories.plan_repository import PlanRepository
from app.application.use_cases.plan_use_cases import PlanUseCases


router = APIRouter(prefix="/plans", tags=["Plans WebSocket"])


class ConnectionManager:
    """
    Gestor de conexiones WebSocket para planes.
    
    Mantiene un registro de conexiones activas por plan_id
    y permite enviar mensajes a todas las conexiones de un plan.
    """
    
    def __init__(self):
        # Diccionario de plan_id -> set de websockets conectados
        self._connections: Dict[int, Set[WebSocket]] = {}
        # Lock para operaciones thread-safe
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, plan_id: int) -> None:
        """
        Acepta y registra una nueva conexion WebSocket.
        
        Args:
            websocket: Conexion WebSocket
            plan_id: ID del plan a monitorear
        """
        await websocket.accept()
        
        async with self._lock:
            if plan_id not in self._connections:
                self._connections[plan_id] = set()
            self._connections[plan_id].add(websocket)
        
        logger.debug(f"WebSocket conectado para plan {plan_id}")
    
    async def disconnect(self, websocket: WebSocket, plan_id: int) -> None:
        """
        Elimina una conexion WebSocket.
        
        Args:
            websocket: Conexion a eliminar
            plan_id: ID del plan
        """
        async with self._lock:
            if plan_id in self._connections:
                self._connections[plan_id].discard(websocket)
                
                # Limpiar si no quedan conexiones
                if not self._connections[plan_id]:
                    del self._connections[plan_id]
        
        logger.debug(f"WebSocket desconectado para plan {plan_id}")
    
    async def send_progress(
        self, 
        plan_id: int, 
        progress: int, 
        message: str,
        status: str = "generating"
    ) -> None:
        """
        Envia actualizacion de progreso a todos los clientes conectados.
        
        Args:
            plan_id: ID del plan
            progress: Porcentaje de progreso (0-100)
            message: Mensaje de estado
            status: Estado del plan
        """
        async with self._lock:
            connections = self._connections.get(plan_id, set()).copy()
        
        if not connections:
            return
        
        data = {
            "type": "progress",
            "plan_id": plan_id,
            "progress": progress,
            "message": message,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Enviar a todas las conexiones
        disconnected = []
        for websocket in connections:
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.warning(f"Error enviando a WebSocket: {e}")
                disconnected.append(websocket)
        
        # Limpiar conexiones muertas
        for ws in disconnected:
            await self.disconnect(ws, plan_id)
    
    async def send_complete(
        self, 
        plan_id: int, 
        success: bool = True,
        message: str = "Plan generado exitosamente"
    ) -> None:
        """
        Envia notificacion de completado.
        
        Args:
            plan_id: ID del plan
            success: Si la generacion fue exitosa
            message: Mensaje final
        """
        async with self._lock:
            connections = self._connections.get(plan_id, set()).copy()
        
        if not connections:
            return
        
        data = {
            "type": "complete",
            "plan_id": plan_id,
            "success": success,
            "message": message,
            "status": "review" if success else "pending",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        for websocket in connections:
            try:
                await websocket.send_json(data)
            except Exception:
                pass
    
    def get_connection_count(self, plan_id: int) -> int:
        """Retorna el numero de conexiones activas para un plan."""
        return len(self._connections.get(plan_id, set()))
    
    def get_total_connections(self) -> int:
        """Retorna el total de conexiones activas."""
        return sum(len(conns) for conns in self._connections.values())


# Instancia global del gestor de conexiones
manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    """Dependency para obtener el gestor de conexiones."""
    return manager


@router.websocket("/ws/{plan_id}")
async def plan_progress_websocket(
    websocket: WebSocket,
    plan_id: int
):
    """
    WebSocket para recibir actualizaciones de progreso de un plan.
    
    Conectarse a este endpoint para recibir actualizaciones en tiempo real
    mientras se genera un plan de entrenamiento.
    
    Mensajes enviados:
    - type: "progress" - Actualizacion de progreso
    - type: "complete" - Generacion completada
    - type: "error" - Error en generacion
    - type: "ping" - Keep-alive
    
    Args:
        websocket: Conexion WebSocket
        plan_id: ID del plan a monitorear
    """
    await manager.connect(websocket, plan_id)
    
    try:
        # Enviar estado inicial
        from app.infrastructure.database.session import AsyncSessionLocal
        
        async with AsyncSessionLocal() as db:
            repo = PlanRepository(db)
            plan = await repo.get_by_id(plan_id)
            
            if plan:
                await websocket.send_json({
                    "type": "connected",
                    "plan_id": plan_id,
                    "status": plan.status,
                    "progress": plan.generation_progress or 0,
                    "message": plan.generation_message or "Conectado",
                    "timestamp": datetime.utcnow().isoformat()
                })
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Plan {plan_id} no encontrado"
                })
                await websocket.close()
                return
        
        # Registrar callback para recibir actualizaciones
        def progress_callback(progress: int, message: str):
            """Callback que se llama cuando hay progreso."""
            asyncio.create_task(
                manager.send_progress(plan_id, progress, message)
            )
        
        PlanUseCases.register_progress_callback(plan_id, progress_callback)
        
        try:
            # Mantener conexion abierta
            while True:
                try:
                    # Esperar mensajes del cliente (para keep-alive)
                    data = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=30.0
                    )
                    
                    # Responder a pings
                    if data == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.utcnow().isoformat()
                        })
                    
                except asyncio.TimeoutError:
                    # Enviar ping para mantener conexion
                    try:
                        await websocket.send_json({
                            "type": "ping",
                            "timestamp": datetime.utcnow().isoformat()
                        })
                    except Exception:
                        break
                        
        finally:
            PlanUseCases.unregister_progress_callback(plan_id, progress_callback)
            
    except WebSocketDisconnect:
        logger.debug(f"Cliente desconectado del plan {plan_id}")
    except Exception as e:
        logger.error(f"Error en WebSocket del plan {plan_id}: {e}")
    finally:
        await manager.disconnect(websocket, plan_id)


@router.get("/ws/stats", summary="Estadisticas de conexiones WebSocket")
async def get_ws_stats():
    """
    Obtiene estadisticas de las conexiones WebSocket activas.
    
    Returns:
        Dict con estadisticas
    """
    return {
        "total_connections": manager.get_total_connections(),
        "timestamp": datetime.utcnow().isoformat()
    }

