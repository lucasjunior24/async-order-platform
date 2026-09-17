"""Testes unitários da propagação de trace_id (T7.2)."""

from app.infrastructure.tracing import get_trace_id, set_trace_id


def test_get_trace_id_generates_value_when_not_set() -> None:
    set_trace_id(None)
    trace_id = get_trace_id()

    assert trace_id
    assert trace_id != ""


def test_get_trace_id_uses_explicit_override() -> None:
    set_trace_id("abc-123")

    assert get_trace_id() == "abc-123"

    set_trace_id(None)
