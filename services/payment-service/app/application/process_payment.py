"""Use case de processamento do pagamento (consumer do `OrderCreated`).

Orquestra idempotência (T4.1), retry com backoff (T4.2), circuit breaker
(T4.3), DLQ (T4.4) e a emissão de `PaymentApproved`/`PaymentFailed` (T4.5).
"""

from app.application.circuit_breaker import CircuitBreaker
from app.application.ports import (
    DeadLetterQueue,
    EventPublisher,
    PaymentProvider,
    PaymentRepository,
    ProcessedEvents,
)
from app.application.retry import Backoff, Sleep, pay_with_retry
from app.domain import (
    DomainEvent,
    NonRetryablePaymentError,
    OrderCreated,
    Payment,
    PaymentApproved,
    PaymentError,
    PaymentFailed,
    PaymentId,
    PaymentStatus,
)


class ProcessPayment:
    """Processa um `OrderCreated` exatamente uma vez e emite o resultado.

    - Idempotência: ``ProcessedEvents.mark_processed`` garante 1 efeito.
    - Resiliência: a cobrança passa por retry (erros transitórios) e por um
      circuit breaker que isola o provedor em falhas consecutivas.
    - Resultado: ``PaymentApproved`` em sucesso, ``PaymentFailed`` em erro de
      negócio e DLQ quando os retries se esgotam.
    """

    def __init__(
        self,
        provider: PaymentProvider,
        processed: ProcessedEvents,
        payments: PaymentRepository,
        publisher: EventPublisher,
        dlq: DeadLetterQueue,
        *,
        breaker: CircuitBreaker,
        max_attempts: int,
        backoff: Backoff,
        sleep: Sleep,
    ) -> None:
        self._provider = provider
        self._processed = processed
        self._payments = payments
        self._publisher = publisher
        self._dlq = dlq
        self._breaker = breaker
        self._max_attempts = max_attempts
        self._backoff = backoff
        self._sleep = sleep

    async def process(self, event: OrderCreated) -> DomainEvent | None:
        """Processa o evento, retornando o evento de saída ou ``None``.

        ``None`` indica que não há evento para publicar: ou o evento já foi
        processado (duplicata) ou foi roteado para a DLQ.
        """
        if not await self._processed.mark_processed(event.event_id):
            return None

        try:
            payment_id = await self._charge(event)
        except NonRetryablePaymentError as exc:
            return await self._fail(event, exc.reason)
        except PaymentError:
            await self._dlq.send(event, "retries_exhausted")
            return None

        return await self._approve(event, payment_id)

    async def _charge(self, event: OrderCreated) -> PaymentId:
        """Cobra o pedido aplicando retry + circuit breaker."""

        async def attempt() -> PaymentId:
            return await self._breaker.call(
                lambda: self._provider.charge(event.order_id, event.customer_id),
            )

        return await pay_with_retry(
            attempt,
            max_attempts=self._max_attempts,
            backoff=self._backoff,
            sleep=self._sleep,
        )

    async def _approve(
        self, event: OrderCreated, payment_id: PaymentId
    ) -> PaymentApproved:
        payment = Payment(
            id=payment_id,
            order_id=event.order_id,
            status=PaymentStatus.APPROVED,
        )
        await self._payments.add(payment)

        result = PaymentApproved(
            order_id=event.order_id,
            payment_id=payment_id,
            trace_id=event.trace_id,
        )
        await self._publisher.publish(result)
        return result

    async def _fail(self, event: OrderCreated, reason: str) -> PaymentFailed:
        payment = Payment(
            order_id=event.order_id,
            status=PaymentStatus.FAILED,
            reason=reason,
        )
        await self._payments.add(payment)

        result = PaymentFailed(
            order_id=event.order_id,
            reason=reason,
            trace_id=event.trace_id,
        )
        await self._publisher.publish(result)
        return result
