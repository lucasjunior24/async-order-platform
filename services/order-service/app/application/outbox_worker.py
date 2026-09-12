"""Outbox worker: publica eventos pendentes no broker."""

from app.application.ports import EventPublisher, UnitOfWork
from app.domain import OrderEvent


class OutboxWorker:
    """Lê os eventos pendentes do outbox e os publica no broker.

    Cada evento publicado com sucesso é removido do outbox. Em caso de falha
    na publicação, o evento é mantido no outbox para reprocessamento futuro,
    preservando a garantia de entrega.
    """

    def __init__(self, uow: UnitOfWork, publisher: EventPublisher) -> None:
        self._uow = uow
        self._publisher = publisher

    async def run(self) -> int:
        """Processa uma rodada do outbox, retornando quantos eventos publicou."""
        events = await self._uow.outbox.list_pending()
        published = 0

        for event in events:
            await self._publish_one(event)
            published += 1

        return published

    async def _publish_one(self, event: OrderEvent) -> None:
        """Publica um evento, removendo-o do outbox somente após sucesso."""
        await self._publisher.publish(event)
        await self._uow.outbox.remove(event)
