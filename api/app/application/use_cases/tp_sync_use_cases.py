"""
Casos de uso para sincronizar nombre de atleta desde TrainingPeaks.

Patron asincrono:
- El endpoint inicia el job en background y retorna inmediatamente un job_id.
- El frontend hace polling al endpoint de status hasta que el job termine.
- Evita timeouts de proxies (Traefik/Easypanel) en operaciones largas de Selenium.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from loguru import logger

from app.application.dto.session_dto import TPSyncJobResponseDTO, TPSyncJobStatusDTO
from app.infrastructure.database.session import AsyncSessionLocal
from app.infrastructure.driver.driver_manager import DriverManager
from app.infrastructure.driver.selenium_executor import run_selenium
from app.infrastructure.driver.services.auth_service import AuthService
from app.infrastructure.driver.services.athlete_service import AthleteService
from app.infrastructure.repositories.athlete_repository import AthleteRepository
from typing import Callable, Awaitable


@dataclass
class _JobState:
    """Estado interno de un job de sincronizacion TP."""
    
    job_id: str
    username: str
    athlete_id: str
    status: str  # running, completed, failed
    progress: int
    message: str
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    # Resultado cuando completed
    tp_name: Optional[str] = None
    group: Optional[str] = None


class TPSyncUseCases:
    """
    Orquestador de jobs de sincronizacion de nombre TP.
    
    Los jobs se guardan en memoria (dict). Para el caso de uso actual es suficiente:
    - Permite polling simple desde el frontend.
    - No introduce infraestructura extra (Redis, DB, etc.).
    """
    
    _jobs: Dict[str, _JobState] = {}
    _jobs_lock = asyncio.Lock()
    
    async def start_sync(self, username: str, athlete_id: str) -> TPSyncJobResponseDTO:
        """
        Inicia un job de sincronizacion en background.
        
        Args:
            username: Username de TrainingPeaks (tp_username)
            athlete_id: ID del atleta en la base de datos
            
        Returns:
            TPSyncJobResponseDTO: Respuesta inmediata con job_id para polling
        """
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        job = _JobState(
            job_id=job_id,
            username=username,
            athlete_id=athlete_id,
            status="running",
            progress=0,
            message="Iniciando sincronizacion con TrainingPeaks...",
            created_at=now,
            updated_at=now,
        )
        
        async with self._jobs_lock:
            self._jobs[job_id] = job
        
        # Ejecutar en background sin bloquear la request
        asyncio.create_task(self._run_job(job_id=job_id, username=username, athlete_id=athlete_id))
        
        return TPSyncJobResponseDTO(
            job_id=job_id,
            status=job.status,
            progress=job.progress,
            message=job.message,
            created_at=job.created_at,
        )
    
    async def get_job_status(self, job_id: str) -> TPSyncJobStatusDTO:
        """
        Obtiene el estado actual de un job (para polling).
        
        Args:
            job_id: ID del job a consultar
            
        Returns:
            TPSyncJobStatusDTO: Estado actual del job
            
        Raises:
            KeyError: Si el job no existe
        """
        async with self._jobs_lock:
            job = self._jobs.get(job_id)
        
        if job is None:
            raise KeyError("job_not_found")
        
        return TPSyncJobStatusDTO(
            job_id=job.job_id,
            status=job.status,
            progress=job.progress,
            message=job.message,
            created_at=job.created_at,
            updated_at=job.updated_at,
            completed_at=job.completed_at,
            error=job.error,
            tp_name=job.tp_name,
            group=job.group,
        )
    
    async def _update_job(self, job_id: str, **changes: Any) -> None:
        """Actualiza campos del job de forma thread-safe."""
        async with self._jobs_lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            for k, v in changes.items():
                setattr(job, k, v)
            job.updated_at = datetime.now(timezone.utc)
    
    async def execute_sync_process(
        self,
        username: Optional[str],
        athlete_id: str,
        progress_callback: Optional[Callable[[str, int], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        Ejecuta la logica de sincronizacion de forma directa.
        
        Args:
            username: Username de TrainingPeaks
            athlete_id: ID del atleta en BD
            progress_callback: Callback opcional para reportar progreso (msg, percent)
            
        Returns:
            Dict con resultado de la operacion (success, message, tp_name, group)
        """
        driver = None
        expected_name = None

        result = {
            "success": False,
            "message": "",
            "username": username,
            "tp_name": None,
            "group": None
        }
        
        full_name_db = None
        
        # Helper para reportar progreso si existe callback
        async def report(msg: str, prog: int):
            if progress_callback:
                await progress_callback(msg, prog)
        
        try:
            # 0. Obtener el nombre del atleta de la BD para busqueda optimizada
            await report("Obteniendo datos del atleta...", 2)
            
            async with AsyncSessionLocal() as db:
                repo = AthleteRepository(db)
                athlete = await repo.get_by_id(athlete_id)
                if athlete:
                    # Preferir tp_name (nombre validado de TP en sync anterior) sobre
                    # name (de AirTable) para evitar fallos con nombres abreviados.
                    expected_name = athlete.tp_name or athlete.name
                    full_name_db = athlete.full_name
                    logger.info(f"[tp-sync] Nombre para busqueda optimizada: {expected_name}")
            
            # 1. Crear driver navegando a #home
            await report("Creando sesion de navegador...", 5)
            logger.info(f"[tp-sync] Buscando atleta con username: {username}")
            driver, wait = await run_selenium(DriverManager._create_driver_for_home)
            
            # Inicializar servicios
            auth_service = AuthService(driver, wait)
            athlete_service = AthleteService(driver, wait)
            
            # 2. Login en TrainingPeaks
            await report("Iniciando sesion en TrainingPeaks...", 15)
            logger.info(f"[tp-sync] Haciendo login...")
            await run_selenium(auth_service.login_with_cookie)
            
            # 3. Navegar a #home
            await report("Navegando a biblioteca de atletas...", 25)
            logger.info(f"[tp-sync] Navegando a #home...")
            await run_selenium(athlete_service.navigate_to_home)
            
            # 4. Buscar Atleta
            search_result = {"found": False}
            
            if username:
                # Caso A: Tenemos username, buscamos directamente
                if expected_name:
                    await report(f"Verificando atleta '{expected_name}' con usuario '{username}'...", 35)
                else:
                    await report(f"Buscando usuario '{username}' (esto puede tardar)...", 35)
                
                search_result = await run_selenium(
                    athlete_service.find_athlete_by_username, 
                    username,
                    expected_name
                )
            else:
                # Caso B: No tenemos username, descubrimos por nombre
                await report(f"Descubriendo usuario TP para '{expected_name}'...", 35)
                
                discovered_username = await run_selenium(
                    athlete_service.discover_username,
                    athlete_name=expected_name,
                    full_name=full_name_db
                )
                
                if discovered_username:
                    username = discovered_username
                    result["username"] = username
                    # Ahora buscamos detalles con el username descubierto
                    search_result = await run_selenium(
                        athlete_service.find_athlete_by_username, 
                        username,
                        expected_name
                    )
            
            if not search_result["found"]:
                error_msg = "No se encontro atleta en TrainingPeaks"
                if username:
                    error_msg += f" con usuario '{username}'"
                
                result["message"] = error_msg
                logger.warning(f"[tp-sync] {error_msg}")
                return result
            
            # Si descubrimos el username, guardarlo en BD
            if athlete and not athlete.tp_username and username:
                async with AsyncSessionLocal() as db:
                    repo = AthleteRepository(db)
                    await repo.update(athlete_id, {"tp_username": username})
                    await db.commit()
                
                # También actualizar en Airtable
                try:
                    self._sync_airtable_username(None, athlete_id, username)
                except Exception:
                    pass

            tp_name = search_result["full_name"]
            group = search_result["group"]
            
            result["tp_name"] = tp_name
            result["group"] = group
            
            await report(f"Atleta encontrado: {tp_name}", 60)
            logger.info(f"[tp-sync] Encontrado: {tp_name} en grupo {group}")
            
            # 5. Guardar en PostgreSQL
            await report("Guardando en base de datos...", 75)
            
            airtable_record_id = None
            async with AsyncSessionLocal() as db:
                repo = AthleteRepository(db)
                athlete = await repo.get_by_id(athlete_id)
                
                if not athlete:
                    result["message"] = f"Atleta no encontrado en DB: {athlete_id}"
                    return result
                
                # Actualizar tp_name en la base de datos
                await repo.update(athlete_id, {"tp_name": tp_name})
                await db.commit()
                
                # Guardar el ID de Airtable para el siguiente paso
                airtable_record_id = athlete.id
            
            logger.info(f"[tp-sync] Guardado en PostgreSQL: {athlete_id}")
            
            # 6. Actualizar en Airtable
            await report("Actualizando Airtable...", 90)
            
            if airtable_record_id:
                try:
                    await self._sync_airtable(None, airtable_record_id, tp_name)
                except Exception as e:
                    logger.error(f"[tp-sync] Error airtable: {e}")
            
            # Completado exitosamente
            result["success"] = True
            result["message"] = f"Sincronizado exitosamente: {tp_name}"
            
            return result
            
        except Exception as e:
            logger.exception(f"[tp-sync] Error critico: {e}")
            result["message"] = str(e)
            return result
            
        finally:
            # Cerrar driver
            if driver:
                try:
                    await run_selenium(driver.quit)
                    logger.info(f"[tp-sync] Driver cerrado")
                except Exception:
                    pass

    async def _run_job(self, *, job_id: str, username: str, athlete_id: str) -> None:
        """
        Ejecuta el job en background usando execute_sync_process.
        """
        try:
            # Definir callback para actualizar el job
            async def job_callback(msg: str, prog: int):
                await self._update_job(job_id, message=msg, progress=prog)

            # Ejecutar logica principal
            result = await self.execute_sync_process(
                username=username, 
                athlete_id=athlete_id, 
                progress_callback=job_callback
            )
            
            if result["success"]:
                await self._update_job(
                    job_id,
                    status="completed",
                    progress=100,
                    message=result["message"],
                    tp_name=result["tp_name"],
                    group=result["group"],
                    completed_at=datetime.now(timezone.utc),
                )
            else:
                await self._update_job(
                    job_id,
                    status="failed",
                    progress=100,
                    message=result["message"],
                    error=result["message"],
                    completed_at=datetime.now(timezone.utc),
                )
                
        except Exception as e:
            logger.exception(f"[tp-sync-job:{job_id}] Error wrapper: {e}")
            await self._update_job(
                job_id,
                status="failed",
                progress=100,
                message="Error inesperado en job",
                error=str(e),
                completed_at=datetime.now(timezone.utc),
            )
    
    async def _sync_airtable(self, job_id: str | None, record_id: str, tp_name: str) -> None:
        """
        Actualiza el campo tp_name en Airtable.
        
        No falla el job si Airtable falla (solo loguea warning).
        """
        from app.infrastructure.external.airtable_sync.airtable_client import (
            AirtableClient, AirtableCredentials
        )
        
        from app.core.config import settings
        
        TP_NAME_FIELD_ID = "fldmVrBQxHtlN4qXL"  # Field ID de tp_name
        
        job_tag = f"[tp-sync-job:{job_id}]" if job_id else "[tp-sync]"
        
        try:
            airtable_token = os.environ.get("AIRTABLE_TOKEN")
            airtable_base_id = os.environ.get("AIRTABLE_BASE_ID")
            
            if airtable_token and airtable_base_id and settings.AIRTABLE_TABLE_NAME:
                client = AirtableClient(
                    AirtableCredentials(token=airtable_token, base_id=airtable_base_id)
                )
                logger.info(f"{job_tag} Actualizando Airtable: record={record_id}")
                client.update_record(
                    table_name=settings.AIRTABLE_TABLE_NAME,
                    record_id=record_id,
                    fields={TP_NAME_FIELD_ID: tp_name}
                )
                logger.info(f"{job_tag} Airtable actualizado: {record_id} -> {tp_name}")
            else:
                logger.warning(f"{job_tag} Credenciales de Airtable no configuradas")
        except Exception as e:
            # No fallar el job si Airtable falla
            logger.exception(f"{job_tag} Error actualizando Airtable: {e}")

    async def _sync_airtable_username(self, job_id: str | None, record_id: str, tp_username: str) -> None:
        """Actualiza el username en Airtable."""
        from app.infrastructure.external.airtable_sync.airtable_client import (
            AirtableClient, AirtableCredentials
        )
        try:
            airtable_token = os.environ.get("AIRTABLE_TOKEN")
            airtable_base_id = os.environ.get("AIRTABLE_BASE_ID")
            
            if airtable_token and airtable_base_id:
                client = AirtableClient(
                   AirtableCredentials(token=airtable_token, base_id=airtable_base_id)
                )
                # Nota: Asumiendo que el campo se llama "Cuenta TrainingPeaks" como en sync_use_cases.py
                client.update_record(
                    table_name=settings.AIRTABLE_TABLE_NAME, 
                    record_id=record_id,
                    fields={"Cuenta TrainingPeaks": tp_username}
                )
        except Exception as e:
            logger.exception(f"[tp-sync] Error actualizando username en Airtable: {e}")
