"""Portas (interfaces) da camada de aplicação do Payment Service."""

from typing import Protocol
from uuid import UUID

from app.domain import (
    DomainEvent,
    OrderCreated,
    Payment,
    PaymentId,
)


class PaymentProvider(Protocol):
    """Porta do provedor externo de pagamento (gateway)."""

    async def charge(self, order_id: UUID, customer_id: int) -> PaymentId: ...


class ProcessedEvents(Protocol):
    """Porta da tabela `processed_events` (idempotência)."""

    async def mark_processed(self, event_id: UUID) -> bool: ...


class PaymentRepository(Protocol):
    """Porta de persistência de pagamentos."""

    async def add(self, payment: Payment) -> None: ...


class EventPublisher(Protocol):
    """Porta de publicação dos eventos de resultado do pagamento."""

    async def publish(self, event: DomainEvent) -> None: ...


class DeadLetterQueue(Protocol):
    """Porta da dead letter queue para mensagens que esgotaram os retries."""

    async def send(self, event: OrderCreated, reason: str) -> None: ...
