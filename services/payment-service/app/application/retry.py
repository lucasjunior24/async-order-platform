"""Política de retry com exponential backoff para erros transitórios.

Implementa a Task T4.2: reexecuta apenas falhas transitórias (5xx/timeout),
nunca erros de negócio.
"""

from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.domain import NonRetryablePaymentError, TransientPaymentError

T = TypeVar("T")

Backoff = Callable[[int], float]
Sleep = Callable[[float], Awaitable[None]]


def exponential_backoff(base: float = 2.0) -> Backoff:
    """Retorna uma função de atraso: `base ** tentativa` segundos."""

    def delay(attempt: int) -> float:
        return base**attempt

    return delay


async def pay_with_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    max_attempts: int,
    backoff: Backoff,
    sleep: Sleep,
) -> T:
    """Executa `operation`, reexecutando apenas erros transitórios.

    - ``TransientPaymentError``: tenta novamente até ``max_attempts`` com backoff.
    - ``NonRetryablePaymentError``: propaga imediatamente, sem retry.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return await operation()
        except NonRetryablePaymentError:
            raise
        except TransientPaymentError as exc:
            if attempt >= max_attempts:
                raise
            await sleep(backoff(attempt))
