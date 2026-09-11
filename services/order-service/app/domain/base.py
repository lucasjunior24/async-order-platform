"""Value objects e tipos primitivos do domínio de pedidos."""

from enum import StrEnum
from typing import NewType
from uuid import UUID

OrderId = NewType("OrderId", UUID)
ProductId = NewType("ProductId", int)
CustomerId = NewType("CustomerId", int)


class OrderStatus(StrEnum):
    """Estados possíveis de um pedido ao longo do fluxo assíncrono."""

    PENDING = "PENDING"
    PAYMENT_APPROVED = "PAYMENT_APPROVED"
    INVENTORY_RESERVED = "INVENTORY_RESERVED"
    CONFIRMED = "CONFIRMED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    OUT_OF_STOCK = "OUT_OF_STOCK"
