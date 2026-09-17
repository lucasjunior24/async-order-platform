"""Use case de administração da dead letter queue (T7.4).

Fornece as operações dos endpoints admin:

- ``list``: lista as mensagens na DLQ.
- ``reprocess``: republica uma mensagem da DLQ no broker e a remove da fila morta.
"""

from collections.abc import Sequence
from uuid import UUID

from app.application.ports import DeadLetterRepository, EventPublisher
from app.domain import OrderEvent


class DeadLetterAdmin:
    """Lista e reprocessa mensagens da dead letter queue."""

    def __init__(
        self,
        dead_letters: DeadLetterRepository,
        publisher: EventPublisher,
    ) -> None:
        self._dead_letters = dead_letters
        self._publisher = publisher

    async def list(self) -> Sequence[OrderEvent]:
        """Retorna todas as mensagens atualmente na DLQ."""
        return await self._dead_letters.list()

    async def reprocess(self, message_id: UUID) -> OrderEvent | None:
        """Republica a mensagem indicada no broker e a remove da DLQ.

        Retorna o evento republicado, ou ``None`` se o identificador não existir.
        """
        message = await self._dead_letters.get(message_id)
        if message is None:
            return None

        await self._publisher.publish(message)
        await self._dead_letters.remove(message_id)
        return message
