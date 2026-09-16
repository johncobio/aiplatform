# V7 proposal guardrails — 2026-09-16

**Setup:** `aiplatform propose --from-file` (no Anthropic credentials on the
laptop; the Claude provider is unit-tested with a fake client). Scratch
worktrees from `main`, tools: terraform 1.16, Checkov via `uvx`, Conftest
0.70 (13 OPA rules), helm 4.3, `gh` for the pull request.

## Runs

| Proposal | Outcome | Where it stopped | Wall time |
|----------|---------|------------------|-----------|
| HA `document-agent` (new `aiplatform.yaml`, 2–3 replicas, upstream engine) | ✅ PR opened: https://github.com/johncobio/aiplatform/pull/1 | all applicable checks passed; cost $42.92 of $100 | 5 s (9 steps + PR) |
| Same proposal, first attempt | ❌ rejected | Kubernetes OPA: init container `fetch-model` had no CPU request / memory limit — a real defect in the platform's own chart, fixed in `9c5d2e2` | 4 s |
| GPU `g5.xlarge` instance + NAT gateway in `dev` | ❌ rejected | Checkov: 4 findings (IMDSv1, EBS unencrypted/unoptimised, no IAM role) | 40 s (terraform init + validate + Checkov) |
| NAT gateway only (Checkov-clean) | ❌ rejected | OPA `terraform` package: "NAT gateways are not allowed (ADR 0003)" | 35 s |

## What the pipeline checks (in order)

1. Allowed paths (workload configs, desired state, environment values, chart values, Terraform; never CI, policies, secrets)
2. `aiplatform.yaml` schema + catalog validation
3. `terraform fmt` · 4. `terraform validate` · 5. `terraform plan` (skipped: no AWS credentials)
6. Checkov (`.checkov.yaml`, 83 checks on the current Terraform)
7. OPA/Conftest on Terraform (308 assertions across the repo's `.tf` files)
8. `helm lint` + render of every workload + OPA/Conftest on manifests (80 assertions per render)
9. Cost estimate from `policy/prices.yaml` against the budget, printed with its inputs

Steps that do not apply are reported as *skipped* with a reason, so a
reviewer sees what was and was not checked.

## Observations

- **Layered checks catch different things.** Checkov flagged instance
  hygiene; OPA carried the platform's own architectural rule (no NAT
  gateways); the Kubernetes policy found a gap in a chart I wrote and had
  already deployed. None of the three would have caught all of it.
- **The scratch-branch design matters.** Checks run on `main` plus the
  proposal, so uncommitted local work cannot leak into a validation (the
  first run "failed" for exactly this reason: the policies were not on
  `main` yet).
- **The PR is the audit trail.** Request, rationale, files, every guardrail
  result, and the cost table live in the PR body; merge is the approval, and
  Argo CD reconciles the merged desired state.
