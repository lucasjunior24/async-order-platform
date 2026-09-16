"""Adaptadores in-memory para os testes unitários do Inventory Service."""

from uuid import UUID

from app.domain import (
    DomainEvent,
    ProductId,
    Reservation,
    StockLevel,
)


class InMemoryStockRepository:
    """Repositório de níveis de estoque em memória, com contador de leituras."""

    def __init__(self) -> None:
        self._stocks: dict[ProductId, StockLevel] = {}
        self._fetch_count = 0

    async def get(self, product_id: ProductId) -> StockLevel | None:
        self._fetch_count += 1
        return self._stocks.get(product_id)

    async def save(self, stock: StockLevel) -> None:
        self._stocks[stock.product_id] = stock

    def add(self, stock: StockLevel) -> None:
        """Inicializa um nível de estoque sem contar como leitura."""
        self._stocks[stock.product_id] = stock

    def fetch_count(self) -> int:
        return self._fetch_count


class InMemoryStockCache:
    """Cache read-through em memória, rastreando escritas e deleções."""

    def __init__(self) -> None:
        self._entries: dict[ProductId, StockLevel] = {}

    async def get(self, product_id: ProductId) -> StockLevel | None:
        return self._entries.get(product_id)

    async def set(self, stock: StockLevel, ttl: int) -> None:
        del ttl
        self._entries[stock.product_id] = stock

    async def delete(self, product_id: ProductId) -> None:
        self._entries.pop(product_id, None)

    def get_raw(self, product_id: ProductId) -> StockLevel | None:
        return self._entries.get(product_id)

    def count(self) -> int:
        return len(self._entries)


class InMemoryReservationRepository:
    """Repositório de reservas em memória."""

    def __init__(self) -> None:
        self._reservations: list[Reservation] = []

    async def add(self, reservation: Reservation) -> None:
        self._reservations.append(reservation)

    def count(self) -> int:
        return len(self._reservations)

    def list(self) -> list[Reservation]:
        return list(self._reservations)


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


class InMemoryEventPublisher:
    """Acumula os eventos publicados em memória."""

    def __init__(self) -> None:
        self._published: list[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> None:
        self._published.append(event)

    def published(self) -> list[DomainEvent]:
        return list(self._published)
