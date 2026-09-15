"""Testes unitários do use case `ProcessPayment` (T4.1, T4.4 e T4.5)."""

from uuid import uuid4

from app.application.circuit_breaker import CircuitBreaker
from app.application.process_payment import ProcessPayment
from app.application.retry import exponential_backoff
from app.domain import OrderCreated, PaymentApproved, PaymentFailed, PaymentStatus
from app.infrastructure.in_memory import (
    InMemoryDeadLetterQueue,
    InMemoryEventPublisher,
    InMemoryPaymentProvider,
    InMemoryPaymentRepository,
    InMemoryProcessedEvents,
)


class _NoopSleep:
    async def __call__(self, delay: float) -> None:
        del delay


def _event() -> OrderCreated:
    return OrderCreated(
        order_id=uuid4(),
        customer_id=123,
        trace_id="trace-1",
    )


def _service(
    *,
    provider: InMemoryPaymentProvider,
    processed: InMemoryProcessedEvents,
    payments: InMemoryPaymentRepository,
    publisher: InMemoryEventPublisher,
    dlq: InMemoryDeadLetterQueue,
    max_attempts: int = 3,
) -> ProcessPayment:
    return ProcessPayment(
        provider,
        processed,
        payments,
        publisher,
        dlq,
        breaker=CircuitBreaker(failure_threshold=5, recovery_timeout=30),
        max_attempts=max_attempts,
        backoff=exponential_backoff(base=1),
        sleep=_NoopSleep(),
    )


async def test_payment_processed_only_once_when_duplicate() -> None:
    provider = InMemoryPaymentProvider()
    provider.transient_error()
    provider.transient_error()
    provider.succeed()

    processed = InMemoryProcessedEvents()
    payments = InMemoryPaymentRepository()
    publisher = InMemoryEventPublisher()
    dlq = InMemoryDeadLetterQueue()
    service = _service(
        provider=provider,
        processed=processed,
        payments=payments,
        publisher=publisher,
        dlq=dlq,
    )

    event = _event()
    first = await service.process(event)
    second = await service.process(event)

    assert first is not None
    assert isinstance(first, PaymentApproved)
    assert second is None  # duplicata ignora o processamento
    assert payments.count() == 1
    assert provider.call_count() == 3


async def test_emits_payment_approved_on_success() -> None:
    provider = InMemoryPaymentProvider()
    provider.succeed()

    payments = InMemoryPaymentRepository()
    publisher = InMemoryEventPublisher()
    service = _service(
        provider=provider,
        processed=InMemoryProcessedEvents(),
        payments=payments,
        publisher=publisher,
        dlq=InMemoryDeadLetterQueue(),
    )

    event = _event()
    result = await service.process(event)

    assert isinstance(result, PaymentApproved)
    assert payments.count() == 1
    assert payments.list()[0].status is PaymentStatus.APPROVED
    assert len(publisher.published()) == 1
    assert publisher.published()[0].trace_id == "trace-1"


async def test_emits_payment_failed_on_business_error() -> None:
    provider = InMemoryPaymentProvider()
    provider.non_retryable_error(reason="insufficient_funds")

    payments = InMemoryPaymentRepository()
    publisher = InMemoryEventPublisher()
    service = _service(
        provider=provider,
        processed=InMemoryProcessedEvents(),
        payments=payments,
        publisher=publisher,
        dlq=InMemoryDeadLetterQueue(),
    )

    event = _event()
    result = await service.process(event)

    assert isinstance(result, PaymentFailed)
    assert result.reason == "insufficient_funds"
    assert payments.count() == 1
    assert payments.list()[0].status is PaymentStatus.FAILED


async def test_routes_to_dlq_after_retries_exhausted() -> None:
    provider = InMemoryPaymentProvider()
    for _ in range(3):
        provider.transient_error()

    dlq = InMemoryDeadLetterQueue()
    service = _service(
        provider=provider,
        processed=InMemoryProcessedEvents(),
        payments=InMemoryPaymentRepository(),
        publisher=InMemoryEventPublisher(),
        dlq=dlq,
        max_attempts=3,
    )

    event = _event()
    result = await service.process(event)

    assert result is None
    assert dlq.count() == 1
    assert provider.call_count() == 3


async def test_does_not_retry_business_error() -> None:
    provider = InMemoryPaymentProvider()
    provider.non_retryable_error(reason="insufficient_funds")

    service = _service(
        provider=provider,
        processed=InMemoryProcessedEvents(),
        payments=InMemoryPaymentRepository(),
        publisher=InMemoryEventPublisher(),
        dlq=InMemoryDeadLetterQueue(),
        max_attempts=5,
    )

    result = await service.process(_event())

    assert isinstance(result, PaymentFailed)
    assert provider.call_count() == 1
