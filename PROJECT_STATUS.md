# Project Status

_Last updated: 2026-09-16_

## Current phase

**V1 — local end-to-end + single-instance AWS deployment.** Local half done
and measured; AWS half written and validated but not applied.

## Completed

- Repository scaffolding, `CLAUDE.md`, `README.md`, `docs/ARCHITECTURE.md`,
  ADRs 0001–0004, `TODO.md`, `Makefile`.
- **CLI (`cli/`)**: `init`, `validate`, `deploy`, `status`, `logs`, `rollback`,
  `destroy`, `models`. Pydantic config schema with DNS-1123 names, Kubernetes
  quantity parsing, autoscaling bounds, model catalog with memory minimums.
  Step pipeline with ✓/✗ reporting. `local` Docker target with CPU/memory
  limits, model cache volume, liveness+readiness gating, release history and
  rollback. 56 unit tests, ruff clean.
- **Sample workload (`services/llm-service/`)**: FastAPI OpenAI-compatible
  `/v1/chat/completions`, `/v1/models`, `/healthz`, `/readyz`, `/metrics`.
  Backends: `mock` and `llamacpp` (Qwen2.5-0.5B-Instruct Q4_K_M). Background
  model load, semaphore admission control with queue-depth metric, JSON
  logging with request ids. Multi-stage Dockerfile, non-root, healthcheck.
  11 tests.
- **Terraform (`infra/terraform/`)**: `network`, `ecr`, `ec2-service` modules;
  `environments/dev` and `staging` roots with S3 backend (native lockfile);
  `bootstrap` state bucket. All `terraform validate` clean. **Not applied.**
- **Local end-to-end verified** on 2026-09-16: cold deploy 242 s, warm deploy
  6 s, rollback 4 s, ~9 tok/s on 2 CPU threads. See
  `docs/benchmarks/2026-09-16-v1-local-baseline.md`.

## Current architecture

See `docs/ARCHITECTURE.md`. CLI → step pipeline → `local` Docker target →
`llm-service` container serving a GGUF model with Prometheus metrics.

## Known issues

- Cold image build takes ~3.5 min because llama-cpp-python compiles from
  source. Mitigation planned in V3 (cached base image / wheel).
- `aiplatform logs` on the local target passes through `docker logs`; there
  is no log aggregation yet (V4).
- Streaming responses are not implemented (`stream: true` returns 400).
- Local host port equals the container port; two workloads on the same port
  would collide. Add a `local.hostPort` override if this becomes a problem.
- The `aws` CLI target (push to ECR + deploy to EC2) is not implemented yet;
  the Terraform for it is.

## Measurements

Real measurements only, in `docs/benchmarks/`:

- `2026-09-16-v1-local-baseline.md` — first end-to-end run.

## Next priorities

1. **AWS V1 (cost-gated, ≈ $14/month while up):** bootstrap state bucket,
   apply `dev` with `enable_compute=false`, add the `aws` CLI target (ECR
   login/push, `terraform apply` with the new tag, SSM-based health check),
   then enable compute, verify, destroy. Requires AWS CLI + credentials.
2. Security scanning of Terraform (checkov) and images — cheap to add now,
   wired into CI in V3.
3. Start V2: `eks` module design (cost analysis first).
