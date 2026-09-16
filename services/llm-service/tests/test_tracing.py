from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from llm_service.app import create_app
from llm_service.settings import Settings
from llm_service.tracing import configure_tracing


def test_chat_completion_produces_gen_ai_spans(monkeypatch):
    exporter = InMemorySpanExporter()
    configure_tracing(exporter=exporter, service_name="test-llm")
    app = create_app(Settings(backend="mock", log_format="text"), tracing=False)
    with TestClient(app) as c:
        app.state.engine.wait_until_settled(timeout=5)
        c.get("/healthz")
        r = c.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "trace me please"}], "max_tokens": 8},
        )
        assert r.status_code == 200

    spans = {s.name: s for s in exporter.get_finished_spans()}
    assert "llm.generate" in spans and "llm.queue_wait" in spans
    gen = spans["llm.generate"]
    assert gen.attributes["gen_ai.request.model"] == "mock-model"
    assert gen.attributes["gen_ai.usage.output_tokens"] == 4
    assert gen.attributes["gen_ai.usage.input_tokens"] == 3
    # FastAPI auto-instrumentation wraps the request; health endpoints are excluded.
    http_spans = [n for n in spans if n.startswith("POST")]
    assert http_spans, list(spans)
    assert not any("healthz" in n for n in spans)
    assert gen.parent is not None


def test_tracing_is_noop_without_endpoint(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert configure_tracing() is False
