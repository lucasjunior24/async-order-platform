"""Domínio de estoque: nível de estoque e reservas."""

from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.domain.base import OrderId, ProductId, ReservationId
from app.domain.errors import OutOfStockError


class StockLevel(BaseModel):
    """Nível imutável de estoque de um produto, com regras de decremento."""

    model_config = ConfigDict(frozen=True)

    product_id: ProductId
    available: int = Field(ge=0)

    def can_fulfill(self, quantity: int) -> bool:
        """Indica se há unidades suficientes para atender `quantity`."""
        return self.available >= quantity

    def decrement(self, quantity: int) -> "StockLevel":
        """Reserva `quantity` unidades, retornando o novo nível.

        Levanta ``OutOfStockError`` quando o saldo é insuficiente.
        """
        if not self.can_fulfill(quantity):
            raise OutOfStockError(product_id=self.product_id)
        return self.model_copy(update={"available": self.available - quantity})


class Reservation(BaseModel):
    """Reserva imutável de estoque para um item de um pedido."""

    model_config = ConfigDict(frozen=True)

    id: ReservationId = Field(default_factory=lambda: ReservationId(uuid4()))
    order_id: OrderId
    product_id: ProductId
    quantity: int = Field(gt=0)
