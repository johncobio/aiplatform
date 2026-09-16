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
- [ ] `aws` target: push to ECR, deploy to EC2 via SSM, health check (cost-gated)
- [x] Record first measurements: image build time, image size, model load time, local tokens/sec
- [x] Setup/teardown docs

## V2 — Kubernetes / EKS / Helm

- [ ] `eks` Terraform module (managed node group, small Graviton nodes, no NAT if possible via public subnets + IRSA)
- [ ] Helm chart for LLM workloads (Deployment, Service, HPA, PDB, ServiceAccount)
- [ ] `eks` target in CLI (helm upgrade --install, rollout status)
- [ ] Environment overlays dev/staging
- [ ] Ingress via AWS Load Balancer Controller (cost-gated: ALB ≈ $16/mo)

## V3 — CI/CD

- [ ] GitHub Actions: lint, test, terraform fmt/validate, checkov, docker build
- [ ] OIDC federation GitHub → AWS (no static keys)
- [ ] Image publish to ECR on main
- [ ] Argo CD install + Application per environment; CLI `deploy` submits via Git

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

## V8 — Reliability

- [ ] SLOs and error budget definitions
- [ ] Alert rules and Alertmanager routing
- [ ] Chaos experiments (pod kill, node drain, latency injection)
- [ ] Incident runbooks in `docs/runbooks/`
