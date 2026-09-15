"""Testes unitários da política de retry (T4.2)."""

from app.application.retry import exponential_backoff, pay_with_retry
from app.domain import NonRetryablePaymentError, TransientPaymentError


class _RecordingSleep:
    """Sleep assíncrono que grava os atrasos solicitados."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


async def test_retries_transient_error_then_succeeds() -> None:
    calls = 0

    async def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TransientPaymentError("provedor indisponível")
        return "OK"

    sleep = _RecordingSleep()
    result = await pay_with_retry(
        operation,
        max_attempts=3,
        backoff=exponential_backoff(base=2),
        sleep=sleep,
    )

    assert result == "OK"
    assert calls == 3
    assert sleep.delays == [2.0, 4.0]


async def test_does_not_retry_business_error() -> None:
    calls = 0

    async def operation() -> str:
        nonlocal calls
        calls += 1
        raise NonRetryablePaymentError("insufficient_funds")

    sleep = _RecordingSleep()
    try:
        await pay_with_retry(
            operation,
            max_attempts=5,
            backoff=exponential_backoff(),
            sleep=sleep,
        )
    except NonRetryablePaymentError:
        pass

    assert calls == 1
    assert sleep.delays == []


async def test_gives_up_after_max_attempts() -> None:
    calls = 0

    async def operation() -> str:
        nonlocal calls
        calls += 1
        raise TransientPaymentError("sempre falha")

    sleep = _RecordingSleep()
    try:
        await pay_with_retry(
            operation,
            max_attempts=3,
            backoff=exponential_backoff(base=1),
            sleep=sleep,
        )
    except TransientPaymentError:
        pass

    assert calls == 3
