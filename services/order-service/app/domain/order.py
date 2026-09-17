"""Entidade `Order` e sua máquina de estados.

Regras de negócio puras, sem dependência de infraestrutura.
"""

from decimal import Decimal
from typing import Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.base import CustomerId, OrderId, OrderStatus, ProductId
from app.domain.events import (
    InventoryReserved,
    OrderEvent,
    OutOfStock,
    PaymentApproved,
    PaymentFailed,
)


class EmptyOrderError(Exception):
    """Levantada ao tentar criar um pedido sem itens."""


class InvalidTransitionError(ValueError):
    """Levantada ao aplicar um evento inválido ao estado atual do pedido."""


class OrderItem(BaseModel):
    """Item de um pedido: produto, quantidade e preço unitário."""

    model_config = ConfigDict(frozen=True)

    product_id: ProductId
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(ge=Decimal("0"))


# Transições permitidas por tipo de evento.
_TRANSITIONS: dict[type[OrderEvent], dict[OrderStatus, OrderStatus]] = {
    PaymentApproved: {
        OrderStatus.PENDING: OrderStatus.PAYMENT_APPROVED,
        OrderStatus.INVENTORY_RESERVED: OrderStatus.CONFIRMED,
    },
    InventoryReserved: {
        OrderStatus.PENDING: OrderStatus.INVENTORY_RESERVED,
        OrderStatus.PAYMENT_APPROVED: OrderStatus.CONFIRMED,
    },
    PaymentFailed: {
        OrderStatus.PENDING: OrderStatus.PAYMENT_FAILED,
    },
    OutOfStock: {
        OrderStatus.PENDING: OrderStatus.OUT_OF_STOCK,
    },
}


class Order(BaseModel):
    """Pedido imutável; evolução de estado ocorre via `apply` retornando nova instância."""

    model_config = ConfigDict(frozen=True)

    id: OrderId = Field(default_factory=lambda: OrderId(uuid4()))
    customer_id: CustomerId
    items: tuple[OrderItem, ...] = ()
    status: OrderStatus = OrderStatus.PENDING

    @model_validator(mode="after")
    def _ensure_not_empty(self) -> Self:
        if not self.items:
            raise EmptyOrderError("O pedido deve conter pelo menos um item.")
        return self

    @property
    def total(self) -> Decimal:
        """Soma (preço unitário x quantidade) de todos os itens."""
        return sum(
            (item.unit_price * item.quantity for item in self.items),
            start=Decimal("0"),
        )

    def apply(self, event: OrderEvent) -> Self:
        """Aplica um evento de domínio, retornando uma nova instância com o novo estado."""
        if event.order_id != self.id:
            raise InvalidTransitionError(
                f"Evento {event.event_type} refere-se a outro pedido.",
            )

        transitions = _TRANSITIONS.get(type(event))
        if transitions is None:
            raise InvalidTransitionError(
                f"Evento {event.event_type} não é aplicável a pedidos.",
            )

        new_status = transitions.get(self.status)
        if new_status is None:
            raise InvalidTransitionError(
                f"Transição inválida: {event.event_type} em {self.status}.",
            )

        return self.model_copy(update={"status": new_status})
