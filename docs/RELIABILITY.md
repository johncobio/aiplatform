# Reliability

How the platform defines "working", how it notices when it is not, and how
it has been broken on purpose. Alert rules: `deploy/observability/slo-rules.yaml`.
Runbooks: `docs/runbooks/`. Experiments: `chaos/`.

## Service level objectives

Measured at ingress-nginx so every engine is held to the same standard
(ADR 0011). One SLI set per `(environment, workload)`.

| SLO | SLI | Target | Window | Why this number |
|-----|-----|--------|--------|-----------------|
| Availability | share of requests that are not HTTP 5xx | 99.5 % | 30 days rolling | CPU inference on small nodes restarts pods on every deploy; 99.5 % (3.6 h/month of budget) is honest for a single-node platform and tightens on EKS. |
| Latency | share of requests completing within 5 s | 90 % | 1 hour | The V5 baseline: median 0.7–1.9 s, P95 2–4 s at 1–2 clients. 5 s marks "a user gave up". |

Error budget = 1 − target. The recording rule `aiplatform:error_budget_remaining:ratio`
tracks how much of the 30-day budget is left.

### Error budget policy
- Budget > 50 % remaining: ship freely; `propose` PRs merge on one review.
- Budget 10–50 %: no capacity-reducing changes; every deploy needs a load-test run.
- Budget exhausted: only reliability work merges until the 30-day window recovers.

## Alerting

Multi-window, multi-burn-rate alerts (Google SRE Workbook, ch. 5) instead of
static thresholds, so a short blip pages nobody and a sustained problem pages
quickly:

| Alert | Fires when | Severity | Runbook |
|-------|-----------|----------|---------|
| AiplatformErrorBudgetBurnFast | burn rate > 14.4× over 1 h **and** 5 m | page | error-budget-burn |
| AiplatformErrorBudgetBurnSlow | burn rate > 6× over 6 h **and** 30 m | ticket | error-budget-burn |
| AiplatformLatencySLOViolation | < 90 % of requests within 5 s for 10 m | ticket | latency |
| AiplatformWorkloadDown | desired > 0, ready = 0 for 2 m | page | workload-down |
| AiplatformQueueSaturated | pending/pod > target at max replicas for 10 m | ticket | queue-saturated |
| AiplatformHPAMetricUnavailable | HPA ScalingActive=false for 5 m | ticket | hpa-metric-unavailable |
| AiplatformScrapeMissing | workload `/metrics` down for 5 m | ticket | workload-down |

Alertmanager (`alertmanager.127.0.0.1.nip.io`) routes by alertname,
environment and workload with a `null` receiver locally; a Slack/webhook
receiver is documented in `deploy/kind/kube-prometheus-stack.values.yaml`
and takes its URL from a mounted Secret, never the repo.

## Chaos experiments

`python chaos/experiment.py <experiment>` keeps a 1-VU load running,
injects one fault with plain `kubectl`, and measures recovery from the
cluster's own signals. Results (with dates) are in `chaos/results/` and
summarised in `docs/benchmarks/2026-09-16-v8-reliability.md`.

| Experiment | Fault | What must recover |
|------------|-------|-------------------|
| pod-kill | delete the serving pod | new pod Ready, endpoint serving |
| adapter-outage | scale prometheus-adapter to 0, then back | HPA `ScalingActive` false → true; alert pending |
| ingress-restart | restart the single ingress-nginx controller | ingress serving again; count failed requests |

## Known failure modes (from building V1–V7)

| Failure | Seen in | Signal | Fix / guard |
|---------|---------|--------|-------------|
| Host swap stalls etcd; control plane crash-loops | V4, V5 | API timeouts, load avg > 50 | Docker VM ≤ 4 GB / 4 vCPU; `cluster addon pause` |
| Rolling update cannot schedule the surge pod | V3, V5 | Pending, `Insufficient memory` | memory sized for 2× during rollout; runbook workload-down |
| CPU-based HPA scales on model-load burst | V2 | replicas ↑ with no traffic | queue-based HPA (ADR 0008) |
| Cold model after idle (mmap eviction) | V4 | first request 19–52 s | `LLM_MLOCK` + warm-up |
| HPA loses its metric when the adapter is paused | V5 | `<unknown>`, Argo Degraded | AiplatformHPAMetricUnavailable; runbook |
| hostPort ingress cannot roll on one node | V6 | new controller pod Pending | `updateStrategy: Recreate` |
| Init container without resources | V7 | OPA denial | chart fixed; policy stays |
