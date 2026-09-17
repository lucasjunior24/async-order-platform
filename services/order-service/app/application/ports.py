"""Portas (interfaces) da camada de aplicação.

Define os contratos dos quais os use cases dependem; são implementados pela
camada de infraestrutura (repositórios SQLAlchemy, publisher RabbitMQ, etc.).
"""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from app.domain import Order, OrderEvent, OrderId


class OrderRepository(Protocol):
    """Porta de persistência de pedidos."""

    async def add(self, order: Order) -> None: ...
    async def get(self, order_id: OrderId) -> Order | None: ...
    async def update(self, order: Order) -> None: ...


class OutboxRepository(Protocol):
    """Porta do transactional outbox."""

    async def add(self, event: OrderEvent) -> None: ...
    async def list_pending(self) -> Sequence[OrderEvent]: ...
    async def remove(self, event: OrderEvent) -> None: ...


class EventPublisher(Protocol):
    """Porta de publicação de eventos no broker de mensagens."""

    async def publish(self, event: OrderEvent) -> None: ...


class ProcessedEvents(Protocol):
    """Porta da tabela `processed_events` (idempotência de eventos consumidos)."""

    async def mark_processed(self, event_id: UUID) -> bool: ...


class DeadLetterRepository(Protocol):
    """Porta de acesso às mensagens roteadas para a dead letter queue."""

    async def list(self) -> Sequence[OrderEvent]: ...
    async def get(self, message_id: UUID) -> OrderEvent | None: ...
    async def remove(self, message_id: UUID) -> None: ...


class UnitOfWork(Protocol):
    """Porta de unidade de trabalho transacional."""

    @property
    def orders(self) -> OrderRepository: ...

    @property
    def outbox(self) -> OutboxRepository: ...

    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
