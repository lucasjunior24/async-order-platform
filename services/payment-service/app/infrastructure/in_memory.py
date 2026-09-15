"""Adaptadores in-memory para os testes unitários do Payment Service."""

from uuid import UUID

from app.domain import (
    DomainEvent,
    NonRetryablePaymentError,
    OrderCreated,
    Payment,
    PaymentId,
    TransientPaymentError,
)


class InMemoryProcessedEvents:
    """Tabela `processed_events` em memória, com idempotência."""

    def __init__(self) -> None:
        self._processed: set[UUID] = set()

    async def mark_processed(self, event_id: UUID) -> bool:
        """Marca `event_id` como processado; retorna False se já existia."""
        if event_id in self._processed:
            return False
        self._processed.add(event_id)
        return True

    def count(self) -> int:
        return len(self._processed)


class InMemoryPaymentRepository:
    """Repositório de pagamentos em memória."""

    def __init__(self) -> None:
        self._payments: list[Payment] = []

    async def add(self, payment: Payment) -> None:
        self._payments.append(payment)

    def count(self) -> int:
        return len(self._payments)

    def list(self) -> list[Payment]:
        return list(self._payments)


class InMemoryEventPublisher:
    """Acumula os eventos publicados em memória."""

    def __init__(self) -> None:
        self._published: list[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> None:
        self._published.append(event)

    def published(self) -> list[DomainEvent]:
        return list(self._published)


class InMemoryDeadLetterQueue:
    """Acumula os eventos roteados para a DLQ em memória."""

    def __init__(self) -> None:
        self._messages: list[tuple[OrderCreated, str]] = []

    async def send(self, event: OrderCreated, reason: str) -> None:
        self._messages.append((event, reason))

    def count(self) -> int:
        return len(self._messages)


class InMemoryPaymentProvider:
    """Provedor de pagamento em memória, configurável para os testes."""

    def __init__(self) -> None:
        self._payments: list[tuple[UUID, int]] = []
        self._results: list[PaymentId | str] = []
        self._calls = 0

    def succeed(self) -> None:
        self._results.append(PaymentId(UUID("550e8400-e29b-41d4-a716-446655440099")))

    def transient_error(self) -> None:
        self._results.append("transient")

    def non_retryable_error(self, reason: str = "insufficient_funds") -> None:
        self._results.append(f"fail:{reason}")

    async def charge(self, order_id: UUID, customer_id: int) -> PaymentId:
        self._calls += 1
        self._payments.append((order_id, customer_id))
        if not self._results:
            return PaymentId(UUID("550e8400-e29b-41d4-a716-446655440099"))
        result = self._results.pop(0)
        if result == "transient":
            raise TransientPaymentError("provedor indisponível")
        if isinstance(result, str) and result.startswith("fail:"):
            raise NonRetryablePaymentError(result.split(":", 1)[1])
        return result  # type: ignore[return-value]

    def call_count(self) -> int:
        return self._calls
