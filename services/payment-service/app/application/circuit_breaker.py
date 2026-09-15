"""Circuit Breaker para isolar o provedor externo de pagamento.

Implementa a Task T4.3: N falhas consecutivas abrem o circuito (OPEN),
fazendo chamadas falharem rápido por um tempo de recuperação.
"""

import time
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import TypeVar

from app.domain import PaymentError

T = TypeVar("T")

Clock = Callable[[], float]


class CircuitState(StrEnum):
    """Estados do circuit breaker."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitOpenError(PaymentError):
    """Levantada quando o circuito está aberto e a chamada é recusada."""


class CircuitBreaker:
    """Protege um provedor externo contra cascata de falhas."""

    def __init__(
        self,
        failure_threshold: int,
        recovery_timeout: float,
        clock: Clock | None = None,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._clock = clock or _monotonic
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> CircuitState:
        """Estado atual do circuito."""
        return self._state

    def record_success(self) -> None:
        """Zera o contador de falhas ao fechar o circuito."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at = None

    def record_failure(self) -> None:
        """Abre o circuito após o número limite de falhas consecutivas."""
        self._failure_count += 1
        if self._failure_count >= self._failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = self._clock()

    async def call(self, operation: Callable[[], Awaitable[T]]) -> T:
        """Executa `operation` respeitando o estado do circuito.

        Em ``OPEN``, recusa a chamada sem tocar o provedor, a menos que o
        tempo de recuperação já tenha expirado (transição para ``HALF_OPEN``).
        """
        self._refresh()
        if self._state is CircuitState.OPEN:
            raise CircuitOpenError("Circuito aberto: provedor isolado.")

        try:
            result = await operation()
        except Exception:
            self.record_failure()
            raise
        self.record_success()
        return result

    def _refresh(self) -> None:
        if self._state is CircuitState.OPEN and self._opened_at is not None:
            elapsed = self._clock() - self._opened_at
            if elapsed >= self._recovery_timeout:
                self._state = CircuitState.HALF_OPEN


def _monotonic() -> float:
    """Relógio monotônico padrão (segundos)."""
    return time.monotonic()
