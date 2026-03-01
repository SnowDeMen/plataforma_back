import pytest
import html
from unittest.mock import AsyncMock, patch
from sqlalchemy import select
from app.application.use_cases.notification_use_cases import NotificationUseCases
from app.infrastructure.database.models import AthleteModel, TelegramSubscriberModel

@pytest.mark.asyncio
async def test_notify_pending_review_athletes_html_escape(db_session):
    """
    Verifica que notify_pending_review_athletes escape caracteres HTML
    en los nombres de los atletas antes de enviar el mensaje a Telegram.
    """
    # 1. Preparar datos en la DB
    # Un atleta activo sin nombre en TP con caracteres especiales
    problematic_name = "Atleta & con <caracteres> > especiales"
    athlete = AthleteModel(
        id="test-athlete-id",
        name=problematic_name,
        client_status="activo",
        tp_name=None,
        training_status="Al día" # No cuenta para 'count' pero sí para 'unsynced_athletes'
    )
    db_session.add(athlete)
    
    # Un suscriptor para recibir el mensaje
    subscriber = TelegramSubscriberModel(
        chat_id="123456789",
        username="testuser",
        is_active=True
    )
    db_session.add(subscriber)
    await db_session.commit()

    # 2. Preparar mocks
    with patch("app.application.use_cases.notification_use_cases.TelegramClient") as MockClient:
        mock_telegram = MockClient.return_value
        mock_telegram.get_updates = AsyncMock(return_value=[])
        mock_telegram.send_message = AsyncMock(return_value=True)
        
        with patch("app.infrastructure.repositories.system_settings_repository.SystemSettingsRepository.get_value") as mock_get_setting:
            # Mock para throttling y otros settings
            mock_get_setting.side_effect = lambda key, default=None: {
                "telegram_last_notification_sent_at": None,
                "telegram_notification_interval_hours": 0.0
            }.get(key, default)

            # 3. Ejecutar caso de uso
            use_cases = NotificationUseCases(db_session)
            success = await use_cases.notify_pending_review_athletes()
            
            # 4. Verificaciones
            assert success is True
            
            # Verificar que send_message fue llamado
            assert mock_telegram.send_message.called
            sent_message = mock_telegram.send_message.call_args[0][0]
            
            # El nombre DEBE estar escapado
            escaped_name = html.escape(problematic_name)
            assert problematic_name not in sent_message
            assert escaped_name in sent_message
            assert "&amp;" in sent_message
            assert "&lt;" in sent_message
            assert "&gt;" in sent_message
