# 0014 — Separate the preview portal from the Terraform operator

**Status:** Local lifecycle and Ohio deployment, readiness, and cleanup verified.

Use a fixed Terraform root per target. An exact saved plan, identified by
SHA256, is the input to apply after operator review. Keep Terraform, ambient
AWS credentials, and state outside the browser process. Lock the workspace
against overlapping operator commands and keep a separate, private state for
each target. This is a single-operator architecture; it is not a distributed
job service or approval audit system.

The local target uses Terraform's built-in provider for rehearsal. The
Academy target (historical name) reuses the Ohio project's default VPC
and a default subnet, with one
previously allowlisted t3.small, an encrypted 8 GiB gp2 volume (the Academy
configuration in ADR 0012), IMDSv2, and
operator-only TCP 8000. It runs a dependency-free sample using the system
Python included in [Amazon Linux 2023](https://docs.aws.amazon.com/linux/al2023/ug/python.html).
The instance has no role, SSH, package downloads, or outbound security group
rules. This keeps startup independent of public image and model downloads.

Health verification checks the actual endpoint and requested version.
Terraform is the primary cleanup path; boot-time self-termination is a
backstop. The preview runs plaintext HTTP for synthetic inputs on the
restricted demo network. Hosting for independent users would require a
different trust boundary, TLS, authorization, and durable jobs and state.
