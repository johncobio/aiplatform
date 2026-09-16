# V3 CI/CD + GitOps baseline — 2026-09-16

**Setup:** same laptop, Docker Desktop back at 4 GB (see known issues), kind
cluster with ingress-nginx, metrics-server and Argo CD 3.5.3. Public GitHub
repo, free Actions runners (`ubuntu-24.04`, `ubuntu-24.04-arm`). Sample
workload sized `cpu: 2`, `memory: 1Gi`.

## CI (GitHub Actions)

| Measurement | Value | Source |
|-------------|-------|--------|
| `ci.yml` (lint, tests ×2, terraform validate ×6, Checkov, helm lint, hadolint, actionlint) | 1 min 24 s | run 35137348959 |
| Image build, cold cache, arm64 native | 3 min 40 s | run 35137349038 |
| Image build, cold cache, amd64 native | 5 min 12 s | run 35137349038 |
| Image build, warm cache, arm64 / amd64 | 25 s / 41 s | run 35141882937 |
| Whole `build-image.yml`, warm cache (build ×2 + manifest publish) | 1 min 07 s | run 35141882937 |
| Dependency-layer cache miss after `pyproject.toml` change (recompiles llama.cpp) | 5 min 18 s | run 35142135528 |
| Multi-arch manifest publish | 11–25 s | all runs |

## GitOps deploys (`aiplatform deploy --target gitops --env staging`)

| Measurement | Value |
|-------------|-------|
| Image pull from GHCR onto the kind node (450 MB, layers cached) | 4.5 s |
| No-change deploy (verify image, sync check, probe) | 3.9 s |
| Rollback (rewrite tag → commit → push → Argo CD sync → rollout → healthy) | 18 s |
| Forward deploy with rolling update, model cached in PVC | 56.7 s |
| Model load inside the pod (`/readyz` `load_seconds`) | 14.2 s (first run in new pod), 0.7 s cached |
| Commit-to-running, service change with warm CI cache (≈ CI 1 min 07 s + deploy 57 s) | ≈ 2 min |

## Observations

- **Argo CD polling is not the bottleneck** once the CLI nudges it with
  refresh annotations: sync starts within seconds of the push. The rollout
  (startup probe every 10 s + model load) dominates the forward deploy.
- **Capacity, not speed, was the real failure mode.** A memory request equal
  to the limit means a zero-downtime rollout needs 2× memory on the node.
  With Argo CD (~1 GiB of requests) on a 3.9 GiB-allocatable node, a 2 GiB
  workload could not be rolled at all; at 1 GiB it can. On EKS this is a
  node-sizing and cluster-autoscaler question, not a chart question.
- **Trivy found real, fixable base-image CVEs** (pcre2, rated HIGH by
  Debian and CRITICAL by NVD). `apt-get upgrade` in the runtime stage removed
  them; the scan gate is now meaningful rather than cosmetic.
- **Cache keying matters:** a one-line version bump in `pyproject.toml`
  invalidated the compiled-dependency layer and cost 5 minutes. Splitting
  runtime dependencies from project metadata is queued in `TODO.md`.
