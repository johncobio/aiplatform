# 0001 — Python for the CLI and the sample service

2026-09-16 · Accepted

## Context

The platform needs a CLI (`aiplatform`) and a sample AI workload. Go is common
for platform CLIs; Python is common for AI serving. One developer maintains
both.

## Decision

Use Python 3.12+ for both, managed with `uv`. CLI: Typer + Pydantic + Rich.
Service: FastAPI + Pydantic + prometheus-client. External tools (`docker`,
`terraform`, `kubectl`, `helm`) are invoked via `subprocess`, not SDKs.

## Consequences

- One toolchain, one linter, one test runner across the repo.
- The CLI is distributed as a Python package rather than a static binary;
  acceptable for an internal platform tool.
- Wrapping the real CLIs keeps behaviour identical to what an engineer would
  run by hand, which makes the pipeline easy to debug and teaches the tools.
