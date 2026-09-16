# llm-service

Sample `aiplatform` workload: an OpenAI-compatible inference API that serves a
small open model itself (llama.cpp on CPU) and exposes Prometheus metrics.

| Endpoint | Purpose |
|----------|---------|
| `POST /v1/chat/completions` | OpenAI-compatible chat (non-streaming) |
| `GET /v1/models` | model card |
| `GET /healthz` | process liveness |
| `GET /readyz` | 200 once the model is loaded, 503 while loading / on failure |
| `GET /metrics` | Prometheus exposition |

Configuration is via `LLM_*` environment variables (see `settings.py`).
`LLM_BACKEND=mock` runs without weights (tests, CI).

```
uv sync --extra dev
uv run pytest
LLM_BACKEND=mock LLM_LOG_FORMAT=text uv run python -m llm_service
```
