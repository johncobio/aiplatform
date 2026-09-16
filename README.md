# aiplatform — self-service AI infrastructure platform

A miniature internal developer platform for deploying containerized LLM
workloads. A developer describes a workload in `aiplatform.yaml`; the platform
validates it, builds the image, deploys it, and verifies health, with the same
command on a laptop (Docker) and, in later phases, on AWS EKS via Terraform
and GitOps.

```yaml
# aiplatform.yaml
name: document-agent
model: qwen2.5-0.5b-instruct
cpu: 2
memory: 2Gi
environment: dev
autoscaling:
  min: 1
  max: 3
```

```
$ aiplatform deploy            # actual output from services/llm-service, first run
✓ Configuration validated llm-service (dev)
✓ Model resolved qwen2.5-0.5b-instruct via llamacpp, needs ≥ 1.0Gi
✓ Docker available 29.4.2
✓ Docker image built aiplatform/llm-service:20260916-125321
✓ Container started aiplatform-dev-llm-service
✓ Health checks passed ready after 20.2s
✓ Release recorded 20260916-125321

Endpoint: http://localhost:8000
Deployed in 242.1s. Try: curl http://localhost:8000/v1/models
```

## Why this project exists

It is a portfolio project for DevOps / platform / AI-infrastructure work. The
emphasis is on operating AI infrastructure (serving a model, measuring it,
scaling it, deploying it safely), not on prompting a hosted API. It is built in
phases; see the roadmap below and `PROJECT_STATUS.md` for what is real today.

## Status

**V1 in progress.** Working today:

- `aiplatform` CLI: `init`, `validate`, `deploy`, `status`, `logs`, `rollback`,
  `destroy`, `models` against a `local` Docker target.
- `llm-service`: OpenAI-compatible inference API serving Qwen2.5-0.5B-Instruct
  on CPU with llama.cpp, plus Prometheus metrics (latency, tokens/s, queue
  depth, model load time).
- Terraform modules for the V1 AWS footprint (network, ECR, single Graviton
  EC2 instance), validated but **not applied** yet.

## Quick start (local, no cloud)

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), Docker Desktop
running, Terraform (only for `make check`).

```
make setup                 # install CLI + service dev deps
make check                 # lint, tests, terraform validate
make run-local             # aiplatform deploy for services/llm-service
curl -s localhost:8000/v1/chat/completions -H 'content-type: application/json' \
  -d '{"messages":[{"role":"user","content":"Explain GitOps in one sentence."}],"max_tokens":64}'
curl -s localhost:8000/metrics | grep ^llm_
make destroy-local
```

The first deploy downloads the model (~400 MB) into `~/.aiplatform/models`,
which is mounted into the container, so later deploys start in seconds.

### Using the CLI on your own workload

```
cd my-service            # must contain a Dockerfile
uv run --project <repo>/cli aiplatform init --name my-service
uv run --project <repo>/cli aiplatform validate
uv run --project <repo>/cli aiplatform deploy
```

## Repository layout

| Path | What |
|------|------|
| `cli/` | `aiplatform` CLI (Python / Typer). Config schema, model catalog, step pipeline, deployment targets. |
| `services/llm-service/` | Sample workload: inference API with metrics. |
| `infra/terraform/` | Reusable modules and per-environment roots. |
| `deploy/` | Helm charts and Argo CD manifests (V2+). |
| `policy/` | OPA / Conftest policies (V7). |
| `docs/` | Architecture, ADRs, benchmarks, runbooks. |

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the diagram and
component descriptions, and [`docs/adr/`](docs/adr/) for decisions.

## Roadmap

| Phase | Scope |
|-------|-------|
| V1 | Local end-to-end, Terraform modules, single EC2 deploy |
| V2 | EKS, Helm, environments |
| V3 | GitHub Actions CI, ECR publishing, Argo CD |
| V4 | Prometheus, Grafana, OpenTelemetry dashboards |
| V5 | Load testing, autoscaling on inference metrics, benchmarks |
| V6 | vLLM on GPU nodes |
| V7 | AI-proposed infrastructure changes with validation, policy, cost and human approval gates |
| V8 | SLOs, alerting, chaos testing, runbooks |

## Cost policy

The owner is a student. Nothing in this repo creates AWS resources without an
explicit `terraform apply` or a cost-gated CLI command, every environment has
a `destroy` path, and estimated monthly costs are documented before use. See
`docs/adr/0003-ec2-stepping-stone-before-eks.md`.

## Teardown

```
make destroy-local                                  # local container
cd infra/terraform/environments/dev && terraform destroy   # AWS (when applied)
```
