"""Teste de integração da API do Order Service.

Integra HTTP → aplicação → persistência (in-memory), validando o caminho do
``POST /orders`` até o registro atômico do pedido e do evento de outbox, além do
endpoint de saúde. Os adaptadores in-memory são injetados via
``dependency_overrides`` para que o estado persistido seja inspecionável no teste.
"""

from uuid import UUID

import httpx
import pytest

from app.api.routes import get_create_order
from app.application import CreateOrder
from app.domain import OrderCreated, OrderId, OrderStatus
from app.infrastructure.in_memory import InMemoryUnitOfWork
from app.main import create_app

pytestmark = pytest.mark.integration


async def test_health_endpoint() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_post_orders_persists_order_and_outbox() -> None:
    app = create_app()
    uow = InMemoryUnitOfWork()
    app.dependency_overrides[get_create_order] = lambda: CreateOrder(
        uow, trace_id="integration-trace"
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/orders",
            json={
                "customer_id": 123,
                "items": [{"product_id": 10, "quantity": 2, "unit_price": "25.00"}],
            },
        )

    assert response.status_code == 201
    order_id = OrderId(UUID(response.json()["order_id"]))

    order = await uow.orders.get(order_id)
    assert order is not None
    assert order.status is OrderStatus.PENDING

    event = uow.outbox.first()
    assert isinstance(event, OrderCreated)
    assert event.order_id == order_id
    assert event.trace_id == "integration-trace"
    assert uow.orders.count() == 1
    assert uow.outbox.count() == 1
