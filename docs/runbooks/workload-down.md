# Workload down (AiplatformWorkloadDown, AiplatformScrapeMissing)

## Symptoms
- `kube_deployment_status_replicas_ready == 0`; ingress returns 503.
- ScrapeMissing: the pod runs but `/metrics` is unreachable (readiness flapping, port change).

## Check
```
kubectl -n aiplatform-<env> get pods -l app.kubernetes.io/instance=<workload>
kubectl -n aiplatform-<env> describe pod -l app.kubernetes.io/instance=<workload> | grep -A10 Events
kubectl -n aiplatform-<env> logs -l app.kubernetes.io/instance=<workload> --previous --tail 50
```
Common causes seen on this platform:
| Event / log | Cause | Fix |
|---|---|---|
| `Insufficient memory` (Pending) | node cannot fit the pod (rolling-update surge needs 2× memory) | pause an add-on, lower `memory`, or add nodes |
| `OOMKilled` | limit too low for the model | raise `memory` (catalog minimum), keep `LLM_MLOCK` in budget |
| startup probe failing > 10 min | model download stalled | check egress / PVC; `kubectl exec` and `ls -la /models` |
| `ImagePullBackOff` | tag not built yet (CI) or registry auth | `docker manifest inspect <image>`; wait for the build |
| Argo CD `Degraded` + HPA `<unknown>` | prometheus-adapter down | [hpa-metric-unavailable.md](hpa-metric-unavailable.md) |

## Mitigate
1. Last change was a deploy → `aiplatform rollback` (kind: helm history; gitops: previous tag).
2. Capacity → `aiplatform cluster addon pause <grafana|tracing|argocd>` on the laptop; node group on EKS.
3. Pod stuck Terminating/Pending after a resize → delete the old pod (documented one-time transition in V3).

## Escalate
Page: if no ready replica after 10 minutes and rollback did not help.

## Follow-up
If the model download was the cause, consider baking the model into the image
or pre-warming the PVC (see `TODO.md`, model distribution).
