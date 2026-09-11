"""Eventos de domínio do Order Service (contrato tipado).

Todo evento carrega `event_id` (idempotência), `event_type` (roteamento),
`order_id` (correlação) e `trace_id` (distributed tracing).
"""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.domain.base import OrderId


class OrderEvent(BaseModel):
    """Base comum de todos os eventos de domínio do pedido."""

    model_config = ConfigDict(frozen=True)

    event_id: UUID = Field(default_factory=uuid4)
    order_id: OrderId
    trace_id: str
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )


class OrderCreated(OrderEvent):
    """Indica que um pedido foi criado e deve ser processado."""

    event_type: Literal["OrderCreated"] = "OrderCreated"
    customer_id: int


class PaymentApproved(OrderEvent):
    """Indica que o pagamento do pedido foi aprovado."""

    event_type: Literal["PaymentApproved"] = "PaymentApproved"
    payment_id: UUID


class PaymentFailed(OrderEvent):
    """Indica que o pagamento do pedido falhou."""

    event_type: Literal["PaymentFailed"] = "PaymentFailed"
    reason: str = "unknown"


class InventoryReserved(OrderEvent):
    """Indica que o estoque do pedido foi reservado."""

    event_type: Literal["InventoryReserved"] = "InventoryReserved"


class OutOfStock(OrderEvent):
    """Indica que não há estoque suficiente para o pedido."""

    event_type: Literal["OutOfStock"] = "OutOfStock"
