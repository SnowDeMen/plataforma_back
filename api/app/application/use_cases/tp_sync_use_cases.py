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
    
    async def _run_job(self, *, job_id: str, username: str, athlete_id: str) -> None:
        """
        Ejecuta el flujo de sincronizacion con TrainingPeaks.
        
        Flujo:
        1. Obtiene el nombre del atleta de la BD (para busqueda optimizada)
        2. Crea driver navegando a #home (en thread para no bloquear)
        3. Hace login en TrainingPeaks
        4. Busca el atleta por username usando el nombre como hint (busqueda rapida)
        5. Si lo encuentra, obtiene el nombre del atleta en TP (tp_name)
        6. Guarda el nombre como tp_name en PostgreSQL
        7. Actualiza el campo tp_name en Airtable
        
        Las operaciones de Selenium se ejecutan en threads separados via run_selenium()
        para no bloquear el event loop y permitir que el healthcheck responda.
        """
        driver = None
        expected_name = None
        
        try:
            # 0. Obtener el nombre del atleta de la BD para busqueda optimizada
            await self._update_job(
                job_id, 
                message="Obteniendo datos del atleta...", 
                progress=2
            )
            
            async with AsyncSessionLocal() as db:
                repo = AthleteRepository(db)
                athlete = await repo.get_by_id(athlete_id)
                if athlete:
                    expected_name = athlete.name
                    logger.info(f"[tp-sync-job:{job_id}] Nombre para busqueda optimizada: {expected_name}")
            
            # 1. Crear driver navegando a #home
            await self._update_job(
                job_id, 
                message="Creando sesion de navegador...", 
                progress=5
            )
            logger.info(f"[tp-sync-job:{job_id}] Buscando atleta con username: {username}")
            driver, wait = await run_selenium(DriverManager._create_driver_for_home)
            
            # Inicializar servicios
            auth_service = AuthService(driver, wait)
            athlete_service = AthleteService(driver, wait)
            
            # 2. Login en TrainingPeaks
            await self._update_job(
                job_id, 
                message="Iniciando sesion en TrainingPeaks...", 
                progress=15
            )
            logger.info(f"[tp-sync-job:{job_id}] Haciendo login...")
            await run_selenium(auth_service.login_with_cookie)
            
            # 3. Navegar a #home
            await self._update_job(
                job_id, 
                message="Navegando a biblioteca de atletas...", 
                progress=25
            )
            logger.info(f"[tp-sync-job:{job_id}] Navegando a #home...")
            await run_selenium(athlete_service.navigate_to_home)
            
            # 4. Buscar por username (optimizado si tenemos expected_name)
            if expected_name:
                await self._update_job(
                    job_id, 
                    message=f"Buscando atleta '{expected_name}' (busqueda optimizada)...", 
                    progress=35
                )
            else:
                await self._update_job(
                    job_id, 
                    message="Buscando atleta por username (esto puede tardar)...", 
                    progress=35
                )
            
            search_result = await run_selenium(
                athlete_service.find_athlete_by_username, 
                username,
                expected_name  # Pasamos el nombre para busqueda rapida
            )
            
            if not search_result["found"]:
                await self._update_job(
                    job_id,
                    status="failed",
                    progress=100,
                    message=f"No se encontro atleta con username: {username}",
                    error=f"Atleta no encontrado en TrainingPeaks: {username}",
                    completed_at=datetime.now(timezone.utc),
                )
                logger.warning(f"[tp-sync-job:{job_id}] No se encontro: {username}")
                return
            
            tp_name = search_result["full_name"]
            group = search_result["group"]
            
            await self._update_job(
                job_id, 
                message=f"Atleta encontrado: {tp_name}", 
                progress=60,
                tp_name=tp_name,
                group=group,
            )
            logger.info(f"[tp-sync-job:{job_id}] Encontrado: {tp_name} en grupo {group}")
            
            # 5. Guardar en PostgreSQL
            await self._update_job(
                job_id, 
                message="Guardando en base de datos...", 
                progress=75
            )
            
            async with AsyncSessionLocal() as db:
                repo = AthleteRepository(db)
                athlete = await repo.get_by_id(athlete_id)
                
                if not athlete:
                    await self._update_job(
                        job_id,
                        status="failed",
                        progress=100,
                        message=f"Atleta no encontrado en DB: {athlete_id}",
                        error=f"Atleta no existe en la base de datos: {athlete_id}",
                        completed_at=datetime.now(timezone.utc),
                    )
                    return
                
                # Actualizar tp_name en la base de datos
                await repo.update(athlete_id, {"tp_name": tp_name})
                await db.commit()
                
                # Guardar el ID de Airtable para el siguiente paso
                airtable_record_id = athlete.id
            
            logger.info(f"[tp-sync-job:{job_id}] Guardado en PostgreSQL: {athlete_id}")
            
            # 6. Actualizar en Airtable
            await self._update_job(
                job_id, 
                message="Actualizando Airtable...", 
                progress=90
            )
            
            await self._sync_airtable(job_id, airtable_record_id, tp_name)
            
            # Completado exitosamente
            await self._update_job(
                job_id,
                status="completed",
                progress=100,
                message=f"Sincronizado exitosamente: {tp_name}",
                completed_at=datetime.now(timezone.utc),
            )
            logger.info(f"[tp-sync-job:{job_id}] Completado: {username} -> {tp_name}")
            
        except Exception as e:
            logger.exception(f"[tp-sync-job:{job_id}] Error: {e}")
            await self._update_job(
                job_id,
                status="failed",
                progress=100,
                message="Error durante la sincronizacion",
                error=str(e),
                completed_at=datetime.now(timezone.utc),
            )
            
        finally:
            # Cerrar driver
            if driver:
                try:
                    await run_selenium(driver.quit)
                    logger.info(f"[tp-sync-job:{job_id}] Driver cerrado")
                except Exception:
                    pass
    
    async def _sync_airtable(self, job_id: str, record_id: str, tp_name: str) -> None:
        """
        Actualiza el campo tp_name en Airtable.
        
        No falla el job si Airtable falla (solo loguea warning).
        """
        from app.infrastructure.external.airtable_sync.airtable_client import (
            AirtableClient, AirtableCredentials
        )
        
        AIRTABLE_TABLE_ID = "tblMNRYRfYTWYpc5o"  # Table ID de Formulario_Inicial
        TP_NAME_FIELD_ID = "fldmVrBQxHtlN4qXL"  # Field ID de tp_name
        
        try:
            airtable_token = os.environ.get("AIRTABLE_TOKEN")
            airtable_base_id = os.environ.get("AIRTABLE_BASE_ID")
            
            if airtable_token and airtable_base_id:
                client = AirtableClient(
                    AirtableCredentials(token=airtable_token, base_id=airtable_base_id)
                )
                logger.info(f"[tp-sync-job:{job_id}] Actualizando Airtable: record={record_id}")
                client.update_record(
                    table_name=AIRTABLE_TABLE_ID,
                    record_id=record_id,
                    fields={TP_NAME_FIELD_ID: tp_name}
                )
                logger.info(f"[tp-sync-job:{job_id}] Airtable actualizado: {record_id} -> {tp_name}")
            else:
                logger.warning(f"[tp-sync-job:{job_id}] Credenciales de Airtable no configuradas")
        except Exception as e:
            # No fallar el job si Airtable falla
            logger.exception(f"[tp-sync-job:{job_id}] Error actualizando Airtable: {e}")
