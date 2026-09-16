# Error budget burn (AiplatformErrorBudgetBurnFast / Slow)

**SLO:** 99.5 % of requests at the ingress are not 5xx over 30 days
(`docs/RELIABILITY.md`). *Fast* means the budget would be gone in ~2 days at
the current rate; *Slow* in ~5 days.

## Symptoms
- Grafana "LLM Inference": red 5xx band in *Requests / s at ingress by status*.
- `aiplatform:sli_availability:ratio_rate5m` below 0.93 (fast) / 0.97 (slow).

## Check
```
kubectl -n aiplatform-<env> get pods,hpa                  # crash loops? 0 ready?
kubectl -n aiplatform-<env> describe pod -l app.kubernetes.io/instance=<workload> | tail -20
kubectl -n aiplatform-<env> logs deploy/<workload> --tail 100 | grep -v healthz
curl -s http://<workload>.<env>.127.0.0.1.nip.io/readyz    # /health for upstream engines
curl -s 'http://prometheus.127.0.0.1.nip.io/api/v1/query' --data-urlencode \
  'query=sum by (status) (rate(nginx_ingress_controller_requests{ingress="<workload>"}[5m]))'
```
Which status? `502/503` → pod not ready or ingress cannot reach it; `500` →
engine errors (out of memory, bad request shape); `504` → generation slower
than the ingress timeout.

## Mitigate
1. Pods not ready → see [workload-down.md](workload-down.md).
2. Bad release → `aiplatform rollback --target gitops --env <env>` (or `-t kind`).
3. Overload (503/504 with high pending requests) → see [queue-saturated.md](queue-saturated.md).
4. Ingress controller restarting → `kubectl -n ingress-nginx get pods`; wait or `rollout restart`.

## Escalate
Page severity: if not mitigated in 15 min, roll back the last two merged
desired-state commits and freeze `propose` merges until root cause is known.

## Follow-up
Record the incident (template in `README.md`); if the alert fired late or
falsely, tune the burn-rate windows in `deploy/observability/slo-rules.yaml`.
