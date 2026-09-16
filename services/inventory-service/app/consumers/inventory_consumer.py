"""Consumer do `OrderCreated` no Inventory Service.

Adaptador que recebe o evento de domínio e delega o processamento ao use case
``ReserveStock``, que aplica idempotência, cache e invalidação.
"""

from app.application.reserve_stock import ReserveStock
from app.domain import DomainEvent, OrderCreated


class InventoryConsumer:
    """Encapsula o tratamento de mensagens `OrderCreated`.

    É o ponto de entrada orquestrado pela camada de infraestrutura de
    mensageria (aio-pika), mantendo a regra hexagonal: consumers só orquestram a
    aplicação, sem lógica de negócio.
    """

    def __init__(self, reserve_stock: ReserveStock) -> None:
        self._reserve_stock = reserve_stock

    async def handle(self, event: OrderCreated) -> DomainEvent | None:
        """Processa o evento, retornando o evento de saída publicado (se houver)."""
        return await self._reserve_stock.process(event)
