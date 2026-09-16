"""Value objects e tipos primitivos do domínio de notificações."""

from typing import NewType
from uuid import UUID

OrderId = NewType("OrderId", UUID)
NotificationId = NewType("NotificationId", UUID)
