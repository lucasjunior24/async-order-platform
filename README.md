# Async Order Platform

> Uma plataforma de processamento de pedidos orientada a eventos, com qualidade de produção, construída com arquitetura de microsserviços.

[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/fastapi-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Pydantic](https://img.shields.io/badge/pydantic-2.x-e92063.svg)](https://docs.pydantic.dev/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://img.shields.io/badge/CI-passing-brightgreen.svg)]()

Uma plataforma que demonstra como um backend de e-commerce moderno processa pedidos de forma **assíncrona** entre múltiplos serviços, aplicando os padrões e trade-offs esperados de um engenheiro backend sênior: arquitetura orientada a eventos, transactional outbox, consumidores idempotentes, padrões de resiliência, observabilidade e um fluxo de trabalho test-first.

---

## Índice

- [Por que isso existe](#por-que-isso-existe)
- [Arquitetura](#arquitetura)
- [Design do Sistema](#design-do-sistema)
- [Conceitos Fundamentais](#conceitos-fundamentais)
- [Stack Tecnológica](#stack-tecnológica)
- [Estrutura do Repositório](#estrutura-do-repositório)
- [Começando](#começando)
- [Fluxo de Desenvolvimento](#fluxo-de-desenvolvimento)
- [Estratégia de Testes](#estratégia-de-testes)
- [Barreiras de Qualidade](#barreiras-de-qualidade)
- [Observabilidade](#observabilidade)
- [Roadmap](#roadmap)
- [Documentação](#documentação)

---

## Por que isso existe

O objetivo deste repositório não é apenas "usar FastAPI, RabbitMQ e Redis" — mas demonstrar **como** e **por que** essas tecnologias são combinadas para resolver problemas reais de sistemas distribuídos:

| Problema | Solução aplicada |
|----------|------------------|
| Perder eventos entre o commit no banco e a publicação | Transactional Outbox |
| Entrega duplicada de mensagens | Consumidores idempotentes + `UNIQUE(event_id)` |
| Falhas transitórias em provedores | Retry com backoff exponencial |
| Mensagens "poison" em loop infinito | Dead Letter Queue |
| Falhas em cascata em provedores externos | Circuit Breaker |
| Visibilidade de latência entre serviços | Distributed tracing (OpenTelemetry) |
| Consultas de estoque com muitas leituras | Cache Redis com invalidação orientada a eventos |
| Consistência distribuída | Consistência eventual + máquina de estados |
| Regressões durante iteração rápida | TDD + pirâmide de testes completa |

Cada decisão é documentada; nenhuma tecnologia é adicionada "porque está na moda".

---

## Arquitetura

A plataforma é decomposta por **domínio de negócio** (bounded contexts), não por camadas técnicas. Cada serviço é dono dos seus dados e se comunica por meio de **eventos de domínio** — HTTP síncrono apenas onde for estritamente necessário.

```
                         POST /orders
                              │
                              ▼
                     ┌─────────────────┐
                     │   API Gateway   │
                     │    (FastAPI)    │
                     └────────┬────────┘
                              │
                              ▼
                     ┌─────────────────┐
                     │  Order Service  │
                     │   orders_db     │
                     └────────┬────────┘
                              │
                   Transactional Outbox
                              │
                              ▼
                          ┌───────┐
                          │RabbitMQ│
                          └───┬───┘
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Payment Service │  │Inventory Service│  │  Notification   │
│  payments_db    │  │  inventory_db   │  │    Service      │
│  Circuit Breaker│  │   Redis Cache   │  │     Redis       │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### Fluxo de eventos (caminho feliz)

```
OrderCreated ──► Payment Service ──► PaymentApproved ──┐
OrderCreated ──► Inventory Service ─► InventoryReserved ┤──► Order Service ──► CONFIRMED
OrderCreated ──► Notification Service ──────────────────┘
```

A máquina de estados do pedido modela essa convergência eventual de forma explícita:

```
PENDING ──PaymentApproved + InventoryReserved──► CONFIRMED
   │
   └── PaymentFailed ──► ORDER_PAYMENT_FAILED
   └── OutOfStock ────► ORDER_OUT_OF_STOCK
```

---

## Design do Sistema

### Serviços e propriedade dos dados

| Serviço | Responsabilidade | Banco de Dados |
|---------|------------------|----------------|
| `order-service` | Cria pedidos, orquestra transições de estado, emite eventos de domínio | `orders_db` |
| `payment-service` | Processa pagamentos via provedor externo, trata retry/circuit breaker | `payments_db` |
| `inventory-service` | Reserva estoque, serve leituras de estoque em cache | `inventory_db` |
| `notification-service` | Envia e-mails/notificações em eventos | Redis (cache de deduplicação) |

> **Escolha deliberada:** um banco de dados por serviço. Um banco compartilhado entre serviços criaria acoplamento forte e acabaria com o propósito da implantação independente.

### Contratos de comunicação

Toda comunicação entre serviços é **baseada em eventos**, com mensagens definidas como contratos tipados e versionados:

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "OrderCreated",
  "order_id": "ORD-123",
  "customer_id": 123,
  "trace_id": "abc-123",
  "occurred_at": "2026-09-10T20:30:00Z"
}
```

Todo evento carrega:
- `event_id` — identificador único, usado para **idempotência**.
- `event_type` — união discriminada, usada para rotear e desserializar corretamente.
- `trace_id` — identificador de correlação, usado para **distributed tracing**.

---

## Conceitos Fundamentais

Os padrões a seguir são cidadãos de primeira classe deste código. Cada um possui um teste dedicado que comprova o comportamento, não apenas um comentário no código.

### 1. Microsserviços (bounded contexts)

Cada serviço é dono do seu domínio, do seu schema e do seu ciclo de vida de implantação. As fronteiras entre serviços são cruzadas exclusivamente por meio de eventos ou contratos HTTP.

### 2. Arquitetura Orientada a Eventos

Os serviços reagem a **fatos que já aconteceram** (`OrderCreated`, `PaymentApproved`). Isso desacopla produtores de consumidores e permite escalabilidade e evolução independentes.

### 3. Idempotência

O RabbitMQ garante entrega **at-least-once** (pelo menos uma vez). Um consumidor pode receber o mesmo evento várias vezes (por exemplo, falha de rede antes do `ACK`). Consumidores idempotentes evitam cobrança dupla:

```sql
CREATE TABLE processed_events (
    event_id UUID PRIMARY KEY,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

O `processing + insert into processed_events` acontece de forma **atômica** (na mesma transação). Uma entrega duplicada é um no-op.

### 4. Retry com Backoff Exponencial

Falhas transitórias merecem uma segunda chance; erros de negócio, não.

```
5xx / timeout  ──► RETRY   (2s, 4s, 8s, 16s...)
4xx / regra de negócio ──► FAIL FAST (sem retry)
```

### 5. Dead Letter Queue (DLQ)

Depois de esgotar as tentativas, a mensagem é movida para uma DLQ em vez de ficar em loop para sempre. As mensagens permanecem **auditáveis** e **reprocessáveis** por meio de endpoints administrativos:

- `GET /admin/dead-letters`
- `POST /admin/dead-letters/{id}/reprocess`

### 6. Circuit Breaker

Previne falhas em cascata quando um provedor externo está fora do ar:

```
CLOSED ──(N falhas)──► OPEN ──(timeout)──► HALF-OPEN ──(probe)──► CLOSED
```

Em `OPEN`, as chamadas **falham rápido** sem tocar no provedor, preservando recursos e reduzindo a latência.

### 7. Distributed Tracing

O `trace_id` é propagado entre as fronteiras de HTTP, RabbitMQ e banco de dados via OpenTelemetry, permitindo análise de latência de ponta a ponta:

```
OrderCreated (120ms)
 └─ Payment Service (70ms)
     └─ External Provider (65ms)
 └─ Inventory Service (40ms)
```

### 8. Cache Redis

As leituras de estoque são armazenadas em cache com TTL e **invalidação orientada a eventos**:

```
GET stock:10 ─► Redis HIT/MISS ─► PostgreSQL ─► SET stock:10 (TTL 60s)
InventoryReserved ─► DELETE stock:10
```

O cache é tratado como um problema de consistência, não como um ganho gratuito de velocidade.

### 9. Transactional Outbox

O padrão outbox garante que **nenhum evento seja perdido** entre uma escrita no banco e a publicação de uma mensagem. O pedido e seu evento de outbox são gravados na **mesma transação**; um worker em segundo plano os publica depois.

```
BEGIN
  INSERT INTO orders
  INSERT INTO outbox_events
COMMIT
```

### 10. Consistência Eventual

Os serviços convergem de forma assíncrona. É aceitável (e esperado) que o pedido esteja `PENDING`, o pagamento `APPROVED` e o estoque `RESERVED` no mesmo instante — eles convergirão para `CONFIRMED` conforme os eventos forem consumidos.

### 11. Desenvolvimento Test-First

Toda a plataforma é construída usando **TDD** — a especificação comportamental é escrita antes da implementação. A pirâmide de testes impõe testes unitários rápidos e isolados e um conjunto menor de testes de integração/E2E contra infraestrutura real.

---

## Stack Tecnológica

| Categoria | Tecnologia | Versão |
|-----------|------------|--------|
| Linguagem | Python | 3.12+ |
| Ambiente e dependências | uv | — |
| Framework web | FastAPI | 0.115+ |
| Validação de dados | Pydantic | 2.x |
| ORM | SQLAlchemy (async) | 2.x |
| Migrações | Alembic | 1.x |
| Mensageria | RabbitMQ + aio-pika | 3.x / 9.x |
| Banco relacional | PostgreSQL | 16 |
| Cache | Redis | 7 |
| Agendamento | APScheduler | 3.x |
| Tracing | OpenTelemetry + Jaeger/Tempo | — |
| Métricas | Prometheus + Grafana | — |
| Contêineres | Docker / Docker Compose | — |
| Orquestração | Kubernetes | — |
| Testes | Pytest + testcontainers | — |
| Lint/Format | Ruff | — |
| Verificação de tipos | mypy (`--strict`) | — |

---

## Estrutura do Repositório

```
async-order-platform/
├── services/
│   ├── order-service/
│   │   ├── app/
│   │   │   ├── api/                  # Rotas HTTP, DI, schemas de requisição
│   │   │   ├── domain/               # entidades, value objects, eventos, máquina de estados
│   │   │   ├── application/          # casos de uso e portas (protocols)
│   │   │   ├── infrastructure/       # repositórios SQLAlchemy, publishers, worker de outbox
│   │   │   └── consumers/            # consumidores RabbitMQ
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   ├── integration/
│   │   │   └── e2e/
│   │   ├── alembic/
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── payment-service/
│   ├── inventory-service/
│   └── notification-service/
├── shared/                            # contratos de eventos compartilhados (tipados)
├── infrastructure/
│   ├── rabbitmq/
│   ├── postgres/
│   ├── redis/
│   └── observability/
├── docker-compose.yml
├── Makefile
└── README.md
```

### Arquitetura em camadas (hexagonal)

As dependências apontam **para dentro**; o domínio nunca depende da infraestrutura.

```
api ──────► application ◄────── consumers
              │
              ▼
           domain
              ▲
              │
        infrastructure
```

- `domain` — lógica de negócio pura, sem imports de framework.
- `application` — casos de uso e portas (interfaces `Protocol`).
- `infrastructure` — adaptadores que implementam as portas (banco, publisher, cache).
- `api` / `consumers` — pontos de entrada que conectam tudo.

---

## Começando

### Pré-requisitos

- Docker & Docker Compose
- [uv](https://docs.astral.sh/uv/) — gerencia o Python 3.12+ e as dependências do projeto

### 1. Inicialize a infraestrutura

```bash
docker compose up -d postgres rabbitmq redis
```

### 2. Instale as dependências

```bash
cd services/order-service
uv sync --all-extras
```

O `uv sync` resolve o Python 3.12+, cria o ambiente virtual (`services/order-service/.venv`) e instala as dependências a partir do `pyproject.toml`, travando as versões no `uv.lock`. O flag `--all-extras` instala também as dependências de desenvolvimento.

### 3. Execute as migrações

```bash
uv run alembic upgrade head
```

### 4. Execute o serviço

```bash
uv run uvicorn app.main:app --reload
```

### 5. Crie um pedido

```bash
curl -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": 123,
    "items": [
      {"product_id": 10, "quantity": 2},
      {"product_id": 20, "quantity": 1}
    ]
  }'
```

---

## Fluxo de Desenvolvimento

O projeto segue um fluxo de trabalho **test-first** estrito:

```bash
# 1. RED — escreva um teste que falha
uv run pytest tests/unit/test_order.py::test_order_total

# 2. GREEN — implemente o mínimo para passar
uv run pytest tests/unit/test_order.py::test_order_total

# 3. REFACTOR — limpe sem quebrar o comportamento
uv run pytest tests/unit/
```

### Comandos de qualidade

```bash
uv run ruff check .    # lint
uv run ruff format .   # formatação
uv run mypy .          # verificação de tipos
uv run pytest          # testes
uv run pytest --cov    # cobertura
```

> O target `make check` orquestra a barreira completa (Ruff + mypy + Pytest), executando as mesmas ferramentas acima via `uv run`.

---

## Estratégia de Testes

A pirâmide de testes mantém o ciclo de feedback rápido, ao mesmo tempo em que verifica a integração real.

```
        /        E2E (lento, poucos)       \
       /      Integração (médio)            \
      /     Contrato (médio)                 \
     /   Unitário (rápido, muitos)            \
    /_________________________________________\
```

| Camada | Diretório | Escopo | Infraestrutura |
|--------|-----------|--------|----------------|
| Unitário | `tests/unit/` | Regras de domínio, casos de uso, validadores, máquina de estados | Nenhuma (mock em tudo) |
| Contrato | `tests/contract/` | Schemas de eventos (pydantic) | Nenhuma |
| Integração | `tests/integration/` | API → DB → RabbitMQ → Consumer → DB | Docker (Postgres, RabbitMQ, Redis reais) |
| E2E | `tests/e2e/` | `POST /orders` → `CONFIRMED` | Docker (todos os serviços) |

### Regras de teste

- **TDD é obrigatório** — nenhum código de produção sem um teste que falhe primeiro.
- Testes unitários devem rodar em **segundos**, sem rede, banco de dados ou tempo real.
- O tempo é injetado/mockado — **sem `time.sleep` nos testes**.
- Um assert por comportamento; nomes descritivos `test_<comportamento>_<cenário>`.
- Mínimo de **80% de cobertura** nas camadas de domínio/aplicação (aplicado no CI).

---

## Barreiras de Qualidade

Todo merge deve passar por:

| Barreira | Ferramenta | Impõe |
|----------|------------|-------|
| Lint | `ruff check .` | Estilo, imports não usados, correção assíncrona, type hints obrigatórios (`ANN`) |
| Formatação | `ruff format --check .` | Formatação consistente |
| Verificação de tipos | `mypy --strict .` | Código 100% tipado, sem `Any` implícito |
| Testes unitários | `pytest tests/unit` | Correção de domínio e aplicação |
| Testes de integração | `pytest tests/integration` | Comportamento com infraestrutura real |
| Cobertura | `pytest --cov` | ≥ 80% em domínio/aplicação |

**Política de tipagem** é inegociável:

- Type hints completos em todo o código de produção (`mypy --strict`).
- `Any` é proibido sem justificativa explícita.
- `NewType` para IDs primitivos para evitar mistura acidental de parâmetros.
- Preferir modelos pydantic frozen/imutáveis e `tuple` em vez de `list`.

---

## Observabilidade

A plataforma emite três sinais correlacionados, cada um carregando `trace_id` e `event_id`:

| Sinal | Ferramenta | Propósito |
|-------|------------|-----------|
| Traces | OpenTelemetry + Jaeger/Tempo | Latência de ponta a ponta por serviço |
| Métricas | Prometheus | Métricas de negócio + infra (`orders_created_total`, `dlq_messages_total`) |
| Logs | JSON estruturado | Depuração, interpretados por Loki/ELK |

---

## Roadmap

Consulte [`como-desenvolver-com-tdd-e-tasks.md`](como-desenvolver-com-tdd-e-tasks.md) para a divisão completa de tarefas.

| Milestone | Escopo |
|-----------|--------|
| M0 | Setup: monorepo, docker-compose, ferramentas, CI |
| M1 | Domínio do Order Service (TDD, testes unitários) |
| M2 | Aplicação do Order Service + outbox |
| M3 | API do Order Service + persistência real |
| M4 | Payment Service (idempotência, retry, circuit breaker, DLQ) |
| M5 | Inventory Service (reserva, cache, invalidação) |
| M6 | Notification Service |
| M7 | Orquestração + observabilidade |
| M8 | E2E + CI/CD + Kubernetes |

---

## Documentação

| Documento | Propósito |
|-----------|-----------|
| [`architecture.md`](arquitetura-do-sistema.md) | Arquitetura técnica completa: stack, tipagem, lint, regras de teste |


## Licença

[MIT](LICENSE), salvo indicação em contrário.