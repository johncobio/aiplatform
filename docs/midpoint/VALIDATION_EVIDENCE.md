# Midpoint validation evidence

Recorded October 15, 2026 on the development laptop. These are excerpts of
actual command output, not a cloud deployment or a fresh inference benchmark.

## Local checks

Command: `make check` (exit 0).

```text
CLI: 112 passed in 0.80s
Service: 14 passed, 2 warnings in 0.22s
Terraform: all six roots/modules valid
1 chart(s) linted, 0 chart(s) failed
chart engine checks passed
308 tests, 308 passed, 0 warnings, 0 failures, 0 exceptions
80 tests, 80 passed, 0 warnings, 0 failures, 0 exceptions
```

The two warnings are upstream Starlette test-client deprecations.

GitHub CI also passed all seven jobs on commit `111610a`:
https://github.com/johncobio/aiplatform/actions/runs/38820810497

Command: `uvx checkov --config-file .checkov.yaml --compact` (exit 0).

```text
terraform scan results:
Passed checks: 83, Failed checks: 0, Skipped checks: 0
```

## Workload configuration

Command: `uv run --project cli aiplatform validate --dir services/qwen-server`
(exit 0).

```text
Configuration validated
qwen-server · dev · model qwen2.5-0.5b-instruct (llamacpp)
cpu 2 · memory 1.0Gi · replicas 1-2
```

## Guardrail rejection

Command:

```bash
uv run --project cli aiplatform propose 'Add a NAT gateway' \
  --from-file examples/proposals/rejected-nat-gateway.json --dry-run
```

Exit 3 is the expected rejection, not a successful deployment:

```text
provider: file
terraform fmt clean
terraform validate infra/terraform/environments/dev
terraform plan skipped: no AWS credentials in the environment
Checkov: Passed checks: 84, Failed checks: 0, Skipped checks: 0
FAIL - infra/terraform/environments/dev/nat.tf - terraform -
aws_nat_gateway.nat: NAT gateways are not allowed
guardrails failed; no pull request opened
```

The extra Checkov check is against the proposed scratch tree, not the base
repository. This exercise used a JSON fixture, not a live model-generated
proposal. No AWS apply or pull request was executed.

## Runtime evidence still required

Docker was stopped during the audit. Capture one successful health check and
non-mock chat response before recording. Label its actual host and date; do
not use the September 16 benchmark results as proof of an October AWS launch.

Historical, command-backed measurements are in `docs/benchmarks/`.
