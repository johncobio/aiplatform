# V1 local baseline — 2026-09-16

**Hardware:** Apple Silicon laptop, 8 GB RAM, 6 cores; Docker Desktop VM with
4 GB RAM. Container limited to `--cpus 2 --memory 2Gi` by `aiplatform.yaml`.
**Model:** Qwen2.5-0.5B-Instruct, GGUF Q4_K_M (491 MB), llama.cpp CPU backend,
portable build (`GGML_NATIVE=OFF`), 2 threads, context 4096.
**Image:** `aiplatform/llm-service:20260916-125321`, linux/arm64.

## Deployment pipeline

Commands: `aiplatform -v deploy --dir services/llm-service` (cold), then
`aiplatform deploy` (warm), `aiplatform rollback`.

| Measurement | Value | Notes |
|-------------|-------|-------|
| Cold deploy, total | 242.1 s | includes llama.cpp compile and model download |
| `docker build` (cold, no cache) | 218.0 s | dominated by compiling llama-cpp-python |
| First readiness (download 491 MB + load) | 20.2 s | `Health checks passed` step |
| Model load from cache | 0.73 s | `llm_model_load_seconds` after rollback |
| Warm redeploy, total | 5.9 s | cached layers, cached model |
| Rollback, total | ~4 s | no build; previous image re-run |
| Image size | 450 MB | `docker image ls` |
| Resident memory, model loaded, idle | 647 MiB | `docker stats` |

## Inference (single request, no concurrency)

Command:

```
curl -s localhost:8000/v1/chat/completions -H 'content-type: application/json' \
  -d '{"messages":[{"role":"user","content":"Explain GitOps in one sentence."}],"max_tokens":64,"temperature":0.2}'
```

| Measurement | Value |
|-------------|-------|
| Request 1: 37 prompt + 28 completion tokens, wall time | 3.40 s |
| Request 2: 24 prompt + 48 completion tokens | finish_reason=length |
| `llm_request_duration_seconds_sum / count` (2 requests) | 3.96 s avg |
| `llm_generation_tokens_per_second` mean (2 requests) | 9.4 tok/s |

Raw metrics scrape after the two requests:

```
llm_requests_total{status="ok"} 2.0
llm_request_duration_seconds_sum 7.913
llm_prompt_tokens_total 61.0
llm_completion_tokens_total 76.0
llm_generation_tokens_per_second_sum 18.87  (count 2)
llm_model_load_seconds 20.95
llm_queue_depth 0.0
```

## Takeaways

- Build time is the bottleneck of the developer loop; CI (V3) should cache the
  compiled wheel layer or publish a base image.
- Single-request throughput on 2 CPU threads is ~9 tok/s: usable for a demo,
  far from production. This is the baseline V5 load tests and V6 vLLM will be
  compared against.
