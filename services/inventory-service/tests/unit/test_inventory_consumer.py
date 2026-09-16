"""Testes unitários do consumer do `OrderCreated` (T5.1)."""

from unittest.mock import AsyncMock
from uuid import UUID

from app.consumers.inventory_consumer import InventoryConsumer
from app.domain import InventoryReserved, OrderCreated, OrderItem


async def test_consumer_delegates_to_reserve_stock() -> None:
    order_id = UUID("550e8400-e29b-41d4-a716-446655440001")

    event = OrderCreated(
        order_id=order_id,
        trace_id="trace-1",
        items=(OrderItem(product_id=10, quantity=2),),
    )
    result = InventoryReserved(
        order_id=order_id,
        trace_id=event.trace_id,
    )

    reserve_stock = AsyncMock()
    reserve_stock.process.return_value = result

    consumer = InventoryConsumer(reserve_stock)

    assert await consumer.handle(event) is result
    reserve_stock.process.assert_awaited_once_with(event)
