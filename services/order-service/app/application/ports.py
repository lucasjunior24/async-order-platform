"""Portas (interfaces) da camada de aplicação.

Define os contratos dos quais os use cases dependem; são implementados pela
camada de infraestrutura (repositórios SQLAlchemy, publisher RabbitMQ, etc.).
"""

from collections.abc import Sequence
from typing import Protocol

from app.domain import Order, OrderEvent, OrderId


class OrderRepository(Protocol):
    """Porta de persistência de pedidos."""

    async def add(self, order: Order) -> None: ...
    async def get(self, order_id: OrderId) -> Order | None: ...


class OutboxRepository(Protocol):
    """Porta do transactional outbox."""

    async def add(self, event: OrderEvent) -> None: ...
    async def list_pending(self) -> Sequence[OrderEvent]: ...
    async def remove(self, event: OrderEvent) -> None: ...


class EventPublisher(Protocol):
    """Porta de publicação de eventos no broker de mensagens."""

    async def publish(self, event: OrderEvent) -> None: ...


class UnitOfWork(Protocol):
    """Porta de unidade de trabalho transacional."""

    orders: OrderRepository
    outbox: OutboxRepository

    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
