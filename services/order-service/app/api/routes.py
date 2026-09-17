"""Rotas HTTP do Order Service (health, orders, admin e metrics).

A camada ``api`` apenas orquestra a camada ``application``, seguindo a regra
hexagonal. As dependências padrão são adaptadores in-memory; a composição de
raiz (``app.main``) pode sobrescrevê-las com implementações reais via
``dependency_overrides``.
"""

from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from app.application import CreateOrder, DeadLetterAdmin
from app.domain import OrderItem, ProductId
from app.infrastructure.in_memory import (
    InMemoryDeadLetterRepository,
    InMemoryEventPublisher,
    InMemoryUnitOfWork,
)
from app.infrastructure.tracing import get_trace_id


class OrderItemPayload(BaseModel):
    """Item do pedido recebido no request HTTP."""

    product_id: int
    quantity: int = Field(gt=0)
    unit_price: str = "0.00"


class CreateOrderPayload(BaseModel):
    """Payload do `POST /orders`."""

    customer_id: int
    items: list[OrderItemPayload]


def get_create_order() -> CreateOrder:
    """Fornece o use case ``CreateOrder`` com dependências in-memory."""
    return CreateOrder(InMemoryUnitOfWork(), trace_id=get_trace_id())


def get_dead_letter_admin() -> DeadLetterAdmin:
    """Fornece o use case ``DeadLetterAdmin`` com dependências in-memory."""
    return DeadLetterAdmin(InMemoryDeadLetterRepository(), InMemoryEventPublisher())


router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Endpoint de saúde do serviço."""
    return {"status": "ok"}


@router.post("/orders", status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: CreateOrderPayload,
    create: Annotated[CreateOrder, Depends(get_create_order)],
) -> dict[str, str]:
    """Cria um pedido e grava o evento de outbox atomicamente."""
    items = tuple(
        OrderItem(
            product_id=ProductId(item.product_id),
            quantity=item.quantity,
            unit_price=Decimal(item.unit_price),
        )
        for item in payload.items
    )
    order_id = await create.execute(customer_id=payload.customer_id, items=items)
    return {"order_id": str(order_id)}


@router.get("/admin/dead-letters")
async def list_dead_letters(
    admin: Annotated[DeadLetterAdmin, Depends(get_dead_letter_admin)],
) -> list[dict[str, object]]:
    """Lista as mensagens atualmente na dead letter queue."""
    messages = await admin.list()
    return [message.model_dump(mode="json") for message in messages]


@router.post("/admin/dead-letters/{message_id}/reprocess")
async def reprocess_dead_letter(
    message_id: UUID,
    admin: Annotated[DeadLetterAdmin, Depends(get_dead_letter_admin)],
) -> dict[str, str]:
    """Republica uma mensagem da DLQ no broker e a remove da fila morta."""
    event = await admin.reprocess(message_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Mensagem não encontrada.")
    return {"event_id": str(event.event_id)}


@router.get("/metrics")
async def metrics() -> Response:
    """Exposição das métricas do serviço no formato texto do Prometheus."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
