# V5 load testing and autoscaling — 2026-09-16

**Setup:** kind on Docker Desktop, VM at **4 vCPU / 4 GB** (reduced from 6 vCPU
to stop starving the host). Staging `llm-service` (Qwen2.5-0.5B Q4_K_M,
llama.cpp, 2 threads, `cpu: 2`, `memory: 1Gi`, `LLM_MLOCK=true`, warm-up on),
HPA on `llm_pending_requests` target 2, min 1, max 2. Running beside:
Prometheus, operator, kube-state-metrics, prometheus-adapter, ingress-nginx,
metrics-server. Argo CD, Grafana, Jaeger and the collector paused. Load from
k6 on the host through ingress-nginx; `max_tokens: 32`, temperature 0.2.

Commands: `make loadtest SCENARIO=... VUS=... DURATION=2m`;
server-side numbers from `python loadtest/report.py <summary> --prom ... --start --end`.

## Results

| Scenario | VUs | Replicas | Throughput | Median | P95 | P99 | Tokens/s (all) | Per-request tok/s (median) | Max queue depth | Max pod CPU |
|----------|-----|----------|------------|--------|-----|-----|----------------|----------------------------|-----------------|-------------|
| smoke | 1 | 1 | 0.508 req/s | 1.88 s | 2.33 s | 2.72 s | 16.3 | 17.0 | 0 | 0.91 |
| steady1 | 1 | 1 | 0.524 req/s | 1.91 s | 2.17 s | 2.26 s | 16.4 | 16.6 | 0 | 1.97 |
| steady2 | 2 | 1 | 0.557 req/s | 3.57 s | 3.94 s | 4.39 s | 17.6 | 8.8 | 1 | 1.96 |
| step | 1→2→4 | 1→2 | 0.476 req/s | 2.18 s | 7.16 s | 8.52 s | 15.0 | 14.6 | 2 | 2.02 |
| steady4x2 | 4 | 2 | 0.588 req/s | 6.35 s | 10.14 s | 12.85 s | 18.7 | 5.0 | 3 | 3.30 |

Failure rate was 0.00 % in every run (n = 16, 63, 68, 131, 74 requests).

## Autoscaling timeline (step scenario, 90 s per stage)

| Time (UTC) | Event |
|------------|-------|
| 22:42:32 | 1 VU stage starts; pending = 0, replicas = 1 |
| 22:44:02 | 2 VU stage; pending ≈ 2 → ratio 1.0, no scale (correct) |
| 22:45:32 | 4 VU stage begins |
| 22:46:32 | HPA event `SuccessfulRescale New size: 2; reason: pods metric llm_pending_requests above target` (pending = 3) |
| 22:46:52 | second replica Ready (cached model in PVC + warm-up) |

**Load step → scale decision: 60 s. Load step → second replica serving: 80 s.**
No scale-down flapping during the runs (120 s stabilization).

## Observations

- **The signal is right.** Queue depth tracked demand exactly: 0 at 1 VU, 1 at
  2 VUs, 2–3 at 4 VUs, and the HPA scaled on it without reacting to the
  model-load CPU spike that fooled the V2 CPU-based HPA.
- **Horizontal scaling on one node bought almost nothing.** Two replicas on a
  4-vCPU node produced 18.7 tok/s versus 16.4 with one (+14 %) while total CPU
  rose from 2.0 to 3.3 cores: the replicas contend for the same cores, and
  per-request speed halved (16.6 → 5.0 tok/s). Autoscaling is a mechanism;
  capacity comes from nodes. On EKS this is the cluster autoscaler /
  Karpenter's job, and the reason the V6 vLLM path needs GPU nodes.
- **Single-replica ceiling:** ~0.52 req/s and ~16.5 tok/s at 32 tokens per
  request on 2 CPU threads; latency doubles as soon as a second client queues.
- **Warm-up removed the cold first request.** New replica ready in 2.9 s
  (model cached, `warm-up generation done in 1.99s`); the smoke run's first
  request was 2.8 s max, versus 19–52 s cold starts seen in V4.
- **The laptop is the limit, not the platform.** Two host-swap stalls and one
  kind restart storm happened during this phase; the mitigations
  (4 vCPU VM, fine-grained `cluster addon pause`) are in place and recorded.
