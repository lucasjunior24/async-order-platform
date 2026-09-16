"""Testes unitários do consumer de eventos (roteamento por `event_type`)."""

from unittest.mock import AsyncMock
from uuid import UUID

from app.consumers.notification_consumer import NotificationConsumer
from app.domain import Notification, OrderCreated, OrderId


async def test_consumer_delegates_to_send_notification() -> None:
    order_id = OrderId(UUID("550e8400-e29b-41d4-a716-446655440001"))

    event = OrderCreated(
        order_id=order_id,
        customer_id=123,
        recipient_email="cliente@example.com",
        trace_id="trace-1",
    )

    notification = Notification(
        recipient_email=event.recipient_email,
        subject="Pedido recebido",
        body="body",
        trace_id=event.trace_id,
    )

    send_notification = AsyncMock()
    send_notification.process.return_value = notification

    consumer = NotificationConsumer(send_notification)

    assert await consumer.handle(event) is notification
    send_notification.process.assert_awaited_once_with(event)
