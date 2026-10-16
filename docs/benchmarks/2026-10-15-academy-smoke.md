# Academy EC2 inference smoke test

Observed October 15, 2026 in America/Chicago; response timestamp
**2026-10-16 01:15:18 UTC**. This is one successful request, not a load test,
percentile, throughput capacity estimate, or availability measurement.

## Deployment

- Commit: `ed73116`; Terraform 1.16.2, AWS provider 6.69.1.
- Authenticated CloudShell, private local state, reviewed saved plan.
- Terraform reported **4 added, 0 changed, 0 destroyed**.
- Existing Academy VPC/subnet/route/IGW; one t3.small with standard CPU credits.
- Encrypted 20 GiB gp2 root, delete-on-termination. No SSH, key or instance role.
- TCP 8000 ingress restricted to the operator's public IPv4 /32.
- Built-in service: amd64 image pinned by digest in the Academy bootstrap.
- Qwen2.5-0.5B-Instruct Q4_K_M pinned by revision and verified by SHA256.
- Docker limits: 2 CPUs, 1 GiB memory. Automatic host termination after two hours.
- Boot console confirmed model readiness at 01:13:55 UTC, at a boot-log offset
  of about 240 seconds. Shutdown is scheduled for 03:10:03 UTC October 16.
- GitHub CI passed: https://github.com/johncobio/aiplatform/actions/runs/38822074273

The endpoint is temporary and IP-restricted. Get its current address from
`terraform output -raw endpoint` in the original CloudShell checkout; do not
reuse an old public IP after teardown.

## Commands

From the permitted laptop, with `DEMO_ENDPOINT` set to that verified endpoint:

```bash
curl --fail --max-time 10 "$DEMO_ENDPOINT/readyz"
curl --fail --max-time 10 "$DEMO_ENDPOINT/v1/models"
curl --fail --max-time 120 "$DEMO_ENDPOINT/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Explain GitOps in one sentence."}],"max_tokens":64,"temperature":0.2}'
curl --fail --max-time 10 "$DEMO_ENDPOINT/metrics"
```

The recorded client elapsed time used Python `time.perf_counter()` around
`urllib.request.urlopen()` and JSON response reading. The same public request
body appears above. `/readyz` and `/v1/models` both returned HTTP 200.

## Actual response

HTTP 200, finish reason `stop`, model `qwen2.5-0.5b-instruct`:

> GitOps is a modern approach to infrastructure management that leverages Git for version control and Kubernetes for orchestration, enabling organizations to manage their infrastructure more efficiently and transparently.

Usage: 37 prompt tokens, 34 completion tokens, 71 total. Client elapsed:
**2.304 seconds**. This generated text demonstrates serving, not authoritative
technical advice; GitOps is not limited to Kubernetes.

## Observed metrics after the request

```text
process_resident_memory_bytes 7.07035136e+08
llm_requests_total{status="ok"} 1.0
llm_request_duration_seconds_count 1.0
llm_request_duration_seconds_sum 2.219115209999984
llm_prompt_tokens_total 37.0
llm_completion_tokens_total 34.0
llm_inflight_requests 0.0
llm_queue_depth 0.0
llm_model_load_seconds 7.657020695
llm_model_info{backend="LlamaCppBackend",model="qwen2.5-0.5b-instruct"} 1.0
llm_generation_tokens_per_second_count 1.0
llm_generation_tokens_per_second_sum 15.322365225281125
```

The tokens/s histogram has one observation, so its sum here is that request's
observed generation rate. Do not confuse it with sustained serving capacity.
RSS is the process snapshot, not the whole EC2 instance's memory utilization.
The model-load timer excludes package installation, downloads and extraction.

## Challenges and remaining verification

Cold bootstrap took several minutes. EC2 console output showed successful
model verification and image downloads/extraction; a CloudWatch CPU-credit
sample was zero while the standard-credit instance bootstrapped. No credit
mode, instance-size or network-permission change was needed for this test.
No end-to-end cold-deploy duration was instrumented, so none is claimed.

Cloud Prometheus/Grafana, Kubernetes, GitOps, GPU serving, P95 load testing and
cloud recovery tests remain separate milestones. Estimated cost is not a
billing measurement. The owner must record the demo before session expiry or
recreate it from a new plan. Teardown verification remains pending until the
recording is finished; use the original state and `make destroy-academy`.
A private destroy plan was prepared and reviewed (0 creates, 0 changes,
4 destroys), but not applied while the service is needed for recording.
