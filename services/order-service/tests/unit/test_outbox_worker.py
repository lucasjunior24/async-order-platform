"""Testes unitários do Outbox Worker (T2.3).

Cobre a leitura dos eventos pendentes no outbox e a publicação no broker
(mockado), garantindo que eventos publicados são removidos do outbox e que
eventos mantêm-se retidos em caso de falha na publicação.
"""

from decimal import Decimal

import pytest

from app.application.create_order import CreateOrder
from app.application.outbox_worker import OutboxWorker
from app.domain import OrderCreated, OrderEvent, OrderItem, ProductId
from app.infrastructure.in_memory import InMemoryEventPublisher, InMemoryUnitOfWork


def _item(product_id: int, quantity: int, unit_price: str = "10.00") -> OrderItem:
    return OrderItem(
        product_id=ProductId(product_id),
        quantity=quantity,
        unit_price=Decimal(unit_price),
    )


class FailingPublisher(InMemoryEventPublisher):
    """Publisher que simula um broker indisponível."""

    async def publish(self, event: OrderEvent) -> None:
        raise RuntimeError("broker down")


async def test_outbox_worker_publishes_pending_event() -> None:
    uow = InMemoryUnitOfWork()
    publisher = InMemoryEventPublisher()

    create = CreateOrder(uow, trace_id="trace-1")
    await create.execute(customer_id=123, items=(_item(10, 1),))
    assert uow.outbox.count() == 1

    worker = OutboxWorker(uow, publisher)
    published = await worker.run()

    assert published == 1
    assert len(publisher.published) == 1
    event = publisher.published[0]
    assert isinstance(event, OrderCreated)
    assert event.customer_id == 123
    assert uow.outbox.count() == 0


async def test_outbox_worker_publishes_all_pending_events() -> None:
    uow = InMemoryUnitOfWork()
    publisher = InMemoryEventPublisher()
    create = CreateOrder(uow, trace_id="trace-1")

    await create.execute(customer_id=123, items=(_item(10, 1),))
    await create.execute(customer_id=456, items=(_item(20, 2),))

    worker = OutboxWorker(uow, publisher)
    published = await worker.run()

    assert published == 2
    assert len(publisher.published) == 2
    assert uow.outbox.count() == 0


async def test_outbox_worker_keeps_event_when_publish_fails() -> None:
    uow = InMemoryUnitOfWork()
    create = CreateOrder(uow, trace_id="trace-1")
    await create.execute(customer_id=123, items=(_item(10, 1),))
    assert uow.outbox.count() == 1

    worker = OutboxWorker(uow, FailingPublisher())

    with pytest.raises(RuntimeError):
        await worker.run()

    # o evento permanece no outbox para reprocessamento futuro
    assert uow.outbox.count() == 1


async def test_outbox_worker_no_pending_events_is_noop() -> None:
    uow = InMemoryUnitOfWork()
    publisher = InMemoryEventPublisher()

    worker = OutboxWorker(uow, publisher)
    published = await worker.run()

    assert published == 0
    assert publisher.published == []
    assert uow.outbox.count() == 0
