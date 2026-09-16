# Project Status

_Last updated: 2026-09-16_

## Current phase

**V2 complete (Kubernetes on kind + Helm).** Next: V3 CI/CD (GitHub Actions,
Argo CD on kind). AWS is deliberately last (ADR 0005).

## Completed

### V1 — local Docker end-to-end
- `aiplatform` CLI: `init`, `validate`, `deploy`, `status`, `logs`, `rollback`,
  `destroy`, `models`; Pydantic config schema, model catalog with memory
  minimums, step pipeline, `local` Docker target with release history.
- `llm-service`: OpenAI-compatible inference API (Qwen2.5-0.5B via llama.cpp),
  Prometheus metrics, JSON logs, hardened multi-stage image.
- Terraform: `network`, `ecr`, `ec2-service` modules, `dev`/`staging` roots,
  state bootstrap. Validated, **not applied**.
- Baseline: `docs/benchmarks/2026-09-16-v1-local-baseline.md`.

### V2 — Kubernetes on kind + Helm
- Helm chart `deploy/helm/llm-workload` (Deployment with hardened security
  context and three probes, Service, Ingress, HPA, PDB, ServiceAccount, PVC
  with keep policy). Lints with `--strict`.
- `aiplatform cluster up|down|status`: single-node kind cluster with pinned
  ingress-nginx 4.15.1 and metrics-server 3.14.0.
- `kind` target: build → kind load → helm upgrade --install (env values +
  generated values) → rollout status → ingress health check → record;
  rollback via `helm rollback`; destroy via `helm uninstall`.
- Shared steps refactor: build/health/record are composed by both targets.
- 71 CLI tests + 11 service tests, ruff clean, `make check` green.
- Baseline: `docs/benchmarks/2026-09-16-v2-kind-baseline.md`.

## Current architecture

See `docs/ARCHITECTURE.md`. CLI → step pipeline → target (`local` Docker or
`kind` Helm) → `llm-service` pod/container serving a GGUF model with
Prometheus metrics, reachable through ingress-nginx at
`http://<name>.<env>.127.0.0.1.nip.io`.

## Known issues

- **CPU HPA scales on model-load spikes** (observed: 856m vs 1-core request
  during startup → unnecessary second replica). V5 moves autoscaling to
  inference metrics (queue depth / in-flight).
- Cold image build ≈ 3.5 min (llama.cpp compile). V3 should cache the built
  wheel layer in CI.
- Redeploy with two replicas took 148 s due to the conservative rolling
  update; acceptable for now, revisit with V5 measurements.
- Model cache PVC is ReadWriteOnce: fine on one kind node, not on multi-node
  EKS. Decision deferred to the AWS phase.
- Streaming responses not implemented; no log aggregation yet (V4).
- Rich wraps long step details at 80 columns when output is not a TTY
  (cosmetic).

## Measurements

Real measurements only, in `docs/benchmarks/`:

- `2026-09-16-v1-local-baseline.md` — Docker target: cold deploy 242 s, warm
  6 s, rollback 4 s, ~9.4 tok/s on 2 threads, 450 MB image, 647 MiB RSS.
- `2026-09-16-v2-kind-baseline.md` — kind target: cluster up 89 s, first
  deploy 38 s, rollback 14 s, 6.1 s for 35 tokens via ingress.

## Next priorities

1. **V3 CI/CD:** GitHub Actions (ruff, pytest, terraform fmt/validate,
   helm lint, checkov, docker build with cache); Argo CD on kind with an
   Application per environment; `aiplatform deploy` submitting via Git.
2. **V4 observability:** kube-prometheus-stack + OpenTelemetry on kind;
   inference dashboards from the existing `llm_*` metrics.
3. **V5:** k6 load tests; HPA on queue depth via Prometheus Adapter or KEDA.
