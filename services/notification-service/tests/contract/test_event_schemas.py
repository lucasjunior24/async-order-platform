"""Testes de contrato dos eventos do Notification Service (T6.1).

O serviço reage a fatos publicados pelos demais serviços; estes testes fixam o
shape do payload consumido (``event_type``, ``order_id``, ``trace_id``,
``event_id`` e ``recipient_email``).
"""

from uuid import UUID

from app.domain.base import OrderId
from app.domain.events import (
    InventoryReserved,
    OrderCreated,
    OutOfStock,
    PaymentApproved,
    PaymentFailed,
)


def _order_id() -> OrderId:
    return OrderId(UUID("550e8400-e29b-41d4-a716-446655440001"))


def test_order_created_payload() -> None:
    event = OrderCreated(
        order_id=_order_id(),
        customer_id=123,
        recipient_email="cliente@example.com",
        trace_id="abc-123",
    )

    payload = event.model_dump()

    assert payload["event_type"] == "OrderCreated"
    assert payload["customer_id"] == 123
    assert payload["recipient_email"] == "cliente@example.com"
    assert payload["trace_id"] == "abc-123"
    assert payload["event_id"] is not None


def test_payment_approved_payload() -> None:
    event = PaymentApproved(
        order_id=_order_id(),
        recipient_email="cliente@example.com",
        trace_id="abc-123",
    )

    payload = event.model_dump()

    assert payload["event_type"] == "PaymentApproved"
    assert payload["recipient_email"] == "cliente@example.com"


def test_payment_failed_payload() -> None:
    event = PaymentFailed(
        order_id=_order_id(),
        recipient_email="cliente@example.com",
        trace_id="abc-123",
        reason="insufficient_funds",
    )

    payload = event.model_dump()

    assert payload["event_type"] == "PaymentFailed"
    assert payload["reason"] == "insufficient_funds"


def test_inventory_reserved_payload() -> None:
    event = InventoryReserved(
        order_id=_order_id(),
        recipient_email="cliente@example.com",
        trace_id="abc-123",
    )

    payload = event.model_dump()

    assert payload["event_type"] == "InventoryReserved"


def test_out_of_stock_payload() -> None:
    event = OutOfStock(
        order_id=_order_id(),
        recipient_email="cliente@example.com",
        trace_id="abc-123",
    )

    payload = event.model_dump()

    assert payload["event_type"] == "OutOfStock"
