"""Adaptadores in-memory para aplicação (usados em testes unitários).

Implementam as portas de ``application`` com armazenamento em memória,
sem qualquer I/O real — ideais para testar os use cases de forma rápida e
isolada, conforme a pirâmide de testes.
"""

from collections.abc import Sequence
from uuid import UUID

from app.domain import Order, OrderCreated, OrderEvent, OrderId


class InMemoryOutboxRepository:
    """Backlog de eventos do outbox mantido em memória (ordem de inserção)."""

    def __init__(self) -> None:
        self._events: list[OrderEvent] = []
        self._committed: list[OrderEvent] = []
        self._dirty = False

    async def add(self, event: OrderEvent) -> None:
        self._events.append(event)
        self._dirty = True

    async def list_pending(self) -> Sequence[OrderEvent]:
        return list(self._events)

    async def remove(self, event: OrderEvent) -> None:
        self._events.remove(event)

    def _checkpoint(self) -> None:
        if self._dirty:
            self._committed = list(self._events)
            self._dirty = False

    def _rollback(self) -> None:
        self._events = list(self._committed)
        self._dirty = False

    def count(self) -> int:
        """Quantidade de eventos atualmente no outbox (útil nos asserts)."""
        return len(self._events)

    def first(self) -> OrderCreated | None:
        """Primeiro evento pendente, se houver (útil nos asserts)."""
        if not self._events:
            return None
        event = self._events[0]
        if isinstance(event, OrderCreated):
            return event
        return None


class InMemoryOrderRepository:
    """Repositório de pedidos em memória."""

    def __init__(self) -> None:
        self._orders: dict[OrderId, Order] = {}
        self._committed: dict[OrderId, Order] = {}
        self._dirty = False

    async def add(self, order: Order) -> None:
        self._orders[order.id] = order
        self._dirty = True

    async def get(self, order_id: OrderId) -> Order | None:
        return self._orders.get(order_id)

    async def update(self, order: Order) -> None:
        self._orders[order.id] = order
        self._dirty = True

    def _checkpoint(self) -> None:
        if self._dirty:
            self._committed = dict(self._orders)
            self._dirty = False

    def _rollback(self) -> None:
        self._orders = dict(self._committed)
        self._dirty = False

    def count(self) -> int:
        """Quantidade de pedidos persistidos (útil nos asserts)."""
        return len(self._orders)


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


class InMemoryDeadLetterRepository:
    """Repositório de dead letters em memória, para testes dos endpoints admin."""

    def __init__(self) -> None:
        self._messages: list[OrderEvent] = []

    async def list(self) -> Sequence[OrderEvent]:
        return list(self._messages)

    async def get(self, message_id: UUID) -> OrderEvent | None:
        for message in self._messages:
            if message.event_id == message_id:
                return message
        return None

    async def remove(self, message_id: UUID) -> None:
        self._messages = [m for m in self._messages if m.event_id != message_id]

    def add(self, event: OrderEvent) -> None:
        self._messages.append(event)

    def count(self) -> int:
        return len(self._messages)


class InMemoryUnitOfWork:
    """Unidade de trabalho em memória com commit/rollback simulados."""

    def __init__(self) -> None:
        self.orders = InMemoryOrderRepository()
        self.outbox = InMemoryOutboxRepository()

    async def commit(self) -> None:
        self.orders._checkpoint()
        self.outbox._checkpoint()

    async def rollback(self) -> None:
        self.orders._rollback()
        self.outbox._rollback()


class InMemoryEventPublisher:
    """Publisher que apenas acumula os eventos publicados em memória."""

    def __init__(self) -> None:
        self.published: list[OrderEvent] = []

    async def publish(self, event: OrderEvent) -> None:
        self.published.append(event)
