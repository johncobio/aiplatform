# HPA cannot read its metric (AiplatformHPAMetricUnavailable)

The queue-based HPA depends on Prometheus → prometheus-adapter →
`custom.metrics.k8s.io`. When any link breaks the HPA reports `<unknown>`,
keeps the current replica count, and Argo CD marks the Application Degraded.

## Symptoms
```
kubectl -n aiplatform-<env> get hpa            # TARGETS <unknown>/2
kubectl -n aiplatform-<env> describe hpa <workload> | grep -A4 Conditions   # FailedGetPodsMetric
```

## Check
```
kubectl -n observability get pods                                   # adapter, prometheus up?
kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1 | head -c 300 # API served?
kubectl get --raw "/apis/custom.metrics.k8s.io/v1beta1/namespaces/aiplatform-<env>/pods/*/llm_pending_requests"
curl -s 'http://prometheus.127.0.0.1.nip.io/api/v1/query' --data-urlencode 'query=aiplatform:llm_pending_requests'
```
- Adapter pod missing → it was paused (`aiplatform cluster addon pause metrics|observability`) or evicted.
- API served but empty → the recording rule has no series: ServiceMonitor
  missing, Prometheus not scraping the pod, or the engine's metric name changed.

## Mitigate
1. `aiplatform cluster addon resume metrics` (restores adapter, Prometheus, operator, kube-state-metrics).
2. Recreate the rules: `kubectl apply -f deploy/observability/rules.yaml`.
3. Emergency scaling by hand: `kubectl -n aiplatform-<env> scale deploy <workload> --replicas=N`
   (the HPA will take over again once its metric returns).

## Escalate
Not user-facing by itself; escalate if it coincides with queue saturation.

## Follow-up
Measured in the chaos experiment `adapter-outage` (`chaos/results/`).
