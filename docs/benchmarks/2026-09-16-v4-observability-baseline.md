# V4 observability baseline — 2026-09-16

**Setup:** kind on a 4 GB Docker VM (node allocatable 3.9 GiB), kube-prometheus-stack
91.4.1 (Prometheus, Grafana, kube-state-metrics; Alertmanager and node-exporter
off), OpenTelemetry Collector chart 0.173.1, Jaeger 2.21.0 all-in-one, staging
`llm-service` at 1Gi memory. Argo CD paused while the stack runs.

## Footprint (`kubectl top`, idle, after settling)

| Component | Memory |
|-----------|--------|
| Grafana (with dashboard + datasource sidecars) | 402 Mi |
| Prometheus (2 d retention, 12 targets, 15 s scrape) | 370 Mi |
| kube-state-metrics | 34 Mi |
| Jaeger | 34 Mi |
| OpenTelemetry Collector | 24 Mi |
| **Node used, before stack (Argo CD running)** | **1776 Mi (45 %)** |
| **Node used, with stack and Argo CD paused** | **2792 Mi (71 %)** |
| Node used with stack **and** Argo CD, before pausing | 3267 Mi + load avg 145, API server timing out |

## Verification

| Check | Result |
|-------|--------|
| ServiceMonitor scrape of staging workload | `up`, labels `environment=staging workload=llm-service model=qwen2.5-0.5b-instruct` |
| Active Prometheus targets | 12 / 12 up |
| Dashboard queries (`scripts/check_dashboard.py`) | 26 / 26 return series |
| Grafana sidecar loaded `LLM Inference` | uid `aiplatform-llm-inference` |
| Trace for one chat completion (Jaeger `/api/v3/traces/<id>`) | 7 spans: FastAPI request → `llm.queue_wait` (1.3 ms) → `llm.generate` (8122.7 ms of 8281.8 ms total) |
| `llm.generate` attributes | `gen_ai.request.model`, `gen_ai.usage.input_tokens=33`, `gen_ai.usage.output_tokens=8`, `gen_ai.response.finish_reasons=[length]` |
| Log ↔ trace correlation | access log `trace_id` equals the Jaeger trace id |
| GitOps deploy of the traced image (add-ons swapped around it) | 77.7 s |

## Observations

- **Instrumentation overhead is invisible at this scale.** Generation is 98 %
  of request time; the OTel spans and the FastAPI middleware account for
  well under a millisecond each.
- **First request after idle took 19–52 s** several times during this
  session, versus 2–4 s steady state. Under memory pressure the kernel evicts
  the mmap'd GGUF pages and llama.cpp re-reads the model from disk. This is
  a real production failure mode (cold model after a noisy neighbour) and
  an argument for `mlock`/preloading or memory headroom, to be revisited in
  V5/V8 with proper measurements.
- **The stack does not coexist with Argo CD on this laptop.** Installing it
  next to Argo CD and the workload exhausted the node and stalled the API
  server for ~10 minutes; `aiplatform cluster addon pause|resume` exists
  because of this. Grafana's sidecars are the surprise: 400 Mi for a UI.
