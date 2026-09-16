# CLAUDE.md — repository conventions for AI-assisted sessions

This file is read at the start of every Claude Code session. Follow it before
anything else in the repo. Human-facing docs live in `README.md` and `docs/`.

## What this project is

`aiplatform` is a self-service internal developer platform for deploying
containerized LLM workloads. A developer writes `aiplatform.yaml`, runs
`aiplatform deploy`, and the platform validates, builds, deploys, and health
checks the workload. It is built incrementally (V1..V8, see `TODO.md`) with a
strong focus on DevOps / platform engineering / AI infrastructure practice.

The owner is a student targeting DevOps / Platform / AI Infra roles. Cost
control on AWS is a hard requirement, not a preference.

## Repository map

| Path | Purpose |
|------|---------|
| `cli/` | The `aiplatform` CLI (Python, Typer, Pydantic). Package `aiplatform`. |
| `services/llm-service/` | Sample AI workload: OpenAI-compatible inference API with Prometheus metrics. |
| `infra/terraform/modules/` | Reusable Terraform modules (`network`, `ecr`, `ec2-service`, later `eks`). |
| `infra/terraform/environments/` | Per-environment root modules (`dev`, `staging`). |
| `infra/terraform/bootstrap/` | One-time remote state bucket. |
| `deploy/helm/llm-workload/` | Helm chart: the deployment contract for every target (kind now, EKS later). |
| `deploy/environments/<env>/values.yaml` | Per-environment chart overrides. |
| `deploy/kind/` | kind cluster config and add-on values (ingress-nginx, metrics-server). |
| `policy/` | OPA / Conftest policies (V7). |
| `docs/ARCHITECTURE.md` | Current architecture and diagram. Update when architecture changes. |
| `docs/adr/` | Architecture Decision Records, numbered `NNNN-title.md`. |
| `docs/benchmarks/` | Real measurements only. |
| `PROJECT_STATUS.md` | Completed features, current architecture, known issues, next priorities. |
| `TODO.md` | Phased backlog. |

## Working rules

1. **Inspect before changing.** Read the relevant files and `PROJECT_STATUS.md` first. Do not rewrite working code without a reason recorded in an ADR.
2. **Work in small increments.** For each task: state intent, change, validate (`make check`), fix, summarize, then update `PROJECT_STATUS.md`.
3. **Cost gate.** Before any command that creates AWS resources (`terraform apply`, `aiplatform deploy --target eks`, ...), state the estimated monthly cost and get explicit confirmation. Never leave a NAT gateway, EKS cluster, GPU instance, or load balancer running without telling the user how to destroy it. Every environment must have a working `make destroy-<env>` path.
4. **No secrets in the repo.** No credentials, account IDs, or tokens in code, docs, or examples. AWS auth comes from the ambient environment (profile / SSO / OIDC). Use `.env.example`, never `.env`.
5. **Least privilege.** IAM policies are scoped to the specific resources they need. Prefer instance / pod roles over static keys.
6. **Dependencies must be justified.** Before adding a library or tool, explain why in the commit or ADR. Prefer the standard library and subprocess calls to well-known CLIs (`docker`, `terraform`, `kubectl`, `helm`) over SDK wrappers.
7. **No invented metrics.** Only record numbers that were actually measured. Put them in `docs/benchmarks/` with the command that produced them.
8. **Keep files small.** One responsibility per module. A file over ~300 lines is a signal to split.
9. **Tests where they pay off.** Config validation, pipeline logic, and API contracts get tests. Do not test the framework.
10. **Documentation is part of the change.** Architecture change → update `docs/ARCHITECTURE.md` and add an ADR. Any change → update `PROJECT_STATUS.md`.

## Conventions

- Python 3.12+, managed with `uv`. Each Python project has its own `pyproject.toml` (`cli/`, `services/llm-service/`). Lint/format with `ruff`. Tests with `pytest`.
- Logging: stdlib `logging`, structured (JSON in containers, human-readable in the CLI). Never `print` for diagnostics in library code; the CLI uses `rich` for user-facing output.
- Errors: raise typed exceptions (`AiPlatformError` subclasses) inside libraries; the CLI entrypoint turns them into a clean message and non-zero exit code.
- Terraform: `terraform fmt` and `terraform validate` must pass. Modules expose `variables.tf`, `outputs.tf`, `main.tf`, `versions.tf`, `README.md`. Tag every resource with `Project`, `Environment`, `ManagedBy`.
- Kubernetes/Helm: one chart per workload type under `deploy/helm/`; environment values under `deploy/environments/<env>/`.
- Commits: conventional commits (`feat:`, `fix:`, `docs:`, `infra:`, `ci:`, `chore:`). Small commits.
- Naming: workload names are DNS-1123 labels (`document-agent`). Docker images: `aiplatform/<name>:<tag>` locally, `<account>.dkr.ecr.<region>.amazonaws.com/aiplatform/<name>:<tag>` in AWS.

## Commands

```
make setup        # install dev deps for cli and service
make check        # lint + tests + terraform fmt/validate
make test         # tests only
make run-local    # aiplatform deploy --target local for the sample service
make cluster-up   # kind cluster + ingress-nginx + metrics-server
make run-kind     # aiplatform deploy --target kind (Helm)
```

Deployment targets: `local` (Docker) and `kind` (Helm on kind). Add new
targets under `cli/src/aiplatform/targets/` by composing the shared steps in
`cli/src/aiplatform/steps/`; never duplicate build/health/record logic.

## Phase roadmap

V1 local Docker → V2 Kubernetes on kind + Helm → V3 GitHub Actions + Argo CD → V4 observability →
V5 load testing + autoscaling → V6 vLLM → V7 AI infra agent with guardrails → V8 SLOs/chaos/runbooks.
AWS (Terraform: VPC, ECR, EKS) is deliberately last; the AWS modules are written and validated but
not applied until the owner says so (see ADR 0005).
See `TODO.md` for the backlog and `PROJECT_STATUS.md` for where we are.
