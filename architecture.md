# 🏛️ Arquitetura do Sistema — Plataforma de Processamento Assíncrono de Pedidos

> Documento de arquitetura técnica: tecnologias, estrutura, tipagem estática, regras de lint e regras de testes.

---

## 1. Visão Geral

Backend de e-commerce orientado a eventos, com microsserviços isolados por domínio de negócio, comunicação assíncrona via RabbitMQ e observabilidade distribuída.

```
                         ┌─────────────────┐
                         │    Cliente      │
                         └────────┬────────┘
                                  │ HTTP
                                  ▼
                         ┌─────────────────┐
                         │   API Gateway   │
                         │    (FastAPI)    │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │  Order Service  │
                         │     FastAPI     │
                         │  orders_db      │
                         └────────┬────────┘
                                  │ Transactional Outbox
                                  ▼
                             ┌─────────┐
                             │RabbitMQ │
                             └────┬────┘
           ┌──────────────────────┼──────────────────────┐
           ▼                      ▼                      ▼
  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
  │ Payment Service │   │Inventory Service│   │ Notification   │
  │  payments_db    │   │  inventory_db   │   │  Service (Redis)│
  │  + Redis Cache  │   │   + Redis Cache │   └─────────────────┘
  └─────────────────┘   └─────────────────┘
```

---

## 2. Tecnologias

### 2.1 Linguagem e Frameworks

| Camada | Tecnologia | Versão | Justificativa |
|--------|------------|--------|---------------|
| Linguagem | Python | 3.12+ | Suporte moderno a typing (`X | Y`, `TypeAlias`, `Generic`) |
| Ambiente e dependências | uv | — | Gerenciamento de Python, ambiente virtual e lockfile (`uv.lock`) |
| API | FastAPI | 0.115+ | Async nativo, pydantic, OpenAPI automático |
| Validação | Pydantic | 2.x | Models tipados, serialização, eventos |
| ORM | SQLAlchemy | 2.x | Tipado com `Mapped[]`, `mapped_column` |
| Migrations | Alembic | 1.x | Versionamento de schema |
| Mensageria | aio-pika | 9.x | Consumer/produtor async RabbitMQ |
| Cache | redis-py | 5.x | Async Redis client |
| Scheduler | APScheduler | 3.x | Outbox worker polling |

### 2.2 Infraestrutura

| Camada | Tecnologia |
|--------|------------|
| Banco relacional | PostgreSQL 16 (um por serviço) |
| Cache / fila de DLQ stats | Redis 7 |
| Mensageria | RabbitMQ 3.x (com dead-letter exchanges) |
| Observabilidade | OpenTelemetry + Jaeger/Tempo |
| Métricas | Prometheus + Grafana |
| Contêineres | Docker e Docker Compose |
| Orquestração | Kubernetes |

### 2.3 Testes e Qualidade

| Ferramenta | Uso |
|------------|-----|
| pytest | Runner principal + fixtures |
| pytest-asyncio | Testes assíncronos |
| pytest-mock | Mocks de use cases/provedores |
| httpx | Testar endpoints FastAPI |
| testcontainers-python | Postgres/RabbitMQ/Redis reais em integração |
| coverage / pytest-cov | Cobertura de código |
| ruff | Linter + formatador |
| mypy | Type checker estático |

---

## 3. Estrutura de Pastas (por serviço)

```
async-order-platform/
├── services/
│   ├── order-service/
│   │   ├── app/
│   │   │   ├── api/                  # rotas, dependências, schemas HTTP
│   │   │   ├── domain/               # entidades, value objects, eventos, estados
│   │   │   ├── application/          # use cases, portas (interfaces)
│   │   │   ├── infrastructure/       # repos SQLAlchemy, publisher, outbox
│   │   │   └── consumers/            # consumers RabbitMQ
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   ├── integration/
│   │   │   └── e2e/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── alembic/
│   ├── payment-service/
│   ├── inventory-service/
│   └── notification-service/
├── shared/                            # schemas de eventos compartilhados (contrato)
│   ├── events/
│   └── types.py
├── infrastructure/
│   ├── rabbitmq/
│   ├── postgres/
│   ├── redis/
│   └── observability/
├── docker-compose.yml
├── Makefile
└── README.md
```

---

## 4. Camadas e Regras de Dependência

```
api ──────────► application ◄──────────── consumers
                  │
                  ▼
               domain
                  ▲
                  │
            infrastructure
```

Regras:

- `domain` **não importa** nenhuma outra camada (nem FastAPI, nem SQLAlchemy).
- `application` importa apenas `domain` e define portas (protocols).
- `infrastructure` implementa as portas definidas em `application`.
- `api` e `consumers` orquestram `application`.
- **Dependência sempre aponta para dentro** (regra hexagonal).

---

## 5. Tipagem Estática (tudo tipado)

### 5.1 Política

- **Todo** código de produção possui type hints completos.
- `mypy --strict` é obrigatório no CI.
- Proibido `Any` sem justificativa explícita (`# type: ignore[no-any-return]`).
- Modelos de domínio e eventos usam **pydantic** com tipos/constrantes próprios.
- Usamos `NewType` para IDs primitivos (evita troca de parâmetros).

### 5.2 Exemplo de tipagem no domínio

```python
from decimal import Decimal
from uuid import UUID, uuid4
from typing import NewType
from enum import StrEnum

from pydantic import BaseModel, Field, ConfigDict

OrderId = NewType("OrderId", UUID)
ProductId = NewType("ProductId", int)
CustomerId = NewType("CustomerId", int)


class OrderStatus(StrEnum):
    PENDING = "PENDING"
    PAYMENT_APPROVED = "PAYMENT_APPROVED"
    INVENTORY_RESERVED = "INVENTORY_RESERVED"
    CONFIRMED = "CONFIRMED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    OUT_OF_STOCK = "OUT_OF_STOCK"


class OrderItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    product_id: ProductId
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(ge=Decimal("0"))


class Order(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: OrderId = Field(default_factory=lambda: OrderId(uuid4()))
    customer_id: CustomerId
    items: tuple[OrderItem, ...] = ()
    status: OrderStatus = OrderStatus.PENDING

    @property
    def total(self) -> Decimal:
        return sum(
            (item.unit_price * item.quantity for item in self.items),
            start=Decimal("0"),
        )

    def apply(self, event: "OrderEvent") -> "Order":
        ...
```

### 5.3 Exemplo de evento tipado

```python
from datetime import datetime
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, Field


class OrderCreated(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: Literal["OrderCreated"] = "OrderCreated"
    order_id: OrderId
    customer_id: CustomerId
    trace_id: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PaymentApproved(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: Literal["PaymentApproved"] = "PaymentApproved"
    order_id: OrderId
    payment_id: UUID
    trace_id: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

### 5.4 Exemplo de porta tipada (Protocol)

```python
from collections.abc import Sequence
from typing import Protocol


class OrderRepository(Protocol):
    async def add(self, order: Order) -> None: ...
    async def get(self, order_id: OrderId) -> Order | None: ...
    async def list_by_status(self, status: OrderStatus) -> Sequence[Order]: ...


class EventPublisher(Protocol):
    async def publish(self, event: OrderCreated) -> None: ...
```

### 5.5 Configuração do mypy

```toml
# pyproject.toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_unused_ignores = true
warn_redundant_casts = true
warn_unreachable = true
disallow_untyped_defs = true
disallow_any_generics = true
no_implicit_optional = true
check_untyped_defs = true

[[tool.mypy.overrides]]
module = ["pytest", "pytest_asyncio"]
ignore_missing_imports = true
```

---

## 6. Regras de Lint e Formatação

### 6.1 Ruff (linter + formatador)

```toml
# pyproject.toml
[tool.ruff]
target-version = "py312"
line-length = 100
src = ["app", "tests"]

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort (ordenação de imports)
    "N",    # pep8-naming
    "UP",   # pyupgrade (sintaxe moderna)
    "B",    # flake8-bugbear
    "C4",   # flake8-comprehensions
    "SIM",  # flake8-simplify
    "RUF",  # ruff-specific
    "ANN",  # flake8-annotations (type hints obrigatórios)
    "ASYNC",# async best practices
    "TID",  # flake8-tidy-imports (banir import relativo)
]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["ANN", "S101"]  # testes podem omitir anotação e usar assert

[tool.ruff.lint.isort]
known-first-party = ["app", "shared"]
```

### 6.2 Regras de estilo obrigatórias

- **Line length:** 100 caracteres.
- **Imports:** ordenados via `isort` (std lib → terceiros → first-party).
- **Nomes:** `snake_case` para funções/variáveis, `PascalCase` para classes, `UPPER_CASE` para constantes.
- **Docstrings:** obrigatórias em módulos, classes e funções públicas (exceção: property e testes).
- **Strings:** aspas duplas (`"`) em todo o projeto.
- **Tipos:** anotações em **todos** os parâmetros e retornos (regra `ANN`).
- **Async:** funções async precisam de `await`; regra `ASYNC` detecta código async bloqueante.
- **Sem `Any` implícito:** a regra `ANN` + mypy cobrem isso.
- **Immutable where possible:** preferir `frozen=True` em models pydantic e `tuple` sobre `list`.

### 6.3 Comandos de qualidade

```bash
# lint
uv run ruff check .

# formatação
uv run ruff format .

# type checking
uv run mypy .

# testes
uv run pytest

# formatação + lint + tipos (tudo)
make check
```

As ferramentas são executadas dentro do ambiente gerenciado pelo uv via `uv run`, garantindo que a versão correta do Python e das dependências (travadas no `uv.lock`) seja usada.

### 6.4 Pre-commit

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic, sqlalchemy]
```

---

## 7. Regras de Testes

### 7.1 Pirâmide de testes

```
        /        E2E (poucos)        \
       /      Integração (média)      \
      /     Contrato (média)           \
     /   Unitários (muitos)             \
    /___________________________________\
```

| Camada | Diretório | O que testa | Infra |
|--------|-----------|-------------|-------|
| Unitário | `tests/unit/` | Domínio, use cases, validators | Nenhuma (mocks) |
| Contrato | `tests/contract/` | Schema dos eventos (pydantic) | Nenhuma |
| Integração | `tests/integration/` | API, DB, fila, cache reais | Docker |
| E2E | `tests/e2e/` | Fluxo completo `POST /orders` → `CONFIRMED` | Docker (todos os serviços) |

### 7.2 Regras obrigatórias

- **TDD:** todo código de produção nasce de um teste falhando (RED → GREEN → REFACTOR).
- **Nomenclatura:** `test_<comportamento>_<cenário>` com nomes descritivos.
- **Um assert por comportamento** (não encher um teste de asserts desconexos).
- **Isolamento:** unitários não tocam rede, banco ou tempo real.
- **Sem sleep:** tempo é mockado (ex.: backoff usa `freezegun` ou injeção de `clock`).
- **Fixtures:** compartilhar setup via `conftest.py`, nunca entre testes por estado global.
- **Cobertura mínima:** 80% no domínio/aplicação (regra de CI).
- **Testes rápidos:** unitários devem rodar em segundos (sem I/O).

### 7.3 Configuração do pytest

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = [
    "--strict-markers",
    "--strict-config",
    "--disable-warnings",
    "-ra",
]
markers = [
    "unit: testes unitários (sem infra)",
    "integration: testes com infraestrutura real (Docker)",
    "e2e: fluxo completo com todos os serviços",
]

[tool.coverage.run]
source = ["app"]
branch = true

[tool.coverage.report]
show_missing = true
fail_under = 80
```

### 7.4 Exemplo de teste unitário tipado

```python
from decimal import Decimal

from app.domain.order import Order, OrderItem, OrderStatus, ProductId, CustomerId


def test_order_total_sums_all_items() -> None:
    order = Order(
        customer_id=CustomerId(123),
        items=(
            OrderItem(product_id=ProductId(10), quantity=2, unit_price=Decimal("50.00")),
            OrderItem(product_id=ProductId(20), quantity=1, unit_price=Decimal("50.00")),
        ),
    )

    assert order.total == Decimal("150.00")


def test_cannot_create_order_with_empty_items() -> None:
    with pytest.raises(EmptyOrderError):
        Order(customer_id=CustomerId(123), items=())
```

### 7.5 Exemplo de teste de integração

```python
import pytest
from httpx import AsyncClient

from app.domain.order import OrderStatus

pytestmark = pytest.mark.integration


async def test_post_orders_persists_order_and_outbox(
    api_client: AsyncClient,
) -> None:
    response = await api_client.post(
        "/orders",
        json={
            "customer_id": 123,
            "items": [{"product_id": 10, "quantity": 2}],
        },
    )

    assert response.status_code == 201
    # o outbox é verificado via repositório real
```

---

## 8. Configuração Consolidada (pyproject.toml)

```toml
[project]
name = "order-service"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "pydantic>=2.8.0",
    "pydantic-settings>=2.4.0",
    "sqlalchemy[asyncio]>=2.0.30",
    "asyncpg>=0.29.0",
    "alembic>=1.13.0",
    "aio-pika>=9.4.0",
    "redis>=5.0.0",
    "opentelemetry-api>=1.25.0",
    "opentelemetry-sdk>=1.25.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.0",
    "pytest-mock>=3.14.0",
    "pytest-cov>=5.0.0",
    "httpx>=0.27.0",
    "testcontainers>=4.5.0",
    "ruff>=0.5.0",
    "mypy>=1.10.0",
]
```

### 8.1 Gerenciamento de ambiente e lockfile (uv)

O `pyproject.toml` é a fonte única de verdade para as dependências; o uv o utiliza diretamente, sem necessidade de `requirements.txt` separado ou `setup.py`.

```bash
# instala/atualiza o ambiente virtual e as dependências a partir do pyproject.toml
uv sync --all-extras

# trava as versões resolvidas em uv.lock (versionar no repositório para builds reproduzíveis)
uv lock

# executa qualquer comando dentro do ambiente virtual (ex.: migrações, testes, linter)
uv run alembic upgrade head
uv run pytest
uv run ruff check .
```

Regras:

- O `uv.lock` é **versionado** no repositório para garantir builds reproduzíveis em CI/produção.
- O ambiente virtual é local ao serviço (ex.: `services/order-service/.venv`) e fica ignorado no `.gitignore`.
- Toda execução de ferramentas do projeto (`pytest`, `ruff`, `mypy`, `alembic`, `uvicorn`) é feita via `uv run`, nunca ativando manualmente o venv.

---

## 9. Observabilidade

| Sinal | Ferramenta | O que mede |
|-------|------------|-----------|
| Traces | OpenTelemetry + Jaeger/Tempo | Latência por serviço, `trace_id` correlacionado |
| Métricas | Prometheus | Taxa de pedidos, tempo de processamento, erros, DLQ |
| Logs | Structured JSON | `trace_id`, `event_id`, `service` em todos os logs |

Regras:

- `trace_id` e `event_id` propagam por todo o fluxo (headers e eventos).
- Logs em JSON estruturado para parse no Loki/ELK.
- Métricas de negócio: `orders_created_total`, `payments_approved_total`, `dlq_messages_total`.

---

## 10. Segurança e Resiliência

- **Idempotência:** consumers usam `processed_events` com `UNIQUE(event_id)`.
- **Retry:** exponential backoff apenas para erros transitórios (`5xx`/timeout).
- **DLQ:** após esgotar retries, mensagem vai para dead-letter e fica auditável.
- **Circuit Breaker:** isola provedor externo em falha (5 falhas → OPEN 30s).
- **Secrets:** via variáveis de ambiente (nunca hardcoded), gerenciadas por pydantic-settings.
- **Validação de entrada:** todos os payloads passam por pydantic.

---

## 11. Resumo das Decisões

| Decisão | Escolha |
|---------|---------|
| Arquitetura | Microservices por bounded context |
| Comunicação | Eventos assíncronos (RabbitMQ) |
| Persistência | PostgreSQL por serviço + Transactional Outbox |
| Cache | Redis com invalidação orientada a eventos |
| Tipagem | 100% tipado, `mypy --strict` |
| Lint/Formatação | Ruff (E, W, F, I, N, UP, B, C4, SIM, RUF, ANN, ASYNC, TID) |
| Testes | TDD, pytest, pirâmide unit → contrato → integração → E2E |
| CI | Ruff + mypy + pytest + coverage ≥ 80% |
| Observabilidade | OpenTelemetry + Prometheus + Grafana |
| Resiliência | Idempotência, retry, DLQ, circuit breaker |