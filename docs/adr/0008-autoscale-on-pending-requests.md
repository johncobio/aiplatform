# 0008 — Autoscale inference pods on pending requests, not CPU

2026-09-16 · Accepted

## Context

V2 showed the CPU-based HPA scaling up during model load (a startup burst,
not demand) and V4 gave us per-pod inference metrics. An LLM pod that
serialises generation (llama.cpp, and vLLM at its concurrency limit) is
"full" when requests wait, regardless of what CPU utilisation says.

## Decision

- **Signal:** `llm_pending_requests` = `llm_queue_depth + llm_inflight_requests`
  per pod, exposed through the Kubernetes custom metrics API by
  prometheus-adapter (rule in `deploy/kind/prometheus-adapter.values.yaml`).
- **Policy:** HPA v2 `type: Pods`, `AverageValue` target (default 2). Scale
  up at most one pod per 30 s with no stabilization; scale down one pod per
  60 s after a 120 s stabilization window because each new pod costs a model
  load (~15 s) and flapping would be worse than a short over-provision.
- **Configuration:** `aiplatform.yaml` `autoscaling.metric: queue|cpu` and
  `autoscaling.target`. `cpu` stays available for workloads without the
  adapter (the `kind` target without observability) and as a comparison.
- **Load testing:** k6 scenarios in `loadtest/k6/chat.js` (smoke, steady,
  ramp, step) with per-request token throughput as a custom metric;
  `loadtest/report.py` joins the k6 summary with server-side Prometheus
  maxima (queue depth, replicas, P95, CPU) for the benchmark record.
- **Cold model:** `LLM_MLOCK=true` in Kubernetes (memory request already
  budgets the weights) and a warm-up generation after load, so the first
  request of a new replica is not the slowest.

## Consequences

- Scaling decisions follow demand with a clear meaning ("two requests per pod
  are waiting or running") that a developer can reason about, and the same
  signal will work for vLLM in V6 (its `vllm:num_requests_waiting` maps to
  the same rule).
- The HPA depends on prometheus-adapter → Prometheus → ServiceMonitor. If any
  link is down the HPA reports `<unknown>` and holds the current replica
  count; on a real cluster this chain must be monitored (V8).
- On this laptop `max: 2` is the ceiling: one extra 1 GiB replica is all the
  node can take beside the observability stack.
