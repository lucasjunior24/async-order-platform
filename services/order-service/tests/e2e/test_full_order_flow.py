"""Teste E2E (T8.1): ``POST /orders`` → ``CONFIRMED`` atravessando os 4 serviços.

Simula, em um único processo, a orquestração orientada a eventos descrita no
architecture.md:

1. ``POST /orders`` cria o pedido e grava o ``OrderCreated`` no outbox (Order).
2. O Outbox Worker publica o evento no broker.
3. O Payment Service consome ``OrderCreated`` e emite ``PaymentApproved``.
4. O Inventory Service consome ``OrderCreated`` e emite ``InventoryReserved``.
5. O Notification Service consome os eventos e envia as notificações.
6. O Order Service consome os resultados e converge o pedido para ``CONFIRMED``.

Como cada serviço define o próprio pacote ``app`` (colisão de nomes), os serviços
downstream são carregados trocando temporariamente ``sys.path``/``sys.modules``
(vide ``_service_scope``), preservando o isolamento dos contratos de eventos de
cada bounded context.
"""

import importlib
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import httpx
import pytest

from app.api.routes import get_create_order
from app.application import ConfirmOrder, CreateOrder, OutboxWorker
from app.domain import (
    InventoryReserved,
    OrderCreated,
    OrderId,
    OrderStatus,
    PaymentApproved,
)
from app.infrastructure.in_memory import (
    InMemoryEventPublisher,
    InMemoryProcessedEvents,
    InMemoryUnitOfWork,
)
from app.main import create_app

pytestmark = pytest.mark.e2e

_CUSTOMER_ID = 123
_PRODUCT_ID = 10
_QUANTITY = 2
_TRACE_ID = "e2e-trace-1"
_RECIPIENT = "cliente@example.com"

# Diretório ``services/``: parents[0]=e2e, [1]=tests, [2]=order-service, [3]=services.
_SERVICES_DIR = Path(__file__).resolve().parents[3]


@contextmanager
def _service_scope(service: str) -> Iterator[None]:
    """Troca temporariamente ``sys.path``/``sys.modules`` para importar ``app``.

    Remove o pacote ``app`` atual (Order Service) e insere o diretório do serviço
    ``service`` no topo do ``sys.path``, permitindo que ``importlib.import_module``
    resolva o ``app`` do serviço downstream. Ao sair, restaura o estado original.
    """
    root = _SERVICES_DIR / service
    saved = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]
    sys.path.insert(0, str(root))
    try:
        yield
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved)
        sys.path.remove(str(root))


def _load_payment() -> SimpleNamespace:
    with _service_scope("payment-service"):
        domain: Any = importlib.import_module("app.domain")
        application: Any = importlib.import_module("app.application")
        infra: Any = importlib.import_module("app.infrastructure.in_memory")
        return SimpleNamespace(
            OrderCreated=domain.OrderCreated,
            PaymentApproved=domain.PaymentApproved,
            ProcessPayment=application.ProcessPayment,
            CircuitBreaker=application.CircuitBreaker,
            exponential_backoff=application.exponential_backoff,
            InMemoryPaymentProvider=infra.InMemoryPaymentProvider,
            InMemoryProcessedEvents=infra.InMemoryProcessedEvents,
            InMemoryPaymentRepository=infra.InMemoryPaymentRepository,
            InMemoryEventPublisher=infra.InMemoryEventPublisher,
            InMemoryDeadLetterQueue=infra.InMemoryDeadLetterQueue,
        )


def _load_inventory() -> SimpleNamespace:
    with _service_scope("inventory-service"):
        domain: Any = importlib.import_module("app.domain")
        application: Any = importlib.import_module("app.application")
        infra: Any = importlib.import_module("app.infrastructure.in_memory")
        return SimpleNamespace(
            OrderCreated=domain.OrderCreated,
            OrderItem=domain.OrderItem,
            StockLevel=domain.StockLevel,
            InventoryReserved=domain.InventoryReserved,
            ReserveStock=application.ReserveStock,
            StockService=application.StockService,
            InMemoryStockRepository=infra.InMemoryStockRepository,
            InMemoryStockCache=infra.InMemoryStockCache,
            InMemoryReservationRepository=infra.InMemoryReservationRepository,
            InMemoryProcessedEvents=infra.InMemoryProcessedEvents,
            InMemoryEventPublisher=infra.InMemoryEventPublisher,
        )


def _load_notification() -> SimpleNamespace:
    with _service_scope("notification-service"):
        domain: Any = importlib.import_module("app.domain")
        application: Any = importlib.import_module("app.application")
        infra: Any = importlib.import_module("app.infrastructure.in_memory")
        return SimpleNamespace(
            OrderCreated=domain.OrderCreated,
            PaymentApproved=domain.PaymentApproved,
            InventoryReserved=domain.InventoryReserved,
            SendNotification=application.SendNotification,
            InMemoryNotificationSender=infra.InMemoryNotificationSender,
            InMemoryProcessedEvents=infra.InMemoryProcessedEvents,
        )


async def _noop_sleep(delay: float) -> None:
    """Sleep no-op para não aguardar o backoff exponencial no teste."""
    del delay


async def test_full_order_flow() -> None:
    """Fluxo completo: ``POST /orders`` converge para ``CONFIRMED``."""
    payment = _load_payment()
    inventory = _load_inventory()
    notification = _load_notification()

    app = create_app()
    uow = InMemoryUnitOfWork()
    app.dependency_overrides[get_create_order] = lambda: CreateOrder(uow, trace_id=_TRACE_ID)

    # 1) Cria o pedido via HTTP (Order Service).
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/orders",
            json={
                "customer_id": _CUSTOMER_ID,
                "items": [
                    {
                        "product_id": _PRODUCT_ID,
                        "quantity": _QUANTITY,
                        "unit_price": "25.00",
                    },
                ],
            },
        )

    assert response.status_code == 201
    order_id = OrderId(UUID(response.json()["order_id"]))

    # 2) Ordem + outbox gravados atomicamente.
    order = await uow.orders.get(order_id)
    assert order is not None
    assert order.status is OrderStatus.PENDING

    event = uow.outbox.first()
    assert isinstance(event, OrderCreated)
    assert event.order_id == order_id
    assert event.trace_id == _TRACE_ID

    # 3) Outbox Worker publica o ``OrderCreated``.
    publisher = InMemoryEventPublisher()
    worker = OutboxWorker(uow, publisher)
    published = await worker.run()
    assert published == 1
    assert len(publisher.published) == 1

    # 4) Payment Service processa ``OrderCreated`` e aprova o pagamento.
    pay_service = payment.ProcessPayment(
        payment.InMemoryPaymentProvider(),
        payment.InMemoryProcessedEvents(),
        payment.InMemoryPaymentRepository(),
        payment.InMemoryEventPublisher(),
        payment.InMemoryDeadLetterQueue(),
        breaker=payment.CircuitBreaker(failure_threshold=5, recovery_timeout=30),
        max_attempts=3,
        backoff=payment.exponential_backoff(base=1),
        sleep=_noop_sleep,
    )
    pay_result = await pay_service.process(
        payment.OrderCreated(order_id=order_id, customer_id=_CUSTOMER_ID, trace_id=_TRACE_ID)
    )
    assert pay_result is not None
    assert pay_result.event_type == "PaymentApproved"
    payment_approved = PaymentApproved(
        order_id=order_id,
        payment_id=pay_result.payment_id,
        trace_id=pay_result.trace_id,
    )

    # 5) Inventory Service reserva o estoque do pedido.
    inv_repo = inventory.InMemoryStockRepository()
    inv_repo.add(inventory.StockLevel(product_id=_PRODUCT_ID, available=100))
    inv_service = inventory.ReserveStock(
        inventory.StockService(inv_repo, inventory.InMemoryStockCache()),
        inventory.InMemoryReservationRepository(),
        inventory.InMemoryProcessedEvents(),
        inventory.InMemoryEventPublisher(),
    )
    inv_result = await inv_service.process(
        inventory.OrderCreated(
            order_id=order_id,
            trace_id=_TRACE_ID,
            items=(inventory.OrderItem(product_id=_PRODUCT_ID, quantity=_QUANTITY),),
        )
    )
    assert inv_result is not None
    assert inv_result.event_type == "InventoryReserved"
    inventory_reserved = InventoryReserved(order_id=order_id, trace_id=inv_result.trace_id)

    # 6) Notification Service envia as notificações do fluxo (3 eventos).
    notif_sender = notification.InMemoryNotificationSender()
    notif_service = notification.SendNotification(
        notif_sender, notification.InMemoryProcessedEvents()
    )
    await notif_service.process(
        notification.OrderCreated(
            order_id=order_id,
            customer_id=_CUSTOMER_ID,
            recipient_email=_RECIPIENT,
            trace_id=_TRACE_ID,
        )
    )
    await notif_service.process(
        notification.PaymentApproved(
            order_id=order_id, recipient_email=_RECIPIENT, trace_id=_TRACE_ID
        )
    )
    await notif_service.process(
        notification.InventoryReserved(
            order_id=order_id, recipient_email=_RECIPIENT, trace_id=_TRACE_ID
        )
    )
    assert notif_sender.send_count() == 3

    # 7) Order Service consome os resultados e converge para ``CONFIRMED``.
    confirm = ConfirmOrder(uow.orders, InMemoryProcessedEvents())
    await confirm.process(payment_approved)
    await confirm.process(inventory_reserved)

    updated = await uow.orders.get(order_id)
    assert updated is not None
    assert updated.status is OrderStatus.CONFIRMED
