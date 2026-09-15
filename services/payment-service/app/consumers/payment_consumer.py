"""Consumer do `OrderCreated` no Payment Service.

Adaptador que recebe o evento de domínio e delega o processamento ao use case
``ProcessPayment``, que aplica idempotência, retry, circuit breaker e DLQ.
"""

from app.application.process_payment import ProcessPayment
from app.domain import DomainEvent, OrderCreated


class PaymentConsumer:
    """Encapsula o tratamento de mensagens `OrderCreated`.

    É o ponto de entrada orquestrado pela camada de infraestrutura de
    mensageria (aio-pika), mantendo a regra hexagonal: consumers só orquestram a
    aplicação, sem lógica de negócio.
    """

    def __init__(self, process_payment: ProcessPayment) -> None:
        self._process_payment = process_payment

    async def handle(self, event: OrderCreated) -> DomainEvent | None:
        """Processa o evento, retornando o evento de saída publicado (se houver)."""
        return await self._process_payment.process(event)
