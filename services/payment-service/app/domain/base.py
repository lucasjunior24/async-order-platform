"""Value objects e tipos primitivos do domínio de pagamentos."""

from typing import NewType
from uuid import UUID

OrderId = NewType("OrderId", UUID)
PaymentId = NewType("PaymentId", UUID)
