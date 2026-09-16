# Latency SLO violation (AiplatformLatencySLOViolation)

**SLO:** 90 % of requests complete within 5 s at the ingress over 1 h.

## Symptoms
- *Latency at ingress P50/P95/P99* rising; *Pending requests* per pod > target.
- Clients see slow but successful responses (not 5xx).

## Check
```
kubectl -n aiplatform-<env> get hpa <workload>          # at max replicas? metric unknown?
kubectl -n aiplatform-<env> top pod                     # CPU at limit → contention
curl -s 'http://prometheus.127.0.0.1.nip.io/api/v1/query' --data-urlencode \
  'query=aiplatform:llm_generation_tokens_per_second:p50_5m{workload="<workload>"}'
```
Generation speed down with same load → CPU contention (another workload,
node pressure, cold model after eviction). Speed unchanged but queue up →
demand exceeds capacity.

## Mitigate
- Demand: raise `autoscaling.max` (within `policy/data/limits.yaml`) or add
  nodes (EKS); on the laptop, pause other add-ons.
- Contention: `kubectl describe node` for other consumers; check
  `LLM_MLOCK`/warm-up are on (cold model shows as one very slow first request).
- Long prompts: cap `max_tokens` client-side or lower `model.contextLength`.

## Escalate
If P95 > 30 s for 10 min, treat as availability (clients time out).

## Follow-up
Compare with `docs/benchmarks/2026-09-16-v5-load-and-autoscaling.md`; if the
baseline moved, re-run the load tests and update the SLO target deliberately.
