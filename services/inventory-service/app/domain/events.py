"""Eventos de domínio do Inventory Service (contrato tipado).

Contém o evento de entrada (`OrderCreated`, publicado pelo Order Service) e os
eventos de saída com o resultado da reserva de estoque, que espelham o contrato
consumido pelo Order Service.

Todo evento carrega `event_id` (idempotência), `event_type` (roteamento),
`order_id` (correlação) e `trace_id` (distributed tracing).
"""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.domain.base import OrderId, ProductId


class DomainEvent(BaseModel):
    """Base comum de todos os eventos que trafegam pelo Inventory Service."""

    model_config = ConfigDict(frozen=True)

    event_id: UUID = Field(default_factory=uuid4)
    order_id: OrderId
    trace_id: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OrderItem(BaseModel):
    """Item do pedido: produto e quantidade demandada."""

    model_config = ConfigDict(frozen=True)

    product_id: ProductId
    quantity: int = Field(gt=0)


class OrderCreated(DomainEvent):
    """Evento de entrada: um pedido foi criado e deve ter estoque reservado."""

    event_type: Literal["OrderCreated"] = "OrderCreated"
    items: tuple[OrderItem, ...] = Field(min_length=1)


class InventoryReserved(DomainEvent):
    """Evento de saída: o estoque do pedido foi reservado (nível de pedido)."""

    event_type: Literal["InventoryReserved"] = "InventoryReserved"


class OutOfStock(DomainEvent):
    """Evento de saída: não há estoque suficiente para o pedido (nível de pedido)."""

    event_type: Literal["OutOfStock"] = "OutOfStock"
