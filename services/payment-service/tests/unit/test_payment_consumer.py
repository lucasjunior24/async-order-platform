"""Testes unitários do consumer do `OrderCreated` (T4.1)."""

from unittest.mock import AsyncMock
from uuid import UUID

from app.consumers.payment_consumer import PaymentConsumer
from app.domain import OrderCreated, PaymentApproved


async def test_consumer_delegates_to_process_payment() -> None:
    order_id = UUID("550e8400-e29b-41d4-a716-446655440001")
    payment_id = UUID("550e8400-e29b-41d4-a716-446655440002")

    event = OrderCreated(
        order_id=order_id,
        customer_id=123,
        trace_id="trace-1",
    )
    result = PaymentApproved(
        order_id=order_id,
        payment_id=payment_id,
        trace_id=event.trace_id,
    )

    process = AsyncMock()
    process.process.return_value = result

    consumer = PaymentConsumer(process)

    assert await consumer.handle(event) is result
    process.process.assert_awaited_once_with(event)
