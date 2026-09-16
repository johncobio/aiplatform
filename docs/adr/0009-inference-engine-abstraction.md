# 0009 — Inference engines behind one contract: builtin, llama.cpp server, vLLM

2026-09-16 · Accepted

## Context

V6 asks for a real open-source inference server (vLLM) with inference-specific
metrics. The development laptop has no GPU and a 4 GB Docker VM, so vLLM
cannot run here; the AWS phase provides GPU nodes. Meanwhile the platform
should not be tied to the sample service it happens to ship.

## Decision

`aiplatform.yaml` gains `engine: builtin | llamacpp-server | vllm`
(default: `vllm` for GPU catalog models, else `builtin`). The Helm chart
renders one Deployment shape with engine-specific container, args, probes
and resources:

| Engine | Image | Model source | Probes | Native metrics |
|--------|-------|--------------|--------|----------------|
| builtin | `aiplatform/llm-service` built from the workload dir | GGUF URL, downloaded by the service | `/healthz`, `/readyz` | `llm_*` |
| llamacpp-server | `ghcr.io/ggml-org/llama.cpp:server-<pinned>` | GGUF URL, fetched by an init container into the shared cache | `/health` | `llamacpp:*` |
| vllm | `vllm/vllm-openai:<pinned>` | Hugging Face repo (optional `HF_TOKEN` secret) | `/health` | `vllm:*` |

- **The contract is the metrics vocabulary, not the engine.** A
  `PrometheusRule` normalises each engine's native series into
  `aiplatform:llm_pending_requests`, `aiplatform:llm_completion_tokens:rate5m`,
  `aiplatform:llm_prompt_tokens:rate5m`, `aiplatform:llm_requests:rate5m` and
  the latency quantiles. The HPA (via prometheus-adapter), the dashboard and
  future alerts read only those, so switching engines changes nothing
  downstream.
- **Platform-level HTTP metrics come from the ingress.** ingress-nginx's
  per-Ingress request counter and latency histogram are recorded as
  `aiplatform:http_*` and cover every engine, including llama.cpp server
  which exposes no request latency of its own.
- **Upstream engines skip the image pipeline.** For non-builtin engines the
  CLI omits build, load and registry checks; the chart pins the image.
- **vLLM is validated by rendering, not running.** `scripts/check_chart.sh`
  asserts the GPU resource requests, model args and token secret wiring for
  every engine in CI. Real vLLM runs wait for the AWS GPU node group.

## Consequences

- A team can bring a model with a one-file workload (`services/qwen-server`)
  and no code; the sample service remains the reference for instrumentation.
- Engine differences surface honestly: llama.cpp server has no latency
  histogram, so its P95 comes from the ingress; vLLM's `e2e_request_latency`
  is used when present.
- The `engine` label is stamped on pods, series and the Grafana "Engine"
  stat so comparisons (builtin vs llama.cpp server) are first-class.
