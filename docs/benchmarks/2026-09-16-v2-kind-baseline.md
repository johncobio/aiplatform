# V2 Kubernetes (kind) baseline — 2026-09-16

**Hardware:** same laptop as the V1 baseline; Docker Desktop VM raised to
5 GB. Single-node kind cluster (`kindest/node` default for kind v0.33.0),
ingress-nginx chart 4.15.1, metrics-server chart 3.14.0.
**Workload:** `services/llm-service` with `cpu: 2`, `memory: 2Gi`,
`autoscaling: {min: 1, max: 3}` → requests cpu 1 / memory 2Gi, limits
cpu 2 / memory 2Gi, HPA at 70% CPU.

## Platform and deployment

| Measurement | Value | Command |
|-------------|-------|---------|
| `aiplatform cluster up` (cluster + 2 add-ons), cold | 89 s | `make cluster-up` |
| First `deploy --target kind` (image cached, model downloaded into PVC) | 38.4 s | `make run-kind` |
| Health check after rollout | 2.3 s | step output |
| Redeploy while HPA had scaled to 2 replicas | 148 s | see note |
| `helm rollback` to previous revision, end to end | 14 s | `aiplatform rollback -t kind` |
| `kind load docker-image` for an unchanged 450 MB image | 2.9 s | measured with `date` |
| Node utilisation with one replica idle | 644m CPU (10%), 1297 MiB (26%) | `kubectl top node` |
| Pod, right after model load | 856m CPU, 207 MiB | `kubectl top pod` |

## Inference through the ingress

```
curl -s http://llm-service.dev.127.0.0.1.nip.io/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"messages":[{"role":"user","content":"What is Kubernetes in one sentence?"}],"max_tokens":48,"temperature":0.2}'
```

| Measurement | Value |
|-------------|-------|
| 36 prompt + 35 completion tokens, wall time via ingress | 6.09 s |

## Observations

- **CPU-based HPA scaled up during model load.** The pod briefly used 856m
  against a 1-core request (85% > 70% target) while loading the model, so the
  HPA added a second replica that nothing needed. This is the classic reason
  CPU is a poor autoscaling signal for inference: V5 replaces it with queue
  depth / in-flight requests from the service's own metrics.
- The 148 s redeploy was a rolling update of two replicas with
  `maxUnavailable: 0`, not image transfer (`kind load` is ~3 s when the image
  already exists in containerd).
- Latency through ingress-nginx on kind is in the same range as the direct
  Docker measurement (V1: 3.4 s for 28 tokens); the proxy adds negligible
  overhead relative to CPU generation time.
