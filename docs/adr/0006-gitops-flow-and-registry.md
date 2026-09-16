# 0006 — GitOps deployment flow, GHCR as the interim registry

2026-09-16 · Accepted

## Context

V3 needs CI, an image registry and Argo CD. AWS (and therefore ECR) is
deferred (ADR 0005). The developer experience must stay `aiplatform deploy`
while the actual deployment is reconciled from Git.

## Decision

- **CI builds, Git deploys.** GitHub Actions builds `llm-service` natively on
  amd64 and arm64 runners, publishes a multi-arch manifest to GHCR tagged
  `sha-<short commit>`, and scans it with Trivy. Images are built only when
  `services/llm-service/**` changes.
- **Desired state is a values file.** `deploy/workloads/<env>/<name>.values.yaml`
  is the unit of deployment. An Argo CD ApplicationSet (git file generator)
  turns every such file into an Application that renders the
  `llm-workload` chart with the environment overlay plus that file.
- **`aiplatform deploy --target gitops`** verifies the image for the last
  commit that touched the service exists in the registry, writes the values
  file, commits and pushes it, nudges Argo CD via refresh annotations, and
  waits for `Synced`/`Healthy` at the pushed revision before probing the
  ingress. Rollback rewrites the previous tag; destroy deletes the file.
- **GHCR now, ECR later.** GHCR is free for public repos and needs no cloud
  account. The AWS phase adds ECR as a second registry (`platform.yaml`
  `registry:`) without changing the flow.
- **Convention:** `dev` is for direct deploys (`--target kind`), `staging` is
  GitOps-managed. The gitops target refuses to deploy over a direct Helm
  release in the same namespace.

## Consequences

- The platform demonstrates the industry-standard split: CI produces
  artifacts, CD reconciles declared state, and humans (or the CLI) only
  touch Git. This is also the foundation V7's human-approval flow builds on
  (propose → PR → merge → Argo CD).
- A deploy takes two commits' worth of history: the code commit that CI
  built and the desired-state commit that references it.
- Argo CD polls Git; without webhooks (a laptop has no public URL) the CLI
  uses refresh annotations to avoid the 60 s poll delay.
- Argo CD adds ~5 pods to the kind cluster; on the 8 GB laptop this means
  running one LLM workload at a time.
