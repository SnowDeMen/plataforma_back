import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import select
from app.application.use_cases.notification_use_cases import NotificationUseCases
from app.infrastructure.database.models import TelegramSubscriberModel

@pytest.mark.asyncio
async def test_sync_subscribers_deduplication(db_session):
    """
    Verifica que sync_subscribers maneje correctamente chat_ids duplicados
    en una sola ráfaga de actualizaciones de Telegram.
    """
    # 1. Preparar mocks
    with patch("app.application.use_cases.notification_use_cases.TelegramClient") as MockClient:
        mock_client_instance = MockClient.return_value
        
        # Simulamos 3 actualizaciones, dos de las cuales son del mismo chat_id
        mock_updates = [
            {
                "message": {
                    "chat": {"id": 8291223930, "type": "private", "username": "fersdeita", "first_name": "Fernando"}
                }
            },
            {
                "message": {
                    "chat": {"id": 8291223930, "type": "private", "username": "fersdeita", "first_name": "Fernando"}
                }
            },
            {
                "message": {
                    "chat": {"id": 1234567890, "type": "private", "username": "otheruser", "first_name": "Other"}
                }
            }
        ]
        mock_client_instance.get_updates = AsyncMock(return_value=mock_updates)
        
        # 2. Ejecutar caso de uso
        use_cases = NotificationUseCases(db_session)
        result = await use_cases.sync_subscribers()
        
        # 3. Verificaciones
        assert result["success"] is True
        assert result["new_subscribers"] == 2  # Debería insertar solo 2 (8291223930 y 1234567890)
        
        # Verificar en base de datos
        query = select(TelegramSubscriberModel)
        db_result = await db_session.execute(query)
        subscribers = db_result.scalars().all()
        
        assert len(subscribers) == 2
        chat_ids = [s.chat_id for s in subscribers]
        assert "8291223930" in chat_ids
        assert "1234567890" in chat_ids

@pytest.mark.asyncio
async def test_sync_subscribers_existing_batch(db_session):
    """
    Verifica que sync_subscribers no intente re-insertar usuarios que ya están en la DB.
    """
    # 1. Pre-insertar un usuario
    existing_subscriber = TelegramSubscriberModel(
        chat_id="8291223930",
        username="fersdeita",
        first_name="Fernando",
        is_active=True
    )
    db_session.add(existing_subscriber)
    await db_session.commit()
    
    # 2. Preparar mocks con el mismo usuario + uno nuevo
    with patch("app.application.use_cases.notification_use_cases.TelegramClient") as MockClient:
        mock_client_instance = MockClient.return_value
        
        mock_updates = [
            {
                "message": {
                    "chat": {"id": 8291223930, "type": "private", "username": "fersdeita", "first_name": "Fernando"}
                }
            },
            {
                "message": {
                    "chat": {"id": 9999999999, "type": "private", "username": "newguy", "first_name": "New"}
                }
            }
        ]
        mock_client_instance.get_updates = AsyncMock(return_value=mock_updates)
        
        # 3. Ejecutar
        use_cases = NotificationUseCases(db_session)
        result = await use_cases.sync_subscribers()
        
        # 4. Verificaciones
        assert result["success"] is True
        assert result["new_subscribers"] == 1  # Solo el nuevo
        
        query = select(TelegramSubscriberModel)
        db_result = await db_session.execute(query)
        subscribers = db_result.scalars().all()
        assert len(subscribers) == 2
