"""Configuração de tracing distribuído com OpenTelemetry (T7.2).

Fornece um tracer global e helpers para obter/propagar `trace_id` entre os
serviços via contexto. A propagação acontece de duas formas:

- HTTP: via cabeçalhos W3C Trace Context (`traceparent`).
- Eventos: via campo ``trace_id`` em cada evento de domínio.

O módulo é tolerante a não-inicialização: se o SDK não foi configurado (ex.:
testes unitários), ``get_trace_id`` gera um identificador novo.
"""

from contextvars import ContextVar
from uuid import uuid4

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

_tracer_provider: TracerProvider | None = None

# ContextVar para permitir injetar/sobrescrever o trace_id atual em testes.
_trace_id_override: ContextVar[str | None] = ContextVar(
    "trace_id_override",
    default=None,
)


def get_tracer(name: str) -> trace.Tracer:
    """Retorna o tracer global do OpenTelemetry para o serviço `name`."""
    return trace.get_tracer(name)


def configure_tracing(service_name: str) -> TracerProvider:
    """Configura o SDK do OpenTelemetry e o registra como provider global.

    Por padrão exporta spans para o console (útil em desenvolvimento). Em
    produção, o exportador OTLP deve ser configurado via variáveis de ambiente,
    conforme documentado no OpenTelemetry.
    """
    global _tracer_provider
    if _tracer_provider is not None:
        return _tracer_provider

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)

    _tracer_provider = provider
    return provider


def get_trace_id() -> str:
    """Retorna o `trace_id` atual ou gera um novo (fallback).

    Ordem de resolução:

    1. valor injetado via ``set_trace_id`` (testes);
    2. span ativo do OpenTelemetry (propagação de contexto);
    3. novo UUID (início de um trace, como em um request HTTP sem contexto).
    """
    override = _trace_id_override.get()
    if override is not None:
        return override

    span = trace.get_current_span()
    if span is not None and span.is_recording():
        span_context = span.get_span_context()
        if span_context.is_valid:
            return _format_trace_id(span_context.trace_id)

    return str(uuid4())


def set_trace_id(trace_id: str | None) -> None:
    """Sobrescreve o trace_id resolvido por ``get_trace_id`` (útil em testes)."""
    _trace_id_override.set(trace_id)


def _format_trace_id(trace_id: int) -> str:
    """Formata o trace_id (128-bit) como string hex de 32 caracteres."""
    return f"{trace_id:032x}"
