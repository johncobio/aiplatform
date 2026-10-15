# ADR 0012: Restricted EC2 midpoint demo in Academy

Date: 2026-10-15. Status: accepted for the approved midpoint demo.

## Context

The owner has an Academy Cloud Architecting sandbox and a midpoint deadline.
Its permitted instances are t2/t3, disks are gp2, and IAM is read-only. The
existing Graviton/ECR/SSM module cannot run unchanged. EKS is not listed as
supported. The owner approved up to $2 of lab credit for a small EC2 demo.

## Decision

Add an isolated `environments/academy` root using existing default networking,
one t3.small, encrypted 20 GiB gp2, standard CPU credits and a /32-restricted
API port. Use no IAM role and no SSH: bootstrap needs only public downloads,
and mirrors logs to the system console. Pin the existing built-in service
image by amd64 digest and the model by revision and SHA256.

Keep local state in authenticated CloudShell rather than creating S3 or
exporting credentials. Save and review a plan before apply. Schedule host
shutdown after two hours and configure terminate-on-shutdown, then explicitly
destroy security rules/group using the same state. Estimated continuous cost
is about $21/month before traffic; the $2 allowance is not a billing cap.

The OPA exception admits only `aws_instance.academy_demo` of type t3.small
tagged Environment=academy and Project=aiplatform. Tests keep t3.medium, other
environments and other names denied. No global x86 allowlist expansion.

## Alternatives and consequences

- EKS is deferred: service availability, IAM and control-plane cost conflict
  with this deadline and sandbox. A personal account is unnecessary for this
  first milestone if the EC2 plan succeeds.
- A manual console-only launch is faster initially but loses reproducible
  state/teardown. A dedicated root preserves those engineering properties.
- Rewriting the existing EC2 module would broaden its interface and risk the
  validated dev/staging path. This small, constrained root stays independent.
- The demo is single-instance HTTP, not HA, authenticated or production-ready.
  It does not claim an integrated AWS CLI target or cloud GitOps deployment.
