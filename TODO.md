# Backlog

Issue-style backlog grouped by phase. Move items to `PROJECT_STATUS.md`
"Completed" when done. Keep this honest: if something is dropped, say why.

## V1 — Local end-to-end + minimal AWS

- [x] CLI skeleton (`init`, `validate`, `deploy`, `status`, `logs`, `rollback`, `destroy`)
- [x] Config schema (`aiplatform.yaml`) with Pydantic validation
- [x] Model catalog with memory requirements; validation rejects impossible combos
- [x] Step pipeline with ✓/✗ output and structured logs
- [x] `local` target (Docker): build, run, health check, status, logs, rollback, destroy
- [x] Sample service: OpenAI-compatible `/v1/chat/completions`, `/healthz`, `/readyz`, `/metrics`
- [x] Backends: `mock` (tests/CI) and `llamacpp` (real small model)
- [x] Multi-stage Dockerfile, non-root user, healthcheck
- [x] Tests: config validation, pipeline, service API
- [x] Terraform modules: `network`, `ecr`, `ec2-service`; `environments/dev`
- [x] Remote state bootstrap (S3 + native lockfile)
- [ ] `aws` target: push to ECR, deploy to EC2 via SSM, health check (cost-gated) — moved to the AWS section
- [x] Record first measurements: image build time, image size, model load time, local tokens/sec
- [x] Setup/teardown docs

## V2 — Kubernetes (kind) / Helm

- [x] Helm chart for LLM workloads (Deployment, Service, Ingress, HPA, PDB, ServiceAccount, PVC)
- [x] `aiplatform cluster up|down|status`: kind + ingress-nginx + metrics-server (pinned)
- [x] `kind` target in CLI (build, kind load, helm upgrade --install, rollout status, ingress health check, helm rollback)
- [x] Environment overlays dev/staging (`deploy/environments/<env>/values.yaml`)
- [ ] Skip `kind load` when the image already exists in the node (minor)
- [ ] Decide model distribution for multi-node clusters (bake into image vs S3 init container vs EFS); RWO PVC only works on one node

## V3 — CI/CD

- [x] GitHub Actions: ruff, pytest, terraform fmt/validate, checkov, helm lint, hadolint, actionlint
- [x] Multi-arch image publish to GHCR on main (native amd64 + arm64 runners, GHA cache, Trivy scan)
- [x] Argo CD on kind (pinned chart), AppProject + ApplicationSet over `deploy/workloads/<env>/*.values.yaml`
- [x] `gitops` target: verify image → write desired state → commit/push → wait for Synced/Healthy → probe
- [ ] Pin third-party GitHub Actions to commit SHAs (supply-chain hardening)
- [ ] PR-based flow (`deploy --pr`) as the base for V7 human approval
- [ ] OIDC federation GitHub → AWS and ECR publishing — moved to the AWS section

## V4 — Observability

- [ ] kube-prometheus-stack (Prometheus, Grafana, Alertmanager)
- [ ] OpenTelemetry Collector + traces from the service
- [ ] Grafana dashboards: request rate, P50/P95/P99, tokens/sec, queue depth, replicas, CPU/mem, cost estimate

## V5 — Load testing and autoscaling

- [ ] k6 load test scenarios
- [ ] HPA on custom metrics (queue depth / in-flight) via Prometheus Adapter or KEDA
- [ ] Benchmarks recorded in `docs/benchmarks/`

## V6 — Real LLM serving

- [ ] vLLM deployment (GPU node group, cost-gated, spot where possible)
- [ ] vLLM native metrics wired into dashboards
- [ ] Model catalog entries for GPU models

## V7 — AI infrastructure agent with guardrails

- [ ] `aiplatform propose "<request>"` → generated Terraform/config diff
- [ ] Pipeline: fmt → validate → plan → checkov → conftest/OPA → cost estimate → human approval → PR
- [ ] OPA policies: required tags, no public S3, instance type allowlist, cost caps

## AWS (deferred until the local platform is complete)

- [ ] Bootstrap state bucket; apply `dev` with `enable_compute=false` (cost ≈ $0)
- [ ] `eks` Terraform module (managed node group, small Graviton nodes, public subnets, IRSA)
- [ ] `eks` target in CLI (ECR push instead of kind load; same chart)
- [ ] Ingress via AWS Load Balancer Controller (cost-gated: ALB ≈ $16/mo)
- [ ] OIDC federation GitHub → AWS; Argo CD pointed at EKS
- [ ] Decide whether the V1 `ec2-service` module is still worth applying or is superseded by EKS

## V8 — Reliability

- [ ] SLOs and error budget definitions
- [ ] Alert rules and Alertmanager routing
- [ ] Chaos experiments (pod kill, node drain, latency injection)
- [ ] Incident runbooks in `docs/runbooks/`
