"""Domínio de pagamentos: entidade e estados."""

from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.domain.base import OrderId, PaymentId


class PaymentStatus(StrEnum):
    """Estados possíveis de um pagamento processado."""

    APPROVED = "APPROVED"
    FAILED = "FAILED"


class Payment(BaseModel):
    """Pagamento imutável resultante do processamento de um pedido."""

    model_config = ConfigDict(frozen=True)

    id: PaymentId = Field(default_factory=lambda: PaymentId(uuid4()))
    order_id: OrderId
    status: PaymentStatus
    reason: str | None = Field(default=None)
