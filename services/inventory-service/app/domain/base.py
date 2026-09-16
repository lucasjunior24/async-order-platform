"""Value objects e tipos primitivos do domínio de estoque."""

from typing import NewType
from uuid import UUID

OrderId = NewType("OrderId", UUID)
ProductId = NewType("ProductId", int)
ReservationId = NewType("ReservationId", UUID)
