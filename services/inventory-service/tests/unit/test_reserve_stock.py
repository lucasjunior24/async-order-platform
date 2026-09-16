"""Testes unitários do use case `ReserveStock` (T5.1 e T5.4)."""

from uuid import uuid4

from app.application.reserve_stock import ReserveStock
from app.application.stock_service import StockService
from app.domain import (
    InventoryReserved,
    OrderCreated,
    OrderItem,
    OutOfStock,
    ProductId,
    StockLevel,
)
from app.infrastructure.in_memory import (
    InMemoryEventPublisher,
    InMemoryProcessedEvents,
    InMemoryReservationRepository,
    InMemoryStockCache,
    InMemoryStockRepository,
)


def _event(*items: OrderItem) -> OrderCreated:
    return OrderCreated(
        order_id=uuid4(),
        trace_id="trace-1",
        items=tuple(items) or (OrderItem(product_id=10, quantity=2),),
    )


def _service() -> tuple[
    ReserveStock,
    InMemoryStockRepository,
    InMemoryReservationRepository,
    InMemoryEventPublisher,
]:
    repository = InMemoryStockRepository()
    reservations = InMemoryReservationRepository()
    publisher = InMemoryEventPublisher()
    stock_service = StockService(repository, InMemoryStockCache())
    service = ReserveStock(
        stock_service,
        reservations,
        InMemoryProcessedEvents(),
        publisher,
    )
    return service, repository, reservations, publisher


async def test_reserve_stock_emits_inventory_reserved() -> None:
    service, repository, reservations, publisher = _service()
    repository.add(StockLevel(product_id=ProductId(10), available=5))

    result = await service.process(_event())

    assert isinstance(result, InventoryReserved)
    assert reservations.count() == 1
    assert repository.fetch_count() > 0
    assert len(publisher.published()) == 1
    assert publisher.published()[0].trace_id == "trace-1"


async def test_reserve_stock_all_items_or_nothing() -> None:
    service, repository, reservations, publisher = _service()
    repository.add(StockLevel(product_id=10, available=5))
    repository.add(StockLevel(product_id=20, available=0))

    result = await service.process(
        _event(
            OrderItem(product_id=10, quantity=2), OrderItem(product_id=20, quantity=1)
        ),
    )

    # o primeiro item não deve ser reservado se o segundo está sem estoque
    assert isinstance(result, OutOfStock)
    assert reservations.count() == 0
    assert publisher.published()[0].event_type == "OutOfStock"


async def test_reserve_stock_processed_only_once_when_duplicate() -> None:
    repo = InMemoryStockRepository()
    repo.add(StockLevel(product_id=ProductId(10), available=5))
    reservations = InMemoryReservationRepository()
    publisher = InMemoryEventPublisher()
    stock_service = StockService(repo, InMemoryStockCache())
    service = ReserveStock(
        stock_service,
        reservations,
        InMemoryProcessedEvents(),
        publisher,
    )

    event = _event()
    await service.process(event)
    await service.process(event)

    assert reservations.count() == 1
    assert len(publisher.published()) == 1


async def test_emits_out_of_stock_when_product_missing() -> None:
    service, _, reservations, publisher = _service()

    result = await service.process(_event())

    assert isinstance(result, OutOfStock)
    assert reservations.count() == 0
    assert publisher.published()[0].event_type == "OutOfStock"
