"""Testes unitários do use case `DeadLetterAdmin` (T7.4)."""

from uuid import uuid4

from app.application.dead_letter_admin import DeadLetterAdmin
from app.domain import InventoryReserved, OrderEvent
from app.infrastructure.in_memory import (
    InMemoryDeadLetterRepository,
    InMemoryEventPublisher,
)


def _event() -> OrderEvent:
    return InventoryReserved(order_id=uuid4(), trace_id="trace-1")


async def test_list_returns_all_messages() -> None:
    dead_letters = InMemoryDeadLetterRepository()
    event = _event()
    dead_letters.add(event)

    admin = DeadLetterAdmin(dead_letters, InMemoryEventPublisher())

    messages = await admin.list()

    assert len(messages) == 1
    assert messages[0].event_id == event.event_id


async def test_reprocess_republishes_and_removes_message() -> None:
    dead_letters = InMemoryDeadLetterRepository()
    publisher = InMemoryEventPublisher()
    event = _event()
    dead_letters.add(event)

    admin = DeadLetterAdmin(dead_letters, publisher)

    result = await admin.reprocess(event.event_id)

    assert result is not None
    assert result.event_id == event.event_id
    assert len(publisher.published) == 1
    assert dead_letters.count() == 0


async def test_reprocess_unknown_message_returns_none() -> None:
    dead_letters = InMemoryDeadLetterRepository()
    publisher = InMemoryEventPublisher()

    admin = DeadLetterAdmin(dead_letters, publisher)

    result = await admin.reprocess(uuid4())

    assert result is None
    assert len(publisher.published) == 0
