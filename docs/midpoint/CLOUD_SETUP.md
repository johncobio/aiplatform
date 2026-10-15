# Midpoint AWS setup decision and walkthrough

## Account choice

Use the existing Academy **Cloud Architecting 3 Sandbox**, found under
Modules → Sandbox → Sandbox environment. Do not repurpose the unrelated Café
lab stacks. The Sandbox instructions viewed October 15 allow t2/t3 through
medium, gp2 EBS up to 35 GB, and read-only IAM. They do not list ECR or EKS.
Confirm your own sandbox before applying anything; Academy course types differ.

A personal account is a fallback if the sandbox blocks the project. Eligible
new customers currently receive $100 initial credits and may earn up to $100
more. The Free plan ends after six months or credit exhaustion. A Paid plan
can charge beyond credits. Check the plan shown during signup:
https://docs.aws.amazon.com/us_en/awsaccountbilling/latest/aboutv2/free-tier-plans.html

## Smallest useful cloud milestone

One EC2 instance running a known image of the inference service, a public
subnet and route to the internet, a security group restricted to the operator's
IP, and encrypted EBS for Docker/model cache. Use an existing permitted
instance profile if available. No IAM creation in this sandbox. Use GHCR for
the image because ECR is not listed as supported. S3 state, EKS, a load balancer,
and GPU nodes are later milestones, not requirements for a real EC2 demo.

**Do not apply `environments/dev` unchanged in Academy:** it creates IAM,
selects Graviton, and uses gp3. Those conflict with the inspected lab's limits.

## Cost gate

Estimate before credits in us-east-1, assuming ordinary Linux on-demand rates:

| Item | Planning allowance |
|---|---|
| t3.small compute | about $0.021/hour |
| Public IPv4 | $0.005/hour |
| 20 GB gp2 EBS | about $2/month, verify regional price |
| t3.small total if left up for 730 hours | about $21/month before traffic |
| t3.medium alternative | about $36/month including IPv4 and disk |

Allow up to $2 of lab credit for the recording session. This is a planning
allowance, not an enforced billing cap. Use standard CPU credits for a demo
instance if supported to avoid unlimited-credit surcharges. Stop/destroy after
evidence collection. An EKS control plane alone is $0.10/hour under standard
support, before workers. Prices and lab credit accounting need confirmation.

Sources: https://aws.amazon.com/vpc/pricing/ and https://aws.amazon.com/eks/pricing/

## Next actions

1. Start Sandbox and wait for the green AWS indicator. Open the console from
   this sandbox rather than reusing a console authenticated to a Café lab.
2. Inspect the session duration, region, permitted services, and IAM instance
   profiles. Check whether resources persist after End Lab before relying on
   them for tomorrow's recording.
3. Authenticate through the lab terminal or a named temporary local profile.
   Keep the session token with the credentials. Never paste keys into chat,
   screenshots, source files, or commit history.
   The October 15 terminal probe resolved to an external runner role and denied
   IAM listing, so do not assume it has sandbox credentials. The federated
   browser console is working; verify CLI identity privately before any apply.
4. Prepare a lab-compatible Terraform configuration, validate it, inspect the
   actual plan, and approve the exact resources/cost before applying.
5. Launch the host using an image already published for its CPU architecture.
   Verify health and a non-mock chat completion; save the actual response and
   deployment evidence with a timestamp. No local model compilation is needed.
6. Update the presentation's cloud status only after that verification.
7. Record the demo, destroy the resources with the same state and inputs, and
   confirm EC2/storage cleanup. Keep state private until cleanup is complete.

The cloud milestone is **pending**, not yet an observed deployment.
