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
**The Kubernetes prototype has run locally. AWS Terraform exists, but no AWS
deployment has been verified in this midpoint audit.** The Academy Sandbox
instructions allow t2/t3 instances through medium size, gp2 disks up to 35 GB,
and read-only IAM. EKS/ECR are not listed as supported services. The proposed
midpoint cloud footprint is therefore one EC2 inference host with a restricted
security group and encrypted EBS. EKS remains a later deployment option.

## Verification and progress

Fresh verification on October 15: `make check` passed **112 CLI tests and 14
service tests**, formatting/lint, six Terraform roots/modules, chart engine
checks, and both Conftest suites. The audit reproduced an earlier remote CI
failure, Checkov CKV_AWS_394, because availability-zone discovery was unfiltered.
The repair pins zone identities; all seven jobs passed on `111610a`
([CI evidence](https://github.com/johncobio/aiplatform/actions/runs/38820810497)).
The local Checkov scan passed 83 checks. Validation alone does not prove a cloud
deployment. See [fresh output excerpts](VALIDATION_EVIDENCE.md).

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

**Before midpoint submission:** verify permitted cloud access, deploy a small
EC2 host if authorised, record an actual API response and teardown procedure,
finalise the group-number filename, rehearse the talk, and submit the video URL.
The local inference demo is the fallback if the lab blocks cloud deployment.

**After feedback, before final submission:** validate a saved Terraform plan
and deployment in the chosen AWS account; complete cloud authentication and
image promotion; add TLS/authentication before wider exposure; evaluate
multi-node model storage; validate EKS/GPU feasibility and cost; add external
uptime probes; review proposal execution and cost checks before enabling a live
provider; repeat load and recovery measurements in the cloud. The final due
date is not yet known, so these are ordered milestones rather than invented dates.

Feedback requested: Is a small EC2 cloud deployment sufficient for the next
milestone? Which final requirement should take priority: EKS, cloud automation,
or reliability measurements?
