"""Testes unitários da entidade `Order` (T1.1).

Cobre cálculo de total, validações de itens (vazio, quantidade zero,
preço negativo) e o estado inicial do pedido.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.order import (
    CustomerId,
    EmptyOrderError,
    Order,
    OrderItem,
    OrderStatus,
    ProductId,
)


def _item(
    product_id: int,
    quantity: int,
    unit_price: str = "10.00",
) -> OrderItem:
    return OrderItem(
        product_id=ProductId(product_id),
        quantity=quantity,
        unit_price=Decimal(unit_price),
    )


def test_order_total_sums_all_items() -> None:
    order = Order(
        customer_id=CustomerId(123),
        items=(
            _item(10, 2, "50.00"),
            _item(20, 1, "50.00"),
        ),
    )

    assert order.total == Decimal("150.00")


def test_order_total_with_single_item() -> None:
    order = Order(
        customer_id=CustomerId(123),
        items=(_item(10, 3, "12.50"),),
    )

    assert order.total == Decimal("37.50")


def test_order_starts_as_pending() -> None:
    order = Order(customer_id=CustomerId(123), items=(_item(10, 1),))

    assert order.status is OrderStatus.PENDING


def test_order_id_is_generated_and_unique() -> None:
    first = Order(customer_id=CustomerId(123), items=(_item(10, 1),))
    second = Order(customer_id=CustomerId(123), items=(_item(10, 1),))

    assert first.id is not None
    assert first.id != second.id


def test_cannot_create_order_with_empty_items() -> None:
    with pytest.raises(EmptyOrderError):
        Order(customer_id=CustomerId(123), items=())


def test_cannot_create_item_with_zero_quantity() -> None:
    with pytest.raises(ValidationError):
        _item(10, 0)


def test_cannot_create_item_with_negative_quantity() -> None:
    with pytest.raises(ValidationError):
        _item(10, -1)


def test_cannot_create_item_with_negative_price() -> None:
    with pytest.raises(ValidationError):
        _item(10, 1, "-1.00")
