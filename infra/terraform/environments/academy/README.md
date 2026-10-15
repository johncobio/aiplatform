# Academy midpoint demo

Isolated from dev/staging and any course lab stacks. Reads the existing
default VPC/subnets; creates one security group, two rules and one t3.small.
The root volume is 20 GiB encrypted gp2 and deleted on termination. No IAM,
SSH, S3, ECR, EKS, load balancer, NAT, key pair or snapshot is created.

The service image is the published amd64 manifest of `sha-bfc96a4`, pinned
by digest. Qwen 0.5B is pinned to an upstream revision and verified by SHA256.
The built-in service exposes inference and native Prometheus metrics, not the
full Kubernetes/observability stack. This is not an `aiplatform deploy` target.

## Cost and safety

- Estimated about $21/month before traffic if left up: compute ~$0.0208/h,
  public IPv4 $0.005/h, 20 GiB gp2 roughly $2/month. Not an enforced cap.
- Owner approved up to $2 of Academy lab credit on October 15, 2026.
- Standard CPU credits avoid unlimited-credit surcharges, but can throttle.
- Only the operator's public IPv4 /32 can reach TCP 8000. No SSH ingress.
- HTTP is suitable only for this restricted demo. Do not send private prompts.
- The host schedules shutdown after 120 minutes during bootstrap; EC2 is set
  to terminate on OS shutdown. Destroy still removes the security group/rules.
- If bootstrap fails before scheduling shutdown, manually terminate immediately.
- Do not change scope or leave running beyond the approved recording session.

## Plan and apply

Use the **AWS console's CloudShell**, not the external Academy browser
terminal (which used an unrelated runner identity during the audit).
CloudShell forwards the console's temporary credentials. Do not export them.

From a fresh checkout with Terraform 1.16.2 available:

```bash
export TF_VAR_operator_cidr='YOUR_LAPTOP_PUBLIC_IPV4/32'
# Keep large provider binaries out of CloudShell's 1 GiB persistent home.
export TF_DATA_DIR=$(mktemp -d)
make plan-academy
```

Supply your laptop's IP, not CloudShell's IP. Verify the saved plan has exactly
four creates: instance, security group, ingress rule and egress rule. It must
not replace or delete any existing lab resources. Review costs and obtain
human approval before:

```bash
terraform -chdir=infra/terraform/environments/academy apply academy.tfplan
terraform -chdir=infra/terraform/environments/academy output -raw endpoint
```

State, plan, operator IP and account identifiers stay in the private CloudShell
checkout. Never upload them or record a screen showing credentials. Keep this
checkout until destroy has completed. If moving machines, transfer state
privately first; do not run from an empty state and call it cleanup.

## Verify and teardown

From the permitted laptop, test `/readyz`, `/v1/models`, a real
`/v1/chat/completions` response and `/metrics`; see the midpoint walkthrough.
If startup stalls, read EC2 system console output (bootstrap logs are mirrored
there). No instance role or shell access is required by bootstrap.

In the **same checkout and credentials** used for apply:

```bash
make destroy-academy
terraform -chdir=infra/terraform/environments/academy state list
```

Review the destroy plan: it may only target this root's four resources. After
destroy, state list should be empty. Verify the instance is terminated, its
volume deleted and the project security group absent. Do not rely on End Lab
as a substitute for teardown. Recreate with a new plan if recording tomorrow.

## Local validation

`make check` includes three mocked Terraform plans and four OPA exception
tests. They prove the configuration's safety constraints, not cloud access or
model readiness. No real AWS calls are made by `make tf-test`.
