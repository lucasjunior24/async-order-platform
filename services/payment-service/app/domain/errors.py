"""Erros do domínio de pagamentos (provedor externo).

Separa erros transitórios (candidatos a retry e trip do circuit breaker) de
erros de negócio (sem retry), conforme a política de resiliência do serviço.
"""


class PaymentError(Exception):
    """Base para erros do provedor de pagamento externo."""


class TransientPaymentError(PaymentError):
    """Erro transitório (5xx/timeout): candidato a retry e trip do circuit breaker."""


class NonRetryablePaymentError(PaymentError):
    """Erro de negócio (ex.: saldo insuficiente): não deve ser reenviado."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
