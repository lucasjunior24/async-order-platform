"""Use case de criação de pedido com transactional outbox."""

from app.application.ports import UnitOfWork
from app.domain import (
    CustomerId,
    Order,
    OrderCreated,
    OrderId,
    OrderItem,
)


class CreateOrder:
    """Cria um pedido e registra seu evento `OrderCreated` atomicamente.

    O pedido e o evento de outbox são gravados na mesma transação (via
    ``UnitOfWork``), garantindo que nenhum evento seja perdido.
    """

    def __init__(self, uow: UnitOfWork, trace_id: str) -> None:
        self._uow = uow
        self._trace_id = trace_id

    async def execute(
        self,
        customer_id: int,
        items: tuple[OrderItem, ...],
    ) -> OrderId:
        """Cria e persiste o pedido, retornando seu identificador."""
        order = Order(
            customer_id=CustomerId(customer_id),
            items=items,
        )

        event = OrderCreated(
            order_id=order.id,
            customer_id=customer_id,
            trace_id=self._trace_id,
        )

        await self._uow.orders.add(order)
        await self._uow.outbox.add(event)
        await self._uow.commit()

        return order.id
