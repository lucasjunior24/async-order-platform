"""Testes unitários do circuit breaker (T4.3)."""

from app.application.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)
from app.domain import TransientPaymentError


class _FakeClock:
    """Relógio controlável para os testes do tempo de recuperação."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


async def _fail() -> str:
    raise TransientPaymentError("provedor indisponível")


async def test_circuit_opens_after_failures() -> None:
    breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30)
    calls = 0

    async def operation() -> str:
        nonlocal calls
        calls += 1
        raise TransientPaymentError("falha")

    for _ in range(5):
        try:
            await breaker.call(operation)
        except TransientPaymentError:
            pass

    assert breaker.state is CircuitState.OPEN

    try:
        await breaker.call(operation)
    except CircuitOpenError:
        pass

    # a 6ª chamada não deve invocar a operação (falha rápido)
    assert calls == 5


async def test_circuit_recovers_after_timeout() -> None:
    clock = _FakeClock()
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=30, clock=clock)

    try:
        await breaker.call(_fail)
    except TransientPaymentError:
        pass

    assert breaker.state is CircuitState.OPEN

    clock.now = 31.0

    async def succeed() -> str:
        return "OK"

    result = await breaker.call(succeed)

    assert result == "OK"
    assert breaker.state is CircuitState.CLOSED


async def test_success_resets_failure_count() -> None:
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30)
    calls = 0

    async def fail_then_succeed() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TransientPaymentError("falha")
        return "OK"

    try:
        await breaker.call(fail_then_succeed)
    except TransientPaymentError:
        pass

    await breaker.call(fail_then_succeed)
    await breaker.call(fail_then_succeed)

    assert breaker.state is CircuitState.CLOSED
