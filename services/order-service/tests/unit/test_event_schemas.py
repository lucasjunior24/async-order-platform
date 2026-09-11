"""Testes unitários dos schemas pydantic dos eventos (T1.3).

Valida o contrato tipado dos eventos de domínio do Order Service.
"""

from uuid import UUID

import pytest
from pydantic import ValidationError

from app.domain.events import (
    InventoryReserved,
    OrderCreated,
    OutOfStock,
    PaymentApproved,
    PaymentFailed,
)


def test_order_created_schema_payload() -> None:
    event = OrderCreated(
        order_id=UUID("550e8400-e29b-41d4-a716-446655440001"),
        customer_id=123,
        trace_id="abc-123",
    )

    payload = event.model_dump()

    assert payload["event_type"] == "OrderCreated"
    assert payload["customer_id"] == 123
    assert payload["trace_id"] == "abc-123"
    assert payload["event_id"] is not None
    assert payload["occurred_at"] is not None


def test_payment_approved_schema_payload() -> None:
    event = PaymentApproved(
        order_id=UUID("550e8400-e29b-41d4-a716-446655440001"),
        payment_id=UUID("550e8400-e29b-41d4-a716-446655440002"),
        trace_id="abc-123",
    )

    payload = event.model_dump()

    assert payload["event_type"] == "PaymentApproved"
    assert payload["payment_id"] == UUID("550e8400-e29b-41d4-a716-446655440002")


def test_payment_failed_schema_payload() -> None:
    event = PaymentFailed(
        order_id=UUID("550e8400-e29b-41d4-a716-446655440001"),
        reason="insufficient_funds",
        trace_id="abc-123",
    )

    payload = event.model_dump()

    assert payload["event_type"] == "PaymentFailed"
    assert payload["reason"] == "insufficient_funds"


def test_inventory_reserved_schema_payload() -> None:
    event = InventoryReserved(
        order_id=UUID("550e8400-e29b-41d4-a716-446655440001"),
        trace_id="abc-123",
    )

    payload = event.model_dump()

    assert payload["event_type"] == "InventoryReserved"


def test_out_of_stock_schema_payload() -> None:
    event = OutOfStock(
        order_id=UUID("550e8400-e29b-41d4-a716-446655440001"),
        trace_id="abc-123",
    )

    payload = event.model_dump()

    assert payload["event_type"] == "OutOfStock"


def test_order_created_requires_trace_id() -> None:
    with pytest.raises(ValidationError):
        OrderCreated(
            order_id=UUID("550e8400-e29b-41d4-a716-446655440001"),
            customer_id=123,
        )
