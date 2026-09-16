"""Domínio do Notification Service: eventos, notificações e tipos primitivos."""

from app.domain.base import NotificationId, OrderId
from app.domain.events import (
    DomainEvent,
    InventoryReserved,
    OrderCreated,
    OutOfStock,
    PaymentApproved,
    PaymentFailed,
)
from app.domain.notification import Notification

__all__ = [
    "DomainEvent",
    "InventoryReserved",
    "Notification",
    "NotificationId",
    "OrderCreated",
    "OrderId",
    "OutOfStock",
    "PaymentApproved",
    "PaymentFailed",
]
