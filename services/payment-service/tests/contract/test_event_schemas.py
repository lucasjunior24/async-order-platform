"""Testes de contrato dos eventos do Payment Service (T4.5)."""

from uuid import UUID

from app.domain.events import OrderCreated, PaymentApproved, PaymentFailed


def test_order_created_payload() -> None:
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


def test_payment_approved_payload() -> None:
    event = PaymentApproved(
        order_id=UUID("550e8400-e29b-41d4-a716-446655440001"),
        payment_id=UUID("550e8400-e29b-41d4-a716-446655440002"),
        trace_id="abc-123",
    )

    payload = event.model_dump()

    assert payload["event_type"] == "PaymentApproved"
    assert payload["payment_id"] == UUID("550e8400-e29b-41d4-a716-446655440002")


def test_payment_failed_payload() -> None:
    event = PaymentFailed(
        order_id=UUID("550e8400-e29b-41d4-a716-446655440001"),
        reason="insufficient_funds",
        trace_id="abc-123",
    )

    payload = event.model_dump()

    assert payload["event_type"] == "PaymentFailed"
    assert payload["reason"] == "insufficient_funds"
