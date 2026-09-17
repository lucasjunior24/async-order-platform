"""Consumer dos eventos de resultado no Order Service.

Adaptador que recebe ``PaymentApproved``/``InventoryReserved`` (e os caminhos de
falha) e delega o processamento ao use case ``ConfirmOrder``, que evolui o
estado do pedido de forma idempotente.
"""

from app.application.confirm_order import ConfirmOrder
from app.domain import OrderEvent, OrderId


class OrderResultConsumer:
    """Encapsula o tratamento de mensagens de resultado do pedido.

    É o ponto de entrada orquestrado pela camada de infraestrutura de
    mensageria (aio-pika), mantendo a regra hexagonal: consumers só orquestram a
    aplicação, sem lógica de negócio.
    """

    def __init__(self, confirm_order: ConfirmOrder) -> None:
        self._confirm_order = confirm_order

    async def handle(self, event: OrderEvent) -> OrderId | None:
        """Processa o evento, retornando o id do pedido ou ``None`` se duplicado."""
        return await self._confirm_order.process(event)
