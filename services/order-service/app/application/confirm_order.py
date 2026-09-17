"""Use case de confirmação do pedido (consumer dos eventos de resultado).

Orquestra a convergência eventual do pedido (T7.1): o Order Service consome
``PaymentApproved``/``InventoryReserved`` (e os caminhos de falha
``PaymentFailed``/``OutOfStock``) e evolui o estado do pedido até o estado
terminal correspondente.

O processamento é idempotente: a entrega duplicada de um mesmo evento não
recalcula o estado do pedido.
"""

from app.application.ports import OrderRepository, ProcessedEvents
from app.domain import OrderEvent, OrderId


class ConfirmOrder:
    """Aplica eventos de resultado ao pedido e persiste a evolução de estado.

    - Idempotência: ``ProcessedEvents.mark_processed`` garante 1 efeito.
    - Máquina de estados: delega a transição para ``Order.apply``.
    """

    def __init__(
        self,
        orders: OrderRepository,
        processed: ProcessedEvents,
    ) -> None:
        self._orders = orders
        self._processed = processed

    async def process(self, event: OrderEvent) -> OrderId | None:
        """Aplica o evento ao pedido, retornando o id do pedido ou ``None``.

        ``None`` indica que o evento já foi processado (entrega duplicada).
        """
        if not await self._processed.mark_processed(event.event_id):
            return None

        order = await self._orders.get(event.order_id)
        if order is None:
            return None

        updated = order.apply(event)
        await self._orders.update(updated)
        return updated.id
