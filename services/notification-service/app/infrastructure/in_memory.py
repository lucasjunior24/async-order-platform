"""Adaptadores in-memory para os testes unitários do Notification Service."""

from uuid import UUID

from app.domain import Notification


class InMemoryProcessedEvents:
    """Tabela `processed_events` em memória, com idempotência."""

    def __init__(self) -> None:
        self._processed: set[UUID] = set()

    async def mark_processed(self, event_id: UUID) -> bool:
        """Marca `event_id` como processado; retorna False se já existia."""
        if event_id in self._processed:
            return False
        self._processed.add(event_id)
        return True

    def count(self) -> int:
        return len(self._processed)


class InMemoryNotificationSender:
    """Provedor de envio de notificações em memória, rastreando os envios."""

    def __init__(self) -> None:
        self._sent: list[Notification] = []

    async def send(self, notification: Notification) -> None:
        self._sent.append(notification)

    def send_count(self) -> int:
        return len(self._sent)

    def sent(self) -> list[Notification]:
        return list(self._sent)
