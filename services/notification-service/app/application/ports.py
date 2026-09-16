"""Portas (interfaces) da camada de aplicação do Notification Service."""

from typing import Protocol
from uuid import UUID

from app.domain import Notification


class NotificationSender(Protocol):
    """Porta do provedor de envio de notificações (e-mail, SMS, push)."""

    async def send(self, notification: Notification) -> None: ...


class ProcessedEvents(Protocol):
    """Porta da tabela `processed_events` (idempotência)."""

    async def mark_processed(self, event_id: UUID) -> bool: ...
