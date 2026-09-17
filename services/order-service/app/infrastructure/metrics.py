"""Métricas de negócio com Prometheus (T7.3).

Expõe contadores e histogramas usando `prometheus_client`. As métricas de
negócio seguem a convenção do architecture.md:

- ``orders_created_total``
- ``payments_approved_total``
- ``dlq_messages_total``
"""

from prometheus_client import Counter, Histogram

orders_created_total = Counter(
    "orders_created_total",
    "Total de pedidos criados.",
)

payments_approved_total = Counter(
    "payments_approved_total",
    "Total de pagamentos aprovados.",
)

dlq_messages_total = Counter(
    "dlq_messages_total",
    "Total de mensagens roteadas para a dead letter queue.",
)

order_processing_duration_seconds = Histogram(
    "order_processing_duration_seconds",
    "Tempo de processamento de um pedido em segundos.",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
