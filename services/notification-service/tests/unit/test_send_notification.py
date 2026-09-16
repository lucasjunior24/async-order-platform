"""Testes unitários do use case `SendNotification` (T6.1 e T6.2)."""

from uuid import uuid4

import pytest

from app.application.send_notification import SendNotification
from app.domain import (
    DomainEvent,
    InventoryReserved,
    Notification,
    OrderCreated,
    OrderId,
    OutOfStock,
    PaymentApproved,
    PaymentFailed,
)
from app.infrastructure.in_memory import (
    InMemoryNotificationSender,
    InMemoryProcessedEvents,
)


def _event() -> OrderCreated:
    return OrderCreated(
        order_id=OrderId(uuid4()),
        customer_id=123,
        recipient_email="cliente@example.com",
        trace_id="trace-1",
    )


def _service(
    sender: InMemoryNotificationSender,
    processed: InMemoryProcessedEvents,
) -> SendNotification:
    return SendNotification(sender, processed)


async def test_sends_notification_on_event() -> None:
    sender = InMemoryNotificationSender()
    service = _service(sender, InMemoryProcessedEvents())

    result = await service.process(_event())

    assert isinstance(result, Notification)
    assert result.recipient_email == "cliente@example.com"
    assert sender.send_count() == 1


async def test_composes_order_received_message() -> None:
    sender = InMemoryNotificationSender()
    service = _service(sender, InMemoryProcessedEvents())

    event = _event()
    result = await service.process(event)

    assert result is not None
    assert result.subject == "Pedido recebido"
    assert str(event.order_id) in result.body


async def test_notification_sent_only_once_when_duplicate() -> None:
    sender = InMemoryNotificationSender()
    processed = InMemoryProcessedEvents()
    service = _service(sender, processed)

    event = _event()
    first = await service.process(event)
    second = await service.process(event)

    assert first is not None
    assert second is None  # entrega duplicada não envia novamente
    assert sender.send_count() == 1


async def test_duplicate_does_not_send_email() -> None:
    sender = InMemoryNotificationSender()
    service = _service(sender, InMemoryProcessedEvents())

    event = _event()
    await service.process(event)
    await service.process(event)
    await service.process(event)

    assert sender.send_count() == 1


@pytest.mark.parametrize(
    ("event", "subject"),
    [
        (
            PaymentApproved(
                order_id=OrderId(uuid4()),
                recipient_email="cliente@example.com",
                trace_id="trace-1",
            ),
            "Pagamento aprovado",
        ),
        (
            PaymentFailed(
                order_id=OrderId(uuid4()),
                recipient_email="cliente@example.com",
                trace_id="trace-1",
                reason="insufficient_funds",
            ),
            "Falha no pagamento",
        ),
        (
            InventoryReserved(
                order_id=OrderId(uuid4()),
                recipient_email="cliente@example.com",
                trace_id="trace-1",
            ),
            "Estoque reservado",
        ),
        (
            OutOfStock(
                order_id=OrderId(uuid4()),
                recipient_email="cliente@example.com",
                trace_id="trace-1",
            ),
            "Produto indisponível",
        ),
    ],
)
async def test_composes_subject_for_each_event_type(
    event: DomainEvent,
    subject: str,
) -> None:
    sender = InMemoryNotificationSender()
    service = _service(sender, InMemoryProcessedEvents())

    result = await service.process(event)

    assert result is not None
    assert result.subject == subject
    assert sender.send_count() == 1
