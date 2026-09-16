"""Testes de contrato dos eventos do Inventory Service (T5.4)."""

from uuid import UUID

import pytest
from pydantic import ValidationError

from app.domain.events import InventoryReserved, OrderCreated, OrderItem, OutOfStock


def test_order_created_payload_with_items() -> None:
    event = OrderCreated(
        order_id=UUID("550e8400-e29b-41d4-a716-446655440001"),
        trace_id="abc-123",
        items=(OrderItem(product_id=10, quantity=2),),
    )

    payload = event.model_dump()

    assert payload["event_type"] == "OrderCreated"
    assert payload["trace_id"] == "abc-123"
    assert payload["items"][0]["product_id"] == 10
    assert payload["items"][0]["quantity"] == 2
    assert payload["event_id"] is not None


def test_inventory_reserved_payload() -> None:
    event = InventoryReserved(
        order_id=UUID("550e8400-e29b-41d4-a716-446655440001"),
        trace_id="abc-123",
    )

    payload = event.model_dump()

    assert payload["event_type"] == "InventoryReserved"
    assert payload["trace_id"] == "abc-123"


def test_out_of_stock_payload() -> None:
    event = OutOfStock(
        order_id=UUID("550e8400-e29b-41d4-a716-446655440001"),
        trace_id="abc-123",
    )

    payload = event.model_dump()

    assert payload["event_type"] == "OutOfStock"


def test_order_created_requires_items() -> None:
    with pytest.raises(ValidationError):
        OrderCreated(
            order_id=UUID("550e8400-e29b-41d4-a716-446655440001"),
            trace_id="abc-123",
            items=(),
        )
