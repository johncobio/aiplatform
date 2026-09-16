# 0010 — AI-proposed infrastructure changes behind guardrails and a pull request

2026-09-16 · Accepted

## Context

The final platform feature is an agent that turns a natural-language request
("deploy this with high availability under $100/month") into infrastructure
changes. The non-negotiable is that the model never applies anything: every
proposal must pass the same validation a careful engineer would run, and a
human must approve it.

## Decision

`aiplatform propose "<request>"` implements the flow

    request → context → model proposal → scratch branch → guardrails → PR → human merge → Argo CD

- **Providers.** `ClaudeProvider` calls the Anthropic Messages API with a
  structured output schema (`Proposal`: summary, rationale, full-file
  changes, reviewer risks) using adaptive thinking; `FileProvider` reads the
  same JSON from disk. The provider only produces the proposal, so it can be
  swapped, faked in tests, or bypassed with a hand-written plan.
- **Context, bounded.** The model sees the catalog, ADR titles, workload
  configs, desired-state values, environment overlays, the dev Terraform root,
  policy limits and the price table, capped at 60 k characters.
- **Guardrails, in order** (each explicit about skipping when it does not
  apply): allowed-path check (only workload configs, desired state,
  environment values, chart values, Terraform; never CI, policies or
  secrets) → `aiplatform.yaml` validation → `terraform fmt` → `validate` →
  `plan` (only with AWS credentials and a bootstrapped backend) → Checkov →
  OPA/Conftest on Terraform (`policy/terraform`) → `helm lint`, render every
  workload and OPA/Conftest on the manifests (`policy/kubernetes`) → cost
  estimate against the budget (`policy/prices.yaml`, `policy/data/limits.yaml`).
- **Human approval is a pull request.** The validated branch is pushed and
  `gh pr create` opens a PR whose body is the guardrail report and cost
  table. Merge = approval; Argo CD reconciles merged desired state, and the
  AWS phase will run `plan` on PRs and `apply` on merge for Terraform.
- **`aiplatform guard`** runs the same checks on any working tree, and CI runs
  the policy suites on every push, so the rules bind humans and agents alike.

## Consequences

- The blast radius of a wrong proposal is a rejected PR. Policies are code in
  `policy/`, reviewed like everything else, and unit-tested by running them
  against known-bad inputs.
- Cost figures are estimates from a price table, printed with their inputs;
  they gate proposals but are not a bill. Infracost or the AWS Pricing API can
  replace the table later without changing the flow.
- No Anthropic credentials were available on the development laptop, so the
  Claude provider is exercised by unit tests with a fake client; the full
  pipeline (file provider → guardrails → PR) was run for real.
