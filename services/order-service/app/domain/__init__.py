"""Domínio do Order Service: entidades, value objects, eventos e estados."""

from app.domain.base import CustomerId, OrderId, OrderStatus, ProductId
from app.domain.events import (
    InventoryReserved,
    OrderCreated,
    OrderEvent,
    OutOfStock,
    PaymentApproved,
    PaymentFailed,
)
from app.domain.order import (
    EmptyOrderError,
    InvalidTransitionError,
    Order,
    OrderItem,
)

__all__ = [
    "CustomerId",
    "EmptyOrderError",
    "InvalidTransitionError",
    "InventoryReserved",
    "Order",
    "OrderCreated",
    "OrderEvent",
    "OrderId",
    "OrderItem",
    "OrderStatus",
    "OutOfStock",
    "PaymentApproved",
    "PaymentFailed",
    "ProductId",
]
