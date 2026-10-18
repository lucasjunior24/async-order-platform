# Documentação da API — Async Order Platform

> Referência das rotas HTTP e dos contratos da **Async Order Platform** — uma
> plataforma de processamento de pedidos orientada a eventos, construída com
> arquitetura de microsserviços (FastAPI + PostgreSQL + RabbitMQ + Redis).

## Índice

- [Visão geral](#visão-geral)
- [Serviços e portas](#serviços-e-portas)
- [Convenções gerais](#convenções-gerais)
- [Order Service — porta 8000](#order-service--porta-8000)
- [Payment Service — porta 8001](#payment-service--porta-8001)
- [Inventory Service — porta 8002](#inventory-service--porta-8002)
- [Notification Service — porta 8003](#notification-service--porta-8003)
- [Modelos de dados](#modelos-de-dados)
- [Eventos de domínio (contrato)](#eventos-de-domínio-contrato)
- [Fluxo assíncrono e máquina de estados](#fluxo-assíncrono-e-máquina-de-estados)
- [Exemplos com `curl`](#exemplos-com-curl)
- [Erros e códigos de status](#erros-e-códigos-de-status)

---

## Visão geral

A plataforma é decomposta por **domínio de negócio** (bounded contexts), não por
camadas técnicas. Cada serviço é dono dos seus dados e se comunica por meio de
**eventos de domínio** assíncronos — HTTP síncrono é usado apenas onde é
estritamente necessário (entrada de pedidos, administração e saúde).

A única rota de negócio exposta hoje é o **`POST /orders`** do Order Service.
A partir dela, todo o restante do fluxo (pagamento, estoque e notificação) é
orquestrado por eventos publicados via **transactional outbox**.

Todos os serviços são **FastAPI** e, portanto, também expõem automaticamente a
interface interativa **Swagger UI** (`/docs`), o **ReDoc** (`/redoc`) e o schema
**OpenAPI** (`/openapi.json`).

---

## Serviços e portas

| Serviço | Porta HTTP | Responsabilidade | Rotas de negócio |
|---------|-----------:|------------------|------------------|
| `order-service` | **8000** | Criação e orquestração de pedidos | `POST /orders`, admin DLQ, metrics |
| `payment-service` | **8001** | Processamento de pagamentos (resiliência) | — (somente `/health`) |
| `inventory-service` | **8002** | Reserva de estoque (com cache) | — (somente `/health`) |
| `notification-service` | **8003** | Notificações ao cliente | — (somente `/health`) |

### Infraestrutura (portas expostas via `docker-compose`)

| Componente | Porta | Observação |
|------------|------:|------------|
| PostgreSQL — orders | 5432 | `orders_db` |
| PostgreSQL — payments | 5433 | `payments_db` |
| PostgreSQL — inventory | 5434 | `inventory_db` |
| RabbitMQ (AMQP) | 5672 | broker de eventos |
| RabbitMQ Management | 15672 | painel web (`guest`/`guest`) |
| Redis | 6379 | cache de estoque |
| Prometheus | 9090 | métricas |
| Grafana | 3000 | dashboards (`admin`/`admin`) |

---

## Convenções gerais

- **Formato:** JSON (`application/json`) em requisições e respostas, exceto
  `/metrics`, que responde no formato texto do Prometheus.
- **Identificadores:** `order_id`, `event_id`, `payment_id` e `message_id` são
  UUIDs (`uuid4`) serializados como string.
- **Valores monetários:** são strings decimais (ex.: `"19.90"`), evitando erros
  de ponto flutuante.
- **Saúde:** todos os serviços expõem `GET /health` → `200 {"status": "ok"}`,
  usado pelas probes do Kubernetes e pelos healthchecks do Docker Compose.
- **Documentação interativa:** cada serviço expõe `/docs`, `/redoc` e
  `/openapi.json` (padrão do FastAPI).

---

## Order Service — porta 8000

Serviço de entrada da plataforma. Expõe a criação de pedidos, a administração
da dead letter queue e as métricas do Prometheus.

### `GET /health`

Verifica a saúde do serviço.

**Resposta — `200 OK`**

```json
{ "status": "ok" }
```

---

### `POST /orders`

Cria um pedido e grava atomicamente o evento `OrderCreated` no transactional
outbox (pedido + evento na mesma transação). O processamento real (pagamento,
estoque, notificação) acontece de forma **assíncrona** pelos serviços
downstream.

**Corpo da requisição (`application/json`)**

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|:-----------:|-----------|
| `customer_id` | `integer` | Sim | Identificador do cliente |
| `items` | `array<object>` | Sim | Itens do pedido (deve conter ao menos 1 item) |

**Objeto `items[]`**

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|:-----------:|-----------|
| `product_id` | `integer` | Sim | Identificador do produto |
| `quantity` | `integer` | Sim | Quantidade (deve ser `> 0`) |
| `unit_price` | `string` | Não | Preço unitário decimal (padrão `"0.00"`) |

**Exemplo de requisição**

```json
{
  "customer_id": 123,
  "items": [
    { "product_id": 10, "quantity": 2, "unit_price": "19.90" },
    { "product_id": 20, "quantity": 1, "unit_price": "5.00" }
  ]
}
```

**Resposta — `201 Created`**

```json
{ "order_id": "550e8400-e29b-41d4-a716-446655440000" }
```

**Possíveis erros**

| Status | Situação |
|-------:|----------|
| `422 Unprocessable Entity` | Corpo inválido (ex.: `quantity <= 0`, tipo errado, campos ausentes) |

> ⚠️ O campo `quantity` é validado como `> 0`; `unit_price` é opcional e, se
> ausente, assume `"0.00"`.

---

### `GET /admin/dead-letters`

Lista as mensagens atualmente retidas na **dead letter queue** (mensagens que
falharam após todos os retries).

**Resposta — `200 OK`**

Retorna um array de eventos de domínio serializados. Cada item segue o contrato
dos [eventos de domínio](#eventos-de-domínio-contrato), por exemplo:

```json
[
  {
    "event_id": "6f9619ff-8b86-4f57-8f5b-1d5c7e8a9b0c",
    "event_type": "PaymentFailed",
    "order_id": "550e8400-e29b-41d4-a716-446655440000",
    "trace_id": "abc-123",
    "occurred_at": "2026-10-17T12:00:00Z",
    "reason": "provider_unavailable"
  }
]
```

---

### `POST /admin/dead-letters/{message_id}/reprocess`

Republica uma mensagem da DLQ no broker e a remove da fila morta. O
`message_id` no caminho é o **`event_id`** da mensagem (UUID).

**Parâmetros de caminho**

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `message_id` | `uuid` | `event_id` da mensagem a reprocessar |

**Resposta — `200 OK`**

```json
{ "event_id": "6f9619ff-8b86-4f57-8f5b-1d5c7e8a9b0c" }
```

**Possíveis erros**

| Status | Situação |
|-------:|----------|
| `404 Not Found` | Mensagem não encontrada na DLQ |
| `422 Unprocessable Entity` | `message_id` não é um UUID válido |

---

### `GET /metrics`

Expõe as métricas do serviço no formato texto do Prometheus (contadores e
histogramas, ex.: `orders_created_total`, `dlq_messages_total`).

**Resposta — `200 OK`** — `Content-Type: text/plain; version=0.0.4; charset=utf-8`

---

## Payment Service — porta 8001

Serviço reativo que processa pagamentos com **idempotência**, **retry com
backoff exponencial** e **circuit breaker**. Nesta versão não expõe rotas de
negócio; apenas o endpoint de saúde.

### `GET /health`

**Resposta — `200 OK`**

```json
{ "status": "ok" }
```

---

## Inventory Service — porta 8002

Serviço reativo que reserva estoque, usando **cache Redis** com invalidação
orientada a eventos. Nesta versão não expõe rotas de negócio; apenas o endpoint
de saúde.

### `GET /health`

**Resposta — `200 OK`**

```json
{ "status": "ok" }
```

---

## Notification Service — porta 8003

Serviço puramente reativo que consome os fatos do fluxo de pedido e envia
notificações ao cliente. Nesta versão não expõe rotas de negócio; apenas o
endpoint de saúde.

### `GET /health`

**Resposta — `200 OK`**

```json
{ "status": "ok" }
```

---

## Modelos de dados

### `OrderItemPayload` (entrada do `POST /orders`)

| Campo | Tipo | Regras |
|-------|------|--------|
| `product_id` | `integer` | obrigatório |
| `quantity` | `integer` | obrigatório, `> 0` |
| `unit_price` | `string` | opcional, padrão `"0.00"` (decimal) |

### `CreateOrderPayload` (corpo do `POST /orders`)

| Campo | Tipo | Regras |
|-------|------|--------|
| `customer_id` | `integer` | obrigatório |
| `items` | `array<OrderItemPayload>` | obrigatório, não vazio |

### `OrderStatus` (enum de estado do pedido)

| Valor | Significado |
|-------|-------------|
| `PENDING` | Pedido criado, aguardando processamento |
| `PAYMENT_APPROVED` | Pagamento aprovado (aguardando estoque) |
| `INVENTORY_RESERVED` | Estoque reservado (aguardando pagamento) |
| `CONFIRMED` | Pagamento **e** estoque concluídos |
| `PAYMENT_FAILED` | Pagamento rejeitado (estado terminal de falha) |
| `OUT_OF_STOCK` | Sem estoque suficiente (estado terminal de falha) |

---

## Eventos de domínio (contrato)

Todo evento carrega os campos de correlação `event_id` (idempotência),
`event_type` (roteamento), `order_id` (correlação), `trace_id` (distributed
tracing) e `occurred_at` (timestamp UTC).

| Evento | `event_type` | Campos adicionais | Publicado por → Consumido por |
|--------|--------------|-------------------|-------------------------------|
| `OrderCreated` | `OrderCreated` | `customer_id: int` | Order → Payment, Inventory, Notification |
| `PaymentApproved` | `PaymentApproved` | `payment_id: uuid` | Payment → Order, Notification |
| `PaymentFailed` | `PaymentFailed` | `reason: string` | Payment → Order, Notification |
| `InventoryReserved` | `InventoryReserved` | — | Inventory → Order, Notification |
| `OutOfStock` | `OutOfStock` | — | Inventory → Order, Notification |

> O `Notification Service` adiciona o campo `recipient_email: string` ao
> contrato dos eventos que consome, pois precisa do destino da notificação.

---

## Fluxo assíncrono e máquina de estados

```
 POST /orders
      │
      ▼
 Order Service ──(OrderCreated)──► Outbox ──► RabbitMQ
                                              │
                    ┌─────────────────────────┴──────────────────────┐
                    ▼                                                ▼
            Payment Service                                  Inventory Service
                    │                                                │
   (PaymentApproved │ PaymentFailed)                (InventoryReserved │ OutOfStock)
                    └───────────────┬────────────────────────────────┘
                                    ▼
                          Notification Service
                                    │
                                    ▼
                     Order Service (consumer de resultados)
                                    │
                                    ▼
                              CONFIRMED
```

### Transições de estado do pedido

| Evento aplicado | Estado atual | Novo estado |
|-----------------|--------------|-------------|
| `PaymentApproved` | `PENDING` | `PAYMENT_APPROVED` |
| `PaymentApproved` | `INVENTORY_RESERVED` | `CONFIRMED` |
| `InventoryReserved` | `PENDING` | `INVENTORY_RESERVED` |
| `InventoryReserved` | `PAYMENT_APPROVED` | `CONFIRMED` |
| `PaymentFailed` | `PENDING` | `PAYMENT_FAILED` |
| `OutOfStock` | `PENDING` | `OUT_OF_STOCK` |

A convergência para `CONFIRMED` ocorre quando **pagamento e estoque** terminam
com sucesso, em qualquer ordem — é o padrão de **consistência eventual** entre
os bounded contexts.

---

## Exemplos com `curl`

> Substitua `localhost:8000` pela porta do serviço, se necessário.

### Criar um pedido

```bash
curl -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": 123,
    "items": [
      { "product_id": 10, "quantity": 2, "unit_price": "19.90" }
    ]
  }'
```

Resposta esperada:

```json
{ "order_id": "550e8400-e29b-41d4-a716-446655440000" }
```

### Verificar a saúde de um serviço

```bash
curl http://localhost:8000/health
# { "status": "ok" }

curl http://localhost:8001/health   # payment-service
curl http://localhost:8002/health   # inventory-service
curl http://localhost:8003/health   # notification-service
```

### Listar mensagens da dead letter queue

```bash
curl http://localhost:8000/admin/dead-letters
```

### Reprocessar uma mensagem da DLQ

```bash
curl -X POST \
  http://localhost:8000/admin/dead-letters/6f9619ff-8b86-4f57-8f5b-1d5c7e8a9b0c/reprocess
```

### Coletar métricas (Prometheus)

```bash
curl http://localhost:8000/metrics
```

---

## Erros e códigos de status

| Código | Significado | Onde ocorre |
|-------:|-------------|-------------|
| `200 OK` | Sucesso | `/health`, `GET /admin/dead-letters`, `POST .../reprocess`, `GET /metrics` |
| `201 Created` | Recurso criado | `POST /orders` |
| `404 Not Found` | Mensagem não encontrada | `POST /admin/dead-letters/{message_id}/reprocess` |
| `422 Unprocessable Entity` | Validação do corpo/caminho falhou | `POST /orders`, DLQ (UUID inválido) |

> A validação de entrada é feita pelo **Pydantic** no próprio FastAPI: erros de
> schema retornam `422` com o detalhe dos campos inválidos no corpo da resposta.

