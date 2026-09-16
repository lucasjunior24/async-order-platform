"""Portas (interfaces) da camada de aplicação do Inventory Service."""

from typing import Protocol
from uuid import UUID

from app.domain import (
    DomainEvent,
    ProductId,
    Reservation,
    StockLevel,
)


class StockRepository(Protocol):
    """Porta de persistência dos níveis de estoque."""

    async def get(self, product_id: ProductId) -> StockLevel | None: ...

    async def save(self, stock: StockLevel) -> None: ...


class ReservationRepository(Protocol):
    """Porta de persistência das reservas de estoque."""

    async def add(self, reservation: Reservation) -> None: ...


class StockCache(Protocol):
    """Porta do cache de leitura de estoque (Redis)."""

    async def get(self, product_id: ProductId) -> StockLevel | None: ...

    async def set(self, stock: StockLevel, ttl: int) -> None: ...

    async def delete(self, product_id: ProductId) -> None: ...


class ProcessedEvents(Protocol):
    """Porta da tabela `processed_events` (idempotência)."""

    async def mark_processed(self, event_id: UUID) -> bool: ...


class EventPublisher(Protocol):
    """Porta de publicação dos eventos de resultado da reserva."""

    async def publish(self, event: DomainEvent) -> None: ...
