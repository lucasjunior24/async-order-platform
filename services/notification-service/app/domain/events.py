"""Eventos de domínio do Notification Service (contrato tipado).

O serviço é puramente reativo: consome fatos publicados pelo Order, Payment e
Inventory Services para disparar notificações ao cliente.

Todo evento carrega `event_id` (idempotência), `event_type` (roteamento),
`order_id` (correlação), `trace_id` (distributed tracing) e `recipient_email`
(destino da notificação).
"""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.domain.base import OrderId


class DomainEvent(BaseModel):
    """Base comum de todos os eventos consumidos pelo Notification Service."""

    model_config = ConfigDict(frozen=True)

    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    order_id: OrderId
    trace_id: str
    recipient_email: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OrderCreated(DomainEvent):
    """Evento de entrada: um pedido foi criado e o cliente deve ser notificado."""

    event_type: Literal["OrderCreated"] = "OrderCreated"
    customer_id: int


class PaymentApproved(DomainEvent):
    """Evento de entrada: o pagamento do pedido foi aprovado."""

    event_type: Literal["PaymentApproved"] = "PaymentApproved"


class PaymentFailed(DomainEvent):
    """Evento de entrada: o pagamento do pedido falhou."""

    event_type: Literal["PaymentFailed"] = "PaymentFailed"
    reason: str


class InventoryReserved(DomainEvent):
    """Evento de entrada: o estoque do pedido foi reservado."""

    event_type: Literal["InventoryReserved"] = "InventoryReserved"


class OutOfStock(DomainEvent):
    """Evento de entrada: não há estoque suficiente para o pedido."""

    event_type: Literal["OutOfStock"] = "OutOfStock"
