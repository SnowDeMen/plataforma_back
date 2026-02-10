"""
Casos de uso para notificaciones y alertas.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.infrastructure.database.models import TelegramSubscriberModel
from app.infrastructure.repositories.athlete_repository import AthleteRepository
from app.infrastructure.external.telegram.telegram_client import TelegramClient
from loguru import logger

class NotificationUseCases:
    """
    Gestiona el envío de notificaciones y la suscripción de usuarios.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.athlete_repo = AthleteRepository(db)
        self.telegram = TelegramClient()

    async def sync_subscribers(self) -> dict:
        """
        Consulta las actualizaciones del bot de Telegram para descubrir nuevos suscriptores.
        """
        try:
            updates = await self.telegram.get_updates()
            new_subscribers = 0
            
            for update in updates:
                message = update.get("message")
                if not message:
                    continue
                
                chat = message.get("chat")
                if not chat or chat.get("type") != "private":
                    continue
                
                chat_id = str(chat.get("id"))
                username = chat.get("username")
                first_name = chat.get("first_name")
                
                # Verificar si ya existe
                query = select(TelegramSubscriberModel).where(TelegramSubscriberModel.chat_id == chat_id)
                result = await self.db.execute(query)
                subscriber = result.scalar_one_or_none()
                
                if not subscriber:
                    subscriber = TelegramSubscriberModel(
                        chat_id=chat_id,
                        username=username,
                        first_name=first_name,
                        is_active=True
                    )
                    self.db.add(subscriber)
                    new_subscribers += 1
                    logger.info(f"Nuevo suscriptor de Telegram: {username or first_name} ({chat_id})")
            
            await self.db.commit()
            return {"new_subscribers": new_subscribers, "success": True}
        except Exception as e:
            logger.error(f"Error al sincronizar suscriptores de Telegram: {e}")
            await self.db.rollback()
            return {"success": False, "error": str(e)}

    async def notify_pending_review_athletes(self) -> bool:
        """
        Busca atletas con status 'Por revisar' y envía un resumen a todos los suscriptores activos.
        Sincroniza suscriptores automáticamente antes de enviar.
        """
        try:
            # 0. Sincronizar suscriptores automáticamente
            await self.sync_subscribers()

            # 1. Contar atletas pendientes (status fijo 'Por revisar')
            status_to_check = "Por revisar"
            count = await self.athlete_repo.count(training_status=status_to_check)
            
            if count == 0:
                logger.info("No hay atletas 'Por Revisar' para notificar.")
                return True

            # 2. Obtener lista de suscriptores activos
            query = select(TelegramSubscriberModel).where(TelegramSubscriberModel.is_active == True)
            result = await self.db.execute(query)
            subscribers = result.scalars().all()
            
            if not subscribers:
                logger.warning("No hay suscriptores de Telegram registrados. No se puede enviar la alerta.")
                return False

            # 3. Construir mensaje
            message = (
                f"🔔 <b>Recordatorio de Revisión</b>\n\n"
                f"Tienes <b>{count}</b> atletas con planes pendientes de revisar en la plataforma.\n\n"
                f"👉 <a href='https://youngsters.app/admin/athletes'>Ir al Panel de Control</a>"
            )
            
            # 4. Enviar a cada suscriptor
            success_count = 0
            for subscriber in subscribers:
                success = await self.telegram.send_message(message, chat_id=subscriber.chat_id)
                if success:
                    success_count += 1
            
            logger.info(f"Notificación enviada a {success_count}/{len(subscribers)} suscriptores.")
            return success_count > 0

        except Exception as e:
            logger.error(f"Error en notify_pending_review_athletes: {e}")
            return False
