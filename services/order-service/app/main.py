"""Ponto de entrada da API do Order Service (composição de raiz).

Monta a aplicação FastAPI a partir das rotas definidas em ``app.api.routes``.
"""

from fastapi import FastAPI

from app.api.routes import router
from app.infrastructure.tracing import configure_tracing


def create_app(service_name: str = "order-service") -> FastAPI:
    """Cria e configura a aplicação FastAPI."""
    configure_tracing(service_name)

    app = FastAPI(title="Order Service")
    app.include_router(router)
    return app


app = create_app()
