"""
Cliente para interactuar con la API de Telegram.
"""
import httpx
from loguru import logger
from app.core.config import settings

class TelegramClient:
    """
    Cliente simple para enviar mensajes vía Telegram Bot API.
    """
    
    def __init__(self, bot_token: str = None):
        self.bot_token = bot_token or settings.TELEGRAM_BOT_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    async def send_message(self, text: str, chat_id: str) -> bool:
        """
        Envía un mensaje de texto a un chat específico.
        
        Args:
            text: Contenido del mensaje.
            chat_id: ID del chat de destino.
        """
        if not self.bot_token or not chat_id:
            logger.warning("Telegram Bot Token o Chat ID no proporcionados. Saltando notificación.")
            return False

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Error al enviar mensaje de Telegram: {e}")
            return False

    async def get_updates(self) -> list:
        """
        Obtiene los últimos mensajes enviados al bot.
        Utilizado para descubrir nuevos suscriptores.
        """
        if not self.bot_token:
            return []

        url = f"{self.base_url}/getUpdates"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                if data.get("ok"):
                    return data.get("result", [])
        except Exception as e:
            logger.error(f"Error al obtener actualizaciones de Telegram: {e}")
        
        return []
