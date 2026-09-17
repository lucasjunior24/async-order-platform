"""Testes unitários do use case `ConfirmOrder` (T7.1).

Cobre a convergência eventual: o Order Service consome os eventos de resultado
(``PaymentApproved`` + ``InventoryReserved``) e evolui o pedido até ``CONFIRMED``,
aplicando idempotência sobre entregas duplicadas.
"""

from decimal import Decimal
from uuid import uuid4

from app.application.confirm_order import ConfirmOrder
from app.domain import (
    InventoryReserved,
    Order,
    OrderItem,
    OrderStatus,
    PaymentApproved,
    ProductId,
)
from app.infrastructure.in_memory import (
    InMemoryOrderRepository,
    InMemoryProcessedEvents,
)


def _order(status: OrderStatus = OrderStatus.PENDING) -> Order:
    return Order(
        customer_id=123,
        items=(
            OrderItem(
                product_id=ProductId(10), quantity=1, unit_price=Decimal("10.00")
            ),
        ),
        status=status,
    )


async def _seed(orders: InMemoryOrderRepository) -> Order:
    order = _order()
    await orders.add(order)
    return order


async def test_confirm_order_after_payment_then_inventory() -> None:
    orders = InMemoryOrderRepository()
    processed = InMemoryProcessedEvents()
    order = await _seed(orders)

    confirm = ConfirmOrder(orders, processed)

    await confirm.process(
        PaymentApproved(order_id=order.id, payment_id=uuid4(), trace_id="t")
    )
    await confirm.process(InventoryReserved(order_id=order.id, trace_id="t"))

    updated = await orders.get(order.id)
    assert updated is not None
    assert updated.status is OrderStatus.CONFIRMED


async def test_confirm_order_after_inventory_then_payment() -> None:
    orders = InMemoryOrderRepository()
    processed = InMemoryProcessedEvents()
    order = await _seed(orders)

    confirm = ConfirmOrder(orders, processed)

    await confirm.process(InventoryReserved(order_id=order.id, trace_id="t"))
    await confirm.process(
        PaymentApproved(order_id=order.id, payment_id=uuid4(), trace_id="t")
    )

    updated = await orders.get(order.id)
    assert updated is not None
    assert updated.status is OrderStatus.CONFIRMED


async def test_duplicate_event_is_ignored() -> None:
    orders = InMemoryOrderRepository()
    processed = InMemoryProcessedEvents()
    order = await _seed(orders)

    confirm = ConfirmOrder(orders, processed)
    event = PaymentApproved(order_id=order.id, payment_id=uuid4(), trace_id="t")

    await confirm.process(event)
    result = await confirm.process(event)

    assert result is None
    assert processed.count() == 1


async def test_event_for_unknown_order_is_noop() -> None:
    orders = InMemoryOrderRepository()
    processed = InMemoryProcessedEvents()
    confirm = ConfirmOrder(orders, processed)

    order = _order()
    result = await confirm.process(InventoryReserved(order_id=order.id, trace_id="t"))

    assert result is None
    assert processed.count() == 1
    assert orders.count() == 0
