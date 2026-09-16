"""Domínio de notificações: a mensagem enviada ao cliente."""

from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.domain.base import NotificationId


class Notification(BaseModel):
    """Notificação imutável enviada ao cliente a partir de um evento."""

    model_config = ConfigDict(frozen=True)

    id: NotificationId = Field(
        default_factory=lambda: NotificationId(uuid4()),
    )
    recipient_email: str
    subject: str
    body: str
    trace_id: str
