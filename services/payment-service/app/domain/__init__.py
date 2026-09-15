"""Domínio do Payment Service: entidades, eventos, erros e tipos primitivos."""

from app.domain.base import OrderId, PaymentId
from app.domain.errors import (
    NonRetryablePaymentError,
    PaymentError,
    TransientPaymentError,
)
from app.domain.events import (
    DomainEvent,
    OrderCreated,
    PaymentApproved,
    PaymentFailed,
)
from app.domain.payment import Payment, PaymentStatus

__all__ = [
    "DomainEvent",
    "NonRetryablePaymentError",
    "OrderCreated",
    "OrderId",
    "Payment",
    "PaymentApproved",
    "PaymentError",
    "PaymentFailed",
    "PaymentId",
    "PaymentStatus",
    "TransientPaymentError",
]
