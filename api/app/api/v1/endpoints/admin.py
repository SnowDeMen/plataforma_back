"""
Endpoints para administración del sistema.
"""
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from apscheduler.triggers.interval import IntervalTrigger

from app.infrastructure.database.session import get_db
from app.application.use_cases.admin_use_cases import AdminUseCases
from app.application.use_cases.notification_use_cases import NotificationUseCases

router = APIRouter()

@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db)):
    """
    Obtiene todas las configuraciones del sistema.
    """
    use_cases = AdminUseCases(db)
    return await use_cases.get_system_settings()

@router.get("/athletes/pending-testing-plan")
async def get_pending_testing_plans(db: AsyncSession = Depends(get_db)):
    """
    Obtiene la lista de atletas candidatos a recibir el plan de prueba de 1 semana.
    """
    use_cases = AdminUseCases(db)
    return await use_cases.get_pending_testing_plans()

@router.post("/athletes/{athlete_id}/assign-testing-plan")
async def assign_testing_plan(athlete_id: str, db: AsyncSession = Depends(get_db)):
    """
    Asigna mediante Selenium el plan de prueba recomendado al atleta especificado.
    """
    use_cases = AdminUseCases(db)
    result = await use_cases.assign_testing_plan(athlete_id)
    
    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=result.get("error", "Error desconocido asignando el plan")
        )
        
    return result

@router.post("/test-notification")
async def test_notification(db: AsyncSession = Depends(get_db)):
    """
    Dispara manualmente una notificación de prueba a Telegram con los atletas pendientes actuales.
    """
    notifier = NotificationUseCases(db)
    success = await notifier.notify_pending_review_athletes()
    
    if not success:
        raise HTTPException(
            status_code=500, 
            detail="Error al enviar la notificación. Verifica que haya suscriptores activos y que el Bot Token sea válido."
        )
    
    return {"message": "Notificación de prueba enviada exitosamente", "success": True}

@router.post("/telegram/sync-subscribers")
async def sync_telegram_subscribers(db: AsyncSession = Depends(get_db)):
    """
    Sincroniza los suscriptores de Telegram consultando las actualizaciones del bot.
    """
    notifier = NotificationUseCases(db)
    result = await notifier.sync_subscribers()
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result

@router.post("/settings/notification-interval")
async def update_notification_interval(
    request: Request,
    hours: float, 
    db: AsyncSession = Depends(get_db)
):
    """
    Actualiza el intervalo de notificaciones de Telegram y reinicia el job.
    """
    use_cases = AdminUseCases(db)
    success = await use_cases.update_notification_interval(hours)
    
    if not success:
        raise HTTPException(status_code=400, detail="Intervalo inválido")
        
    # Intentar actualizar el job en el scheduler activo
    scheduler = request.app.state.scheduler
    if scheduler:
        try:
            scheduler.reschedule_job(
                "telegram_notification",
                trigger=IntervalTrigger(hours=hours)
            )
            return {"message": f"Intervalo actualizado a {hours}h y job reiniciado", "success": True}
        except Exception as e:
            return {"message": f"Configuración guardada, pero hubo un error al reiniciar el job: {str(e)}", "success": True}
            
    return {"message": f"Configuración guardada para el próximo reinicio", "success": True}

@router.post("/settings/days-in-advance")
async def update_days_in_advance_generation(
    days: int, 
    db: AsyncSession = Depends(get_db)
):
    """
    Actualiza el número de días de anticipación con los que se genera el próximo plan mensual basado en plan_end_date.
    """
    use_cases = AdminUseCases(db)
    success = await use_cases.update_days_in_advance_generation(days)
    
    if not success:
        raise HTTPException(status_code=400, detail="Días de anticipación inválidos (debe ser >= 0)")
        
    return {"message": f"Días de anticipación actualizados a {days}", "success": True}
