"""Eventos de domínio do Payment Service (contrato tipado).

Contém tanto o evento de entrada (`OrderCreated`, publicado pelo Order Service)
quanto os eventos de saída com o resultado do pagamento.

Todo evento carrega `event_id` (idempotência), `event_type` (roteamento),
`order_id` (correlação) e `trace_id` (distributed tracing).
"""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.domain.base import OrderId, PaymentId


class DomainEvent(BaseModel):
    """Base comum de todos os eventos que trafegam pelo Payment Service."""

    model_config = ConfigDict(frozen=True)

    event_id: UUID = Field(default_factory=uuid4)
    order_id: OrderId
    trace_id: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OrderCreated(DomainEvent):
    """Evento de entrada: um pedido foi criado e deve ser pago."""

    event_type: Literal["OrderCreated"] = "OrderCreated"
    customer_id: int


class PaymentApproved(DomainEvent):
    """Evento de saída: o pagamento do pedido foi aprovado."""

    event_type: Literal["PaymentApproved"] = "PaymentApproved"
    payment_id: PaymentId


class PaymentFailed(DomainEvent):
    """Evento de saída: o pagamento do pedido falhou."""

    event_type: Literal["PaymentFailed"] = "PaymentFailed"
    reason: str
