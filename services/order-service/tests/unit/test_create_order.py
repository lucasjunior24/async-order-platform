"""Testes unitários do use case `CreateOrder` (T2.1 e T2.2).

Cobre a persistência do pedido e do evento `OrderCreated` no outbox de forma
atômica, usando um Unit of Work in-memory.
"""

from decimal import Decimal

import pytest

from app.application.create_order import CreateOrder
from app.domain import (
    CustomerId,
    EmptyOrderError,
    OrderCreated,
    OrderItem,
    OrderStatus,
    ProductId,
)
from app.infrastructure.in_memory import InMemoryUnitOfWork


def _item(product_id: int, quantity: int, unit_price: str = "10.00") -> OrderItem:
    return OrderItem(
        product_id=ProductId(product_id),
        quantity=quantity,
        unit_price=Decimal(unit_price),
    )


class FailingCommitUnitOfWork(InMemoryUnitOfWork):
    """UoW que falha no `commit`, descartando as alterações (simula erro transacional)."""

    async def commit(self) -> None:
        await self.rollback()
        raise RuntimeError("commit failed")


async def test_create_order_persists_order() -> None:
    uow = InMemoryUnitOfWork()
    service = CreateOrder(uow, trace_id="trace-1")

    order_id = await service.execute(
        customer_id=123,
        items=(_item(10, 2, "50.00"), _item(20, 1, "50.00")),
    )

    order = await uow.orders.get(order_id)
    assert order is not None
    assert order.status is OrderStatus.PENDING
    assert order.total == Decimal("150.00")
    assert order.customer_id == CustomerId(123)


async def test_create_order_records_order_created_event() -> None:
    uow = InMemoryUnitOfWork()
    service = CreateOrder(uow, trace_id="trace-1")

    order_id = await service.execute(customer_id=123, items=(_item(10, 2),))

    event = uow.outbox.first()
    assert event is not None
    assert isinstance(event, OrderCreated)
    assert event.event_type == "OrderCreated"
    assert event.order_id == order_id
    assert event.customer_id == 123
    assert event.trace_id == "trace-1"


async def test_create_order_persists_order_and_outbox_atomically() -> None:
    uow = InMemoryUnitOfWork()
    service = CreateOrder(uow, trace_id="trace-1")

    await service.execute(customer_id=123, items=(_item(10, 1),))

    assert uow.orders.count() == 1
    assert uow.outbox.count() == 1


async def test_create_order_leaves_nothing_on_commit_failure() -> None:
    uow = FailingCommitUnitOfWork()
    service = CreateOrder(uow, trace_id="trace-1")

    with pytest.raises(RuntimeError):
        await service.execute(customer_id=123, items=(_item(10, 1),))

    assert uow.orders.count() == 0
    assert uow.outbox.count() == 0


async def test_create_order_rejects_empty_items() -> None:
    uow = InMemoryUnitOfWork()
    service = CreateOrder(uow, trace_id="trace-1")

    with pytest.raises(EmptyOrderError):
        await service.execute(customer_id=123, items=())
