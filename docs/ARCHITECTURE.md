# Architecture

_Status: V2 (local Docker target and Kubernetes-on-kind target implemented; AWS Terraform written, not applied)._
Update this document and add an ADR whenever the architecture changes.

## Goal

Give a developer a one-command path from a small configuration file to a
running, health-checked, observable LLM workload. The platform owns the
"how" (build, push, deploy, verify); the developer owns the "what"
(`aiplatform.yaml`).

## System overview

```mermaid
flowchart LR
    subgraph Developer
        cfg[aiplatform.yaml]
        cli[aiplatform CLI]
    end

    subgraph Pipeline["deploy pipeline (steps)"]
        v1[validate config]
        v2[resolve model catalog]
        b[build image]
        d[deploy to target]
        h[health check]
    end

    subgraph Targets
        local[local: Docker]
        kind[kind: Helm on kind\ningress-nginx + metrics-server]
        eks[eks: Helm on EKS (later)]
    end

    subgraph Workload["llm-service container"]
        api[FastAPI\n/v1/chat/completions]
        be[backend: llama.cpp | mock | vLLM (V6)]
        met[/metrics Prometheus/]
        api --> be
        api --> met
    end

    cfg --> cli --> v1 --> v2 --> b --> d --> h
    d --> local
    d --> kind
    d --> eks
    local --> Workload
    kind --> Workload
    eks --> Workload
```

## Components

### `aiplatform` CLI (`cli/`)

- **Config** (`aiplatform.config`): Pydantic schema for `aiplatform.yaml`.
  Validates names (DNS-1123), CPU/memory quantities (Kubernetes syntax), and
  autoscaling bounds. Resolves `model:` against the model catalog and rejects
  combinations that cannot run (e.g. an 8B model with 2Gi memory).
- **Steps** (`aiplatform.steps`): a `Step` has a name and a `run(ctx)`; the
  `Pipeline` executes steps in order, prints `✓ name` / `✗ name`, logs
  structured events, and stops at the first failure. Every phase of the
  project adds steps rather than commands.
- **Targets** (`aiplatform.targets`): `Target` interface with `deploy`,
  `status`, `logs`, `rollback`, `destroy`, each expressed as steps. Shared
  steps (`steps/docker.py`, `steps/health.py`, `steps/record.py`) are composed
  by every target so behaviour stays identical.
  - `local`: Docker CLI via subprocess.
  - `kind`: builds the image, `kind load`s it, runs `helm upgrade --install`
    with generated values, waits for rollout, probes the ingress. Rollback is
    `helm rollback` to the previous revision.
  - `eks` (later): same chart; pushes to ECR instead of `kind load`.
- **Cluster** (`aiplatform.cluster`, `aiplatform cluster up|down|status`):
  creates the single-node kind cluster from `deploy/kind/cluster.yaml` and
  installs pinned add-ons: ingress-nginx (host ports 80/443) and
  metrics-server (HPA). Workloads are reachable at
  `http://<name>.<env>.127.0.0.1.nip.io`.
- **State**: per-workload deployment history in `.aiplatform/<env>/<name>.json`
  (image tags, timestamps) so `rollback` can re-deploy the previous release.

### Sample workload: `llm-service` (`services/llm-service/`)

An OpenAI-compatible inference API that *serves a model itself* instead of
proxying to a hosted API.

- `POST /v1/chat/completions` (non-streaming in V1), `GET /healthz`
  (process alive), `GET /readyz` (model loaded), `GET /metrics`.
- Backends behind one interface: `mock` (deterministic, no model, used by
  tests and CI) and `llamacpp` (a GGUF model on CPU; default model
  Qwen2.5-0.5B-Instruct Q4_K_M, ~400 MB, runs in ~1 GB RAM). V6 adds vLLM
  behind the same API contract.
- Concurrency: llama.cpp generation is serialized with a semaphore; requests
  waiting for the slot are counted as **queue depth**, which is the signal
  V5 autoscaling will use.
- Metrics (Prometheus): `llm_requests_total`, `llm_request_duration_seconds`,
  `llm_prompt_tokens_total`, `llm_completion_tokens_total`,
  `llm_generation_tokens_per_second`, `llm_model_load_seconds`,
  `llm_inflight_requests`, `llm_queue_depth`, `llm_model_info`.

### Helm chart: `llm-workload` (`deploy/helm/llm-workload/`)

The deployment contract for every Kubernetes target. Renders a Deployment
(rolling update with zero unavailable, startup/readiness/liveness probes,
non-root, read-only root filesystem, all capabilities dropped), Service,
Ingress, HPA when `autoscaling.max > 1`, PDB when more than one replica can
exist, ServiceAccount (token not auto-mounted) and a `keep`-annotated PVC for
the model cache. The CLI translates `aiplatform.yaml` into values
(`cli/src/aiplatform/targets/kind.py: build_values`): CPU request is half the
limit, memory request equals the limit. Environment overrides live in
`deploy/environments/<env>/values.yaml`; one namespace per environment
(`aiplatform-<env>`).

### Infrastructure (`infra/terraform/`)

- `modules/network`: VPC, two public subnets across AZs, IGW, route table.
  **No NAT gateway** in V1 (≈ $32/month by itself). Private subnets are added
  with EKS in V2 only if required.
- `modules/ecr`: one repository per workload, scan-on-push, lifecycle policy
  keeping the last 10 images.
- `modules/ec2-service`: a Graviton `t4g.small` running the container via
  Docker; IAM instance role with ECR pull + SSM Session Manager only (no SSH
  keys, no inbound 22). Stepping stone that V2 replaces with EKS.
- `environments/dev`: root module wiring the above. Remote state in S3 with
  Terraform's native lockfile (`use_lockfile = true`), created by
  `bootstrap/`.

## Data flow: `aiplatform deploy --target local`

1. Load and validate `aiplatform.yaml`; resolve model catalog entry.
2. `docker build` the service directory → `aiplatform/<name>:<git-sha-or-timestamp>`.
3. Stop the previous container (if any); `docker run` with CPU/memory limits
   from the config, model cache volume mounted from `~/.aiplatform/models`.
4. Poll `/healthz` then `/readyz` until ready (model download + load happens
   here on first run).
5. Record the release in local state; print the endpoint.

## Data flow: `aiplatform deploy --target kind`

1. Validate config, resolve model; check Docker, kind cluster and context.
2. `docker build`, then `kind load docker-image` into the node's containerd.
3. Write generated values to `.aiplatform/<env>/<name>.values.yaml`; run
   `helm upgrade --install` with environment values + generated values.
4. `kubectl rollout status`, then probe `/healthz` and `/readyz` through the
   ingress host.
5. Record the release; print the endpoint.

## Cross-cutting

- **Security**: no secrets in repo; non-root container user; least-privilege
  IAM; image scanning on push.
- **Logging**: JSON logs from the service; CLI logs human-readable with
  `--verbose` for step details.
- **Cost**: every AWS-creating command is cost-gated and documented with a
  monthly estimate and a destroy path. See `docs/COST.md` once created.

## Decisions

See `docs/adr/` for the reasoning behind each major choice.
