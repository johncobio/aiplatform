# llm-workload chart

Renders an aiplatform LLM inference workload: Deployment (rolling update,
startup/readiness/liveness probes, hardened security context), Service,
Ingress, optional HPA (CPU for now; inference metrics in V5), PDB when more
than one replica is possible, and a PVC for the model cache.

`image.tag` and `ingress.host` are required. The `aiplatform` CLI sets them
along with resources, model and autoscaling from `aiplatform.yaml`.

```
helm lint deploy/helm/llm-workload
helm template demo deploy/helm/llm-workload --set image.tag=t --set ingress.host=demo.local
```
