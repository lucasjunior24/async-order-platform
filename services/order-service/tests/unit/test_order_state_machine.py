"""Testes unitários da máquina de estados do pedido (T1.2).

Cobre a convergência eventual:
    PENDING --PaymentApproved + InventoryReserved--> CONFIRMED
e os caminhos de falha:
    PENDING --PaymentFailed--> PAYMENT_FAILED
    PENDING --OutOfStock--> OUT_OF_STOCK
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.base import OrderId
from app.domain.events import (
    InventoryReserved,
    OrderCreated,
    OutOfStock,
    PaymentApproved,
    PaymentFailed,
)
from app.domain.order import (
    CustomerId,
    InvalidTransitionError,
    Order,
    OrderItem,
    OrderStatus,
    ProductId,
)


def _order(status: OrderStatus = OrderStatus.PENDING) -> Order:
    return Order(
        customer_id=CustomerId(123),
        items=(
            OrderItem(
                product_id=ProductId(10),
                quantity=1,
                unit_price=Decimal("10.00"),
            ),
        ),
        status=status,
    )


def test_order_confirmed_after_payment_then_inventory() -> None:
    order = _order()

    order = order.apply(
        PaymentApproved(order_id=order.id, payment_id=uuid4(), trace_id="trace-1")
    )
    assert order.status is OrderStatus.PAYMENT_APPROVED

    order = order.apply(InventoryReserved(order_id=order.id, trace_id="trace-1"))
    assert order.status is OrderStatus.CONFIRMED


def test_order_confirmed_after_inventory_then_payment() -> None:
    order = _order()

    order = order.apply(InventoryReserved(order_id=order.id, trace_id="trace-1"))
    assert order.status is OrderStatus.INVENTORY_RESERVED

    order = order.apply(
        PaymentApproved(order_id=order.id, payment_id=uuid4(), trace_id="trace-1")
    )
    assert order.status is OrderStatus.CONFIRMED


def test_order_payment_failed_transition() -> None:
    order = _order()

    order = order.apply(PaymentFailed(order_id=order.id, trace_id="trace-1"))

    assert order.status is OrderStatus.PAYMENT_FAILED


def test_order_out_of_stock_transition() -> None:
    order = _order()

    order = order.apply(OutOfStock(order_id=order.id, trace_id="trace-1"))

    assert order.status is OrderStatus.OUT_OF_STOCK


def test_invalid_transition_from_confirmed_raises() -> None:
    order = _order(status=OrderStatus.CONFIRMED)

    with pytest.raises(InvalidTransitionError):
        order.apply(PaymentFailed(order_id=order.id, trace_id="trace-1"))


def test_invalid_transition_from_terminal_state_raises() -> None:
    order = _order(status=OrderStatus.PAYMENT_FAILED)

    with pytest.raises(InvalidTransitionError):
        order.apply(
            PaymentApproved(order_id=order.id, payment_id=uuid4(), trace_id="trace-1")
        )


def test_apply_event_for_different_order_raises() -> None:
    order = _order()
    other_id = OrderId(uuid4())

    with pytest.raises(InvalidTransitionError):
        order.apply(PaymentFailed(order_id=other_id, trace_id="trace-1"))


def test_apply_non_state_event_raises() -> None:
    order = _order()

    with pytest.raises(InvalidTransitionError):
        order.apply(
            OrderCreated(order_id=order.id, customer_id=123, trace_id="trace-1")
        )
