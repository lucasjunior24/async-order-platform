"""Use case de reserva de estoque (consumer do `OrderCreated`).

Orquestra idempotência (T5.1), reserva de estoque com cache (T5.2/T5.3) e a
emissão de `InventoryReserved`/`OutOfStock` (T5.4).

A reserva é "tudo ou nada": se qualquer item do pedido não tiver estoque
suficiente, nenhum item é decrementado e o evento `OutOfStock` é emitido.
"""

from app.application.ports import (
    EventPublisher,
    ProcessedEvents,
    ReservationRepository,
)
from app.application.stock_service import StockService
from app.domain import (
    DomainEvent,
    InventoryReserved,
    OrderCreated,
    OutOfStock,
    Reservation,
)


class ReserveStock:
    """Reserva o estoque de um pedido exatamente uma vez e emite o resultado."""

    def __init__(
        self,
        stock_service: StockService,
        reservations: ReservationRepository,
        processed: ProcessedEvents,
        publisher: EventPublisher,
    ) -> None:
        self._stock_service = stock_service
        self._reservations = reservations
        self._processed = processed
        self._publisher = publisher

    async def process(self, event: OrderCreated) -> DomainEvent | None:
        """Reserva o estoque do pedido, retornando o evento de saída.

        Retorna ``None`` se o evento já foi processado (entrega duplicada).
        """
        if not await self._processed.mark_processed(event.event_id):
            return None

        if not await self._has_stock_for(event):
            return await self._out_of_stock(event)

        await self._reserve_items(event)
        return await self._reserved(event)

    async def _has_stock_for(self, event: OrderCreated) -> bool:
        """Verifica se todos os itens possuem estoque suficiente."""
        for item in event.items:
            stock = await self._stock_service.get_stock(item.product_id)
            if stock is None or not stock.can_fulfill(item.quantity):
                return False
        return True

    async def _reserve_items(self, event: OrderCreated) -> None:
        """Decrementa e persiste a reserva de cada item do pedido."""
        for item in event.items:
            await self._stock_service.reserve(item.product_id, item.quantity)
            await self._reservations.add(
                Reservation(
                    order_id=event.order_id,
                    product_id=item.product_id,
                    quantity=item.quantity,
                ),
            )

    async def _reserved(self, event: OrderCreated) -> InventoryReserved:
        result = InventoryReserved(
            order_id=event.order_id,
            trace_id=event.trace_id,
        )
        await self._publisher.publish(result)
        return result

    async def _out_of_stock(self, event: OrderCreated) -> OutOfStock:
        result = OutOfStock(
            order_id=event.order_id,
            trace_id=event.trace_id,
        )
        await self._publisher.publish(result)
        return result
