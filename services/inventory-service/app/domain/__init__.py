"""Domínio do Inventory Service: estoque, reservas, eventos, erros e tipos."""

from app.domain.base import OrderId, ProductId, ReservationId
from app.domain.errors import (
    InventoryError,
    OutOfStockError,
    StockNotFoundError,
)
from app.domain.events import (
    DomainEvent,
    InventoryReserved,
    OrderCreated,
    OrderItem,
    OutOfStock,
)
from app.domain.stock import Reservation, StockLevel

__all__ = [
    "DomainEvent",
    "InventoryError",
    "InventoryReserved",
    "OrderCreated",
    "OrderId",
    "OrderItem",
    "OutOfStock",
    "OutOfStockError",
    "ProductId",
    "Reservation",
    "ReservationId",
    "StockLevel",
    "StockNotFoundError",
]
