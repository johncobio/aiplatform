# V8 reliability: SLOs, alerts and chaos — 2026-09-16

**Setup:** kind (4 vCPU / 4 GB VM), `qwen-server` in `dev` (upstream llama.cpp
engine, 1 replica, model cached in the PVC, warm-up on), Prometheus +
Alertmanager + prometheus-adapter running, Grafana/tracing/Argo CD paused.
`python chaos/experiment.py <experiment> --duration 150 --inject-at 30`
keeps a 1-VU k6 load on the ingress while one fault is injected with kubectl.
Raw rows: `chaos/results/*.md`.

## Chaos results

| Experiment | Fault | Recovery (measured) | Requests during run | Failed | Client P95 | 5m availability SLI min |
|------------|-------|---------------------|---------------------|--------|------------|--------------------------|
| pod-kill | `kubectl delete pod` of the only replica | new pod Ready **11.1 s**, endpoint serving **12.5 s** after deletion | 126 | 1 | 1.0 s | 99.18 % (the failure was counted) |
| adapter-outage | prometheus-adapter scaled to 0, restored after the HPA degraded | HPA `ScalingActive=false` after **5.3 s**; back to `true` **46.4 s** after restore | 188 | 0 | 1.05 s | 100 % (serving unaffected) |
| ingress-restart | `rollout restart` of the single ingress-nginx controller (Recreate) | down after 1.5 s, serving again **16.2 s** later | 18 544 | 18 377 (connection refused, retried instantly) | – | **100 % — blind spot**: no ingress, no 5xx counted |

## Alerts observed

| Alert | State during the session | Trigger |
|-------|--------------------------|---------|
| AiplatformHPAMetricUnavailable | firing (staging/llm-service) | deployment scaled to 0 replicas by hand: no pods → no metric; resolved after scaling back to 1 |
| KubePdbNotEnoughHealthyPods (kube-prometheus-stack default) | firing | same cause: PDB `minAvailable: 1` with 0 pods |
| PrometheusMissingRuleEvaluations | pending | laptop CPU pressure during load tests; rule groups took longer than their interval |
| Watchdog | firing | by design (dead-man switch) |
| ErrorBudgetBurnFast/Slow, LatencySLOViolation, WorkloadDown, QueueSaturated | inactive | none of the experiments burned enough budget for long enough (correct: a 12 s pod restart is inside the 99.5 % budget) |

## Observations

- **Pod loss costs ~12 s** with a cached model and warm-up; with one replica
  that is user-visible (1 failed request in 126). `min: 2` replicas (as the
  V7 proposal used) turns this into zero user impact at the cost of memory.
- **Losing the metrics pipeline is not an outage** — serving continued with
  0 failures — but the HPA freezes at its current size within 5 s and the
  alert exists for that reason. Recovery after restore took 46 s (adapter
  start + first successful metric read).
- **The ingress is a single point of failure on a single node**, and the
  ingress-based SLI cannot see its own absence. On EKS the controller runs
  with ≥ 2 replicas behind an ALB; locally the `Recreate` strategy makes the
  outage window (16 s) explicit rather than a scheduling deadlock. A
  black-box probe from outside the cluster (blackbox-exporter or a synthetic
  check) is the standard fix and is queued.
- **Burn-rate alerts stayed quiet through short faults**, which is what
  multi-window alerting is for: a 12 s blip in a 99.5 % / 30-day SLO is not
  page-worthy; a sustained failure would cross the 1 h + 5 m windows.
