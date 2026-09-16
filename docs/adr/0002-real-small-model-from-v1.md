# 0002 — Serve a real (tiny) model from V1 with pluggable backends

2026-09-16 · Accepted

## Context

The project must demonstrate operating AI infrastructure, not calling an API.
The development machine is an 8 GB Apple Silicon laptop; vLLM needs Linux and
ideally a GPU, so it cannot be the local backend.

## Decision

`llm-service` exposes an OpenAI-compatible API over a `Backend` interface:

- `mock` — deterministic, no weights; used in tests and CI.
- `llamacpp` — llama-cpp-python on CPU with a GGUF model. Default:
  Qwen2.5-0.5B-Instruct Q4_K_M (≈ 400 MB), which fits in the Docker VM.
- `vllm` (V6) — same HTTP contract on GPU nodes in EKS.

Model selection is driven by a **model catalog** in the CLI that maps a model
name to its artifact and minimum memory, so validation can fail fast.

## Consequences

- AI-specific metrics (tokens/sec, model load time, queue depth) are real from
  the first deploy, and dashboards built in V4 keep working through V6.
- The Docker image compiles llama.cpp for linux/arm64 at build time (a few
  minutes). Mitigated with a multi-stage build and layer caching.
- `llama-3.1-8b` from the brief is in the catalog but marked as requiring
  ≥ 16 GiB (CPU) or a GPU; validation rejects it on the local target.
