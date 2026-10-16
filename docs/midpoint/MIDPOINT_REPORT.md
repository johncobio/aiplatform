# Midpoint report: aiplatform

**Author:** John Cobio

**Review date:** October 15, 2026

**Repository:** https://github.com/johncobio/aiplatform

## Problem and proposed solution

Deploying an open-source language model requires more than an API endpoint.
Developers must select an inference engine, supply model storage, allocate
resources, configure networking, monitor demand, and recover from failures.
Manual setup makes deployments difficult to reproduce and expensive to debug.

aiplatform provides a configuration file and a CLI that validate a model's
resource requirements and deploy the workload through a repeatable pipeline.
The prototype supports local Docker, Kubernetes on kind, and GitOps through
Argo CD. It actually operates open-source model inference. Its optional proposal
agent is a separate feature for suggesting configuration changes.

## Current implementation and architecture

The CLI validates `aiplatform.yaml` with Pydantic and a model catalog. For a
built-in workload it builds an image. For an upstream engine it uses a pinned
image. Helm renders deployments, services, ingress, probes, model-cache PVCs,
and an HPA. The GitOps target writes desired-state values to Git for Argo CD.

GitHub Actions runs Python tests, Terraform validation, chart checks and policy
tests. A separate workflow publishes amd64/arm64 inference images to GHCR and
scans published images. Prometheus recording rules normalise engine metrics,
Grafana displays inference and resource signals, and the built-in service
exports OpenTelemetry traces to a collector and Jaeger. Policies and example
proposals demonstrate a review gate before infrastructure changes.

See [architecture.mmd](architecture.mmd) and the presentation for diagrams.
**Kubernetes has run locally; a real EC2 inference request is now verified.**
The Academy Sandbox
instructions allow t2/t3 instances through medium size, gp2 disks up to 35 GB,
and read-only IAM. EKS/ECR are not listed as supported services. The verified
midpoint cloud footprint is one t3.small inference host with a restricted
security group and encrypted 20 GiB gp2 root. A saved Terraform plan created
four resources without changing existing lab resources. The host needs no
instance role or SSH. EKS remains a later deployment option.

## Verification and progress

Fresh verification on October 15: `make check` passed **112 CLI tests and 14
service tests**, formatting/lint, seven Terraform roots/modules, chart engine
checks, and both Conftest suites. The audit reproduced an earlier remote CI
failure, Checkov CKV_AWS_394, because availability-zone discovery was unfiltered.
The repair pins zone identities. With the Academy root added, all seven CI
jobs passed on `ed73116`
([CI evidence](https://github.com/johncobio/aiplatform/actions/runs/38822074273)).
Checkov passed 102 checks with one documented role-free-host exception. Three
mocked Terraform plans and four OPA unit tests verify the Academy constraints.
See [fresh output excerpts](VALIDATION_EVIDENCE.md).

The cloud request at **2026-10-16 01:15:18 UTC** returned HTTP 200 with 34 output
tokens in 2.304 seconds of client-observed time. `/readyz`, `/v1/models`, model
identity and native Prometheus metrics were also verified. Model loading took
7.657 seconds, excluding downloads and container setup. This is a single smoke
test, not a percentile or capacity benchmark.
[Commands, actual response and metrics](../benchmarks/2026-10-15-academy-smoke.md).

Historical measurements on September 16, documented with configuration and
commands in `docs/benchmarks/`, include:

| Experiment | Observed result | Scope |
|---|---|---|
| Upstream llama.cpp, 1 virtual user | 1.511 requests/s, P95 0.80 s, 47.6 completion tokens/s | Qwen 0.5B on local kind, 2 CPU threads |
| Built-in inference, 1 virtual user | 0.524 requests/s, P95 2.17 s | Same model family and local resource budget, different serving build |
| Queue-based HPA | Scale decision after 60 s, second replica serving at 80 s | Single-node kind experiment |
| Pod deletion | Endpoint recovered in 12.5 s | Cached model, one replica |

These are recorded observations rather than production SLAs or AWS benchmarks.
The speed comparison does not isolate one cause: engine builds and serving
configuration differ. SLO definitions are targets, not demonstrated 30-day uptime.

## Challenges and lessons

- An 8 GB laptop cannot run every control-plane add-on and several models
  together reliably. Add-on pause/resume and a smaller demo footprint reduce risk.
- Extra replicas on one CPU-constrained node yielded little throughput gain.
  Horizontal scaling requires available compute capacity.
- The ingress-based SLI missed an ingress outage. External probes remain needed.
- IAM and service restrictions in Academy require a smaller cloud deployment.
- Model and image downloads can dominate setup. Pre-pull and rehearse before
  recording. Keep one known-working inference image available.

## Remaining work and execution plan

**Before midpoint submission:** record the verified EC2 demo, finalise the
group-number filename, rehearse the talk, share the video and submit. Destroy
the host and security group with the original CloudShell state afterward.
The host is scheduled to terminate at 03:10:03 UTC October 16; the security
group still needs explicit cleanup. Recreate only from a new approved plan if
recording later. No cloud teardown success is claimed yet.

**After feedback, before final submission:** extend the verified Terraform
deployment into cloud image promotion and the platform CLI; add
TLS/authentication before wider exposure; evaluate
multi-node model storage; validate EKS/GPU feasibility and cost; add external
uptime probes; review proposal execution and cost checks before enabling a live
provider; repeat load and recovery measurements in the cloud. The final due
date is not yet known, so these are ordered milestones rather than invented dates.

Feedback requested: Is a small EC2 cloud deployment sufficient for the next
milestone? Which final requirement should take priority: EKS, cloud automation,
or reliability measurements?
