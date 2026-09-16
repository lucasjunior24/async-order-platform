"""Use case de envio de notificação (consumer de eventos do fluxo de pedido).

Orquestra idempotência (T6.2) e o envio da notificação via provedor mockado
(T6.1). Cada entrega duplicada é um no-op: o e-mail só é enviado uma vez por
``event_id``.
"""

from collections.abc import Callable

from app.application.ports import NotificationSender, ProcessedEvents
from app.domain import (
    DomainEvent,
    InventoryReserved,
    Notification,
    OrderCreated,
    OutOfStock,
    PaymentApproved,
    PaymentFailed,
)


class SendNotification:
    """Envia uma notificação ao cliente exatamente uma vez por evento consumido."""

    def __init__(
        self,
        sender: NotificationSender,
        processed: ProcessedEvents,
    ) -> None:
        self._sender = sender
        self._processed = processed

    async def process(self, event: DomainEvent) -> Notification | None:
        """Envia a notificação do evento, retornando ``None`` se já processado.

        A notificação é composta conforme o tipo do evento (``event_type``) e o
        envio é guardado pela idempotência de ``processed_events``.
        """
        if not await self._processed.mark_processed(event.event_id):
            return None

        notification = self._compose(event)
        await self._sender.send(notification)
        return notification

    def _compose(self, event: DomainEvent) -> Notification:
        """Monta a mensagem (assunto + corpo) a partir do tipo do evento."""
        template = _TEMPLATES.get(type(event))
        if template is None:
            raise ValueError(f"Evento não notificável: {event.event_type}")

        subject, body = template(event)
        return Notification(
            recipient_email=event.recipient_email,
            subject=subject,
            body=body,
            trace_id=event.trace_id,
        )


def _order_received(event: DomainEvent) -> tuple[str, str]:
    assert isinstance(event, OrderCreated)
    return (
        "Pedido recebido",
        f"Seu pedido {event.order_id} foi recebido e está sendo processado.",
    )


def _payment_approved(event: DomainEvent) -> tuple[str, str]:
    assert isinstance(event, PaymentApproved)
    return (
        "Pagamento aprovado",
        f"O pagamento do pedido {event.order_id} foi aprovado.",
    )


def _payment_failed(event: DomainEvent) -> tuple[str, str]:
    assert isinstance(event, PaymentFailed)
    return (
        "Falha no pagamento",
        f"O pagamento do pedido {event.order_id} falhou: {event.reason}.",
    )


def _inventory_reserved(event: DomainEvent) -> tuple[str, str]:
    assert isinstance(event, InventoryReserved)
    return (
        "Estoque reservado",
        f"O estoque do pedido {event.order_id} foi reservado.",
    )


def _out_of_stock(event: DomainEvent) -> tuple[str, str]:
    assert isinstance(event, OutOfStock)
    return (
        "Produto indisponível",
        f"Não há estoque suficiente para o pedido {event.order_id}.",
    )


_TEMPLATES: dict[type[DomainEvent], Callable[[DomainEvent], tuple[str, str]]] = {
    OrderCreated: _order_received,
    PaymentApproved: _payment_approved,
    PaymentFailed: _payment_failed,
    InventoryReserved: _inventory_reserved,
    OutOfStock: _out_of_stock,
}
