# Queue saturated at max replicas (AiplatformQueueSaturated)

## Symptoms
- `aiplatform:llm_pending_requests` per pod above target for 10 min while the
  HPA sits at `maxReplicas`; latency climbing; eventually 504s.

## Check
```
kubectl -n aiplatform-<env> get hpa <workload> -o wide
kubectl -n aiplatform-<env> describe hpa <workload> | grep -A6 Conditions
kubectl top node                                   # is there room for more replicas?
```

## Mitigate
- Raise `autoscaling.max` in `aiplatform.yaml` and deploy (or propose it);
  the policy cap is `policy/data/limits.yaml`.
- On a single CPU-bound node more replicas barely help (V5 finding: +14 %);
  add nodes or a faster engine (`engine: llamacpp-server` was 2.9× the builtin).
- Shed load: lower `max_tokens_limit` (`LLM_MAX_TOKENS_LIMIT`) so each request
  is cheaper; reject at the edge with an ingress rate limit if needed.

## Escalate
If clients time out (504) for more than 15 minutes, treat as an availability
incident and coordinate with the owning team on demand shaping.

## Follow-up
Capacity plan: record req/s per replica from the load tests and set
`max` from the expected peak plus 30 % headroom.
