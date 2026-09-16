"""Consumer de eventos do fluxo de pedido no Notification Service.

Adaptador que recebe um evento de domínio e delega o processamento ao use case
``SendNotification``, que aplica idempotência e envia a notificação ao cliente.
"""

from app.application.send_notification import SendNotification
from app.domain import DomainEvent, Notification


class NotificationConsumer:
    """Encapsula o tratamento de mensagens de eventos do pedido.

    É o ponto de entrada orquestrado pela camada de infraestrutura de
    mensageria (aio-pika), mantendo a regra hexagonal: consumers só orquestram a
    aplicação, sem lógica de negócio.
    """

    def __init__(self, send_notification: SendNotification) -> None:
        self._send_notification = send_notification

    async def handle(self, event: DomainEvent) -> Notification | None:
        """Processa o evento, retornando a notificação enviada (se houver)."""
        return await self._send_notification.process(event)
