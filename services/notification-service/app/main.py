"""Ponto de entrada do Notification Service (liveness/readiness).

Em produção, este processo também inicia o consumer aio-pika que consome os
eventos do fluxo de pedido. Nesta versão, expõe apenas o endpoint de saúde,
usado pelas probes do Kubernetes e pelo docker-compose.
"""

from fastapi import FastAPI

app = FastAPI(title="Notification Service")


@app.get("/health")
async def health() -> dict[str, str]:
    """Endpoint de saúde do serviço."""
    return {"status": "ok"}
