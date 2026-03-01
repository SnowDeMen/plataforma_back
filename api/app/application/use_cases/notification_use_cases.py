"""
Casos de uso para notificaciones y alertas.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.infrastructure.database.models import TelegramSubscriberModel, AthleteModel
from app.infrastructure.repositories.athlete_repository import AthleteRepository
from app.infrastructure.repositories.system_settings_repository import SystemSettingsRepository
from app.infrastructure.external.telegram.telegram_client import TelegramClient
from loguru import logger
from datetime import datetime, timedelta
import html

class NotificationUseCases:
    """
    Gestiona el envío de notificaciones y la suscripción de usuarios.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.athlete_repo = AthleteRepository(db)
        self.settings_repo = SystemSettingsRepository(db)
        self.telegram = TelegramClient()

    async def sync_subscribers(self) -> dict:
        """
        Consulta las actualizaciones del bot de Telegram para descubrir nuevos suscriptores.
        Evita duplicados si el mismo usuario envió varios mensajes.
        """
        try:
            updates = await self.telegram.get_updates()
            if not updates:
                return {"new_subscribers": 0, "success": True}

            # 1. Extraer datos únicos de las actualizaciones (de-duplicación local)
            unique_chats = {}
            for update in updates:
                message = update.get("message")
                if not message:
                    continue
                
                chat = message.get("chat")
                if not chat or chat.get("type") != "private":
                    continue
                
                chat_id = str(chat.get("id"))
                if chat_id not in unique_chats:
                    unique_chats[chat_id] = {
                        "username": chat.get("username"),
                        "first_name": chat.get("first_name")
                    }

            if not unique_chats:
                return {"new_subscribers": 0, "success": True}

            # 2. Consultar cuáles ya existen en lote para minimizar roundtrips
            chat_ids = list(unique_chats.keys())
            query = select(TelegramSubscriberModel.chat_id).where(TelegramSubscriberModel.chat_id.in_(chat_ids))
            result = await self.db.execute(query)
            existing_ids = set(result.scalars().all())

            # 3. Insertar solo los nuevos
            new_subscribers_count = 0
            for chat_id, data in unique_chats.items():
                if chat_id not in existing_ids:
                    subscriber = TelegramSubscriberModel(
                        chat_id=chat_id,
                        username=data["username"],
                        first_name=data["first_name"],
                        is_active=True
                    )
                    self.db.add(subscriber)
                    new_subscribers_count += 1
                    logger.info(f"Nuevo suscriptor de Telegram: {data['username'] or data['first_name']} ({chat_id})")

            if new_subscribers_count > 0:
                await self.db.commit()
            
            return {"new_subscribers": new_subscribers_count, "success": True}
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
            # 0. Verificar throttling (seguridad contra reinicios frecuentes)
            now = datetime.now()
            last_sent_str = await self.settings_repo.get_value("telegram_last_notification_sent_at")
            interval_hours = await self.settings_repo.get_value("telegram_notification_interval_hours", 24.0)
            
            if last_sent_str:
                try:
                    last_sent = datetime.fromisoformat(last_sent_str)
                    if now - last_sent < timedelta(hours=interval_hours):
                        elapsed = (now - last_sent).total_seconds() / 3600
                        logger.info(f"Omitiendo notificación de Telegram: solo han pasado {elapsed:.2f}h de las {interval_hours}h requeridas.")
                        return True
                except ValueError:
                    logger.warning(f"Formato de fecha inválido en telegram_last_notification_sent_at: {last_sent_str}")

            # 1. Sincronizar suscriptores automáticamente
            await self.sync_subscribers()

            # 2. Contar atletas pendientes (status fijo 'Por revisar') solo para activo
            status_to_check = "Por revisar"
            count = await self.athlete_repo.count(
                training_status=status_to_check,
                client_statuses=["activo"]
            )
            
            # Buscar atletas activos cuyo nombre no se pudo obtener (tp_name nulo o vacio)
            query_unsynced = select(AthleteModel.name).where(
                func.lower(AthleteModel.client_status) == "activo",
                or_(AthleteModel.tp_name.is_(None), AthleteModel.tp_name == "")
            )
            result_unsynced = await self.db.execute(query_unsynced)
            unsynced_athletes = result_unsynced.scalars().all()
            
            if count == 0 and not unsynced_athletes:
                logger.info("No hay atletas 'Por revisar' ni atletas activos sin nombre de TP para notificar.")
                return True

            # Obtener lista de suscriptores activos
            query = select(TelegramSubscriberModel).where(TelegramSubscriberModel.is_active == True)
            result = await self.db.execute(query)
            subscribers = result.scalars().all()
            
            if not subscribers:
                logger.warning("No hay suscriptores de Telegram registrados. No se puede enviar la alerta.")
                return False

            # 3. Construir mensaje
            message_parts = [f"🔔 <b>Notificación de Plataforma</b>\n"]
            
            if count > 0:
                message_parts.append(f"Tienes <b>{count}</b> atletas con planes pendientes de revisar en la plataforma.")
                
            if unsynced_athletes:
                count_unsynced = len(unsynced_athletes)
                message_parts.append(f"⚠️ <b>{count_unsynced} Atletas Activos sin Nombre en TP:</b>\n" + "\n".join([f"- {html.escape(name)}" for name in unsynced_athletes]))
                
            message_parts.append(f"\n👉 <a href='https://youngsters.neuronomy.ai'>Ir al Panel de Control</a>")
            message = "\n".join(message_parts)
            
            # 4. Enviar a cada suscriptor
            success_count = 0
            for subscriber in subscribers:
                success = await self.telegram.send_message(message, chat_id=subscriber.chat_id)
                if success:
                    success_count += 1
            
            # 5. Actualizar timestamp de último envío si hubo éxito
            if success_count > 0:
                await self.settings_repo.set_value("telegram_last_notification_sent_at", now.isoformat())
                await self.db.commit()
                logger.info(f"Notificación enviada a {success_count}/{len(subscribers)} suscriptores. Timestamp actualizado.")
            
            return success_count > 0

        except Exception as e:
            logger.error(f"Error en notify_pending_review_athletes: {e}")
            return False
