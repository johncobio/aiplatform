from fastapi.testclient import TestClient

from llm_service.app import create_app
from llm_service.settings import Settings


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_readyz_after_load(client):
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"
    assert r.json()["model"] == "mock-model"


def test_models_endpoint(client):
    data = client.get("/v1/models").json()
    assert data["data"][0]["id"] == "mock-model"


def test_chat_completion_openai_shape(client):
    r = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hello there world"}], "max_tokens": 10},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"] == {
        "role": "assistant",
        "content": "echo: hello there world",
    }
    assert body["usage"]["completion_tokens"] == 4
    assert body["usage"]["total_tokens"] == 7
    assert r.headers["x-request-id"]


def test_chat_rejects_empty_messages(client):
    r = client.post("/v1/chat/completions", json={"messages": []})
    assert r.status_code == 422


def test_chat_rejects_excessive_max_tokens(client):
    r = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}], "max_tokens": 999},
    )
    assert r.status_code == 400


def test_streaming_not_supported(client):
    r = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}], "stream": True},
    )
    assert r.status_code == 400


def test_metrics_exposed(client):
    client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "a b c"}]})
    text = client.get("/metrics").text
    assert 'llm_requests_total{status="ok"}' in text
    assert "llm_request_duration_seconds_bucket" in text
    assert "llm_model_ready 1.0" in text
    assert "llm_completion_tokens_total" in text
    assert "llm_queue_depth 0.0" in text


def test_readyz_503_while_loading_and_on_failure():
    class SlowFailingBackend:
        model_name = "broken"

        def load(self):
            raise RuntimeError("no weights")

        def generate(self, *a, **k):
            raise AssertionError("should not be called")

    app = create_app(Settings(backend="mock", log_format="text"), backend=SlowFailingBackend())
    with TestClient(app) as c:
        app.state.engine.wait_until_settled(timeout=5)
        r = c.get("/readyz")
        assert r.status_code == 503
        assert r.json()["status"] == "failed"
        assert "no weights" in r.json()["error"]
        r = c.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}]})
        assert r.status_code == 503


def test_settings_expose_mlock_and_warmup(monkeypatch):
    monkeypatch.setenv("LLM_MLOCK", "true")
    monkeypatch.setenv("LLM_WARMUP", "false")
    s = Settings()
    assert s.mlock is True and s.warmup is False
