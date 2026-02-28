"""
Casos de uso para administración del sistema.
"""
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
from app.infrastructure.repositories.system_settings_repository import SystemSettingsRepository
from app.infrastructure.repositories.athlete_repository import AthleteRepository
from app.infrastructure.database.models import AthleteModel
from app.infrastructure.driver.driver_manager import DriverManager
from app.infrastructure.driver.selenium_executor import run_selenium
from loguru import logger

class AdminUseCases:
    """
    Gestiona configuraciones globales y mantenimiento del sistema.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings_repo = SystemSettingsRepository(db)
        self.athlete_repo = AthleteRepository(db)

    async def get_system_settings(self) -> Dict[str, Any]:
        """
        Retorna todas las configuraciones actuales.
        """
        return await self.settings_repo.get_all()

    async def update_notification_interval(self, hours: float) -> bool:
        """
        Actualiza el intervalo de notificaciones de Telegram.
        Nota: El efecto real en el scheduler ocurrirá en el próximo reinicio
        o mediante un trigger en el endpoint que actualice el job activo.
        """
        if hours <= 0:
            return False
            
        await self.settings_repo.set_value(
            "telegram_notification_interval_hours", 
            hours,
            "Frecuencia con la que se envían alertas de atletas pendientes (horas)."
        )
        await self.db.commit()
        logger.info(f"Intervalo de notificaciones actualizado a {hours}h")
        return True

    async def seed_default_settings(self) -> None:
        """
        Puebla configuraciones iniciales si no existen.
        """
        settings = [
            {
                "key": "telegram_notification_interval_hours",
                "value": 24.0,
                "description": "Frecuencia con la que se envían alertas de atletas pendientes (horas)."
            }
        ]
        
        for s in settings:
            # Solo si no existe
            val = await self.settings_repo.get_value(s["key"])
            if val is None:
                await self.settings_repo.set_value(s["key"], s["value"], s["description"])
        
        await self.db.commit()
        logger.info("Configuraciones por defecto inicializadas")

    def _determine_testing_plan(self, athlete: AthleteModel) -> str:
        """
        Determina el testing plan primariamente por el evento, luego por disciplina.
        """
        event_txt = f"{athlete.main_event or ''} {athlete.event_type or ''} {athlete.secondary_events or ''}".lower()
        
        if "triatl" in event_txt or "triathlon" in event_txt:
            return "Testing Triatlon"
        elif "run" in event_txt or "marat" in event_txt or "carr" in event_txt or "k" in event_txt:
            return "Testing runner"
            
        # Si no esta claro por el evento, usamos el deporte
        sport_txt = f"{athlete.discipline or ''} {athlete.athlete_type or ''}".lower()
        if "triatl" in sport_txt or "triathlon" in sport_txt:
            return "Testing Triatlon"
            
        # Por defecto ("Ninguno" o no especificado) sera runner
        return "Testing runner"

    async def get_pending_testing_plans(self) -> list[Dict[str, Any]]:
        """
        Retorna la lista de atletas que cumplen las condiciones para 
        ser asignados a un Training Plan de prueba (Start date en el futuro + Por generar).
        """
        today = datetime.now().date()
        
        query = select(AthleteModel).where(
            func.lower(AthleteModel.client_status).in_(['activo', 'prueba']),
            func.lower(AthleteModel.training_status) == "por generar",
            AthleteModel.training_start_date > today
        )
        
        result = await self.db.execute(query)
        athletes = result.scalars().all()
        
        pending_list = []
        for a in athletes:
            plan_name = self._determine_testing_plan(a)
            
            pending_list.append({
                "athlete_id": a.id,
                "name": a.name,
                "email": a.email,
                "tp_name": a.tp_name,
                "start_date": a.training_start_date.isoformat() if a.training_start_date else None,
                "recommended_plan": plan_name
            })
            
        return pending_list

    async def assign_testing_plan(self, athlete_id: str) -> Dict[str, Any]:
        """
        Asigna manualmente el Testing Plan a un atleta específico usando Selenium.
        """
        athlete = await self.athlete_repo.get_by_id(athlete_id)
        if not athlete:
            return {"success": False, "error": f"Atleta {athlete_id} no encontrado."}
            
        if not athlete.tp_name:
            return {"success": False, "error": f"El atleta {athlete.name} no tiene nombre de TrainingPeaks sincronizado (tp_name)."}
            
        if not athlete.training_start_date:
            return {"success": False, "error": f"El atleta {athlete.name} no tiene fecha de inicio de entrenamiento."}
            
        testing_plan_name = self._determine_testing_plan(athlete)
        
        try:
            # 1. Crear sesion de Selenium
            session = await run_selenium(
                DriverManager.create_session, 
                athlete.name
            )
            
            try:
                # 2. Login con cookies
                logger.info(f"Asignando {testing_plan_name} a {athlete.name} en TP...")
                await run_selenium(session.auth_service.login_with_cookie)
                
                # 3. Aplicar el Training Plan
                await run_selenium(
                    session.training_plan_service.apply_training_plan,
                    testing_plan_name,
                    athlete.tp_name,
                    athlete.training_start_date
                )
                
                # 4. Actualizar estado a "Plan activo" para que salga de la vista de pendientes
                await self.athlete_repo.update(athlete_id, {
                    "training_status": "Plan activo", 
                    "last_training_generation_at": datetime.now()
                })
                await self.db.commit()
                
                logger.success(f"Testing plan '{testing_plan_name}' pre-asignado a {athlete.name}.")
                return {"success": True, "message": f"Plan {testing_plan_name} asignado."}
                
            finally:
                if session:
                    await run_selenium(session.close)
                    
        except Exception as e:
            logger.error(f"Error asignando Testing Plan a {athlete.name}: {e}")
            return {"success": False, "error": str(e)}
