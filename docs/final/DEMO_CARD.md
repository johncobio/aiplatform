# Final demo card — Group 18

**One sentence:** A teammate describes a temporary preview in plain English;
a local model proposes a version and lifetime, and Terraform deploys the
reviewed plan to a restricted AWS preview.

For class, prepare the portal and issue an
[instant HTTPS invite](REMOTE_PREVIEW.md#instant-access-for-a-classmate)
before presenting. The guest opens the link and clicks **Compare versions**.
Version 1 accepts the invalid input; version 2 rejects it. The live demo
form runs in the already deployed Lambda, so no one waits for Terraform.
Use the [hosted rehearsal](../benchmarks/2026-11-12-remote-portal-smoke.md)
to show how a separately approved request produced and verified a real
EC2 preview. That rehearsal's resources were removed.

The local sequence below is a fallback if you cannot provision a new portal.

1. Show the browser request: “Let me test the updated sign-up form for a
   quarter hour.” Point to version 2 and 15 minutes. Submit as a tester and
   approve as operator. Label the browser's provisioning as a rehearsal.
2. Compare the same fake email on version 1 and version 2. This gives the
   preview a purpose: test a fix before releasing it.
3. Switch to the [operator runbook](PREVIEW_AWS.md). Explain that the model
   returns two fields; fixed Terraform code chooses the instance, network
   and allowed ingress. Show the three planned creates and the approval hash.
4. Show the [recorded live EC2 results](../benchmarks/2026-11-12-ohio-preview-smoke.md):
   version 2 reported ready, rejected the invalid email, and accepted the
   valid email. The tested endpoint was destroyed after verification.
5. Show the cleanup evidence from the same state. Say why one instance, one source IP,
   encrypted storage and automatic termination fit a short student demo.

**Evidence:** The model API accepted two requests
in 0.70 s and 0.68 s and rejected a request to open SSH in 0.62 s. These
are three warm local observations on one laptop, not a latency percentile.
One model-driven local Terraform lifecycle succeeded. A real model-led AWS
plan in Ohio showed three creates; the Terraform plan stage took 4.66 s.
The first live apply command reached version 2 readiness in 22.41 s.
The second reached readiness and passed both form checks in 22.32 s.
Destroy took 30.96 s and 28.16 s; AWS inventory confirmed removal both times.
These are two cloud smoke tests; there is no failure rate or throughput claim.

**Fallback:** Keep the deterministic browser demo available with
`make preview-demo`, and use the recorded plan, readiness and teardown
as infrastructure evidence. The EC2 path is single-instance and operator-only. Local Kubernetes
and observability work are separate portfolio evidence; they are not part of
this EC2 deployment.
