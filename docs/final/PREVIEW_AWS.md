# Preview Terraform runner and AWS handoff

The browser demo is a separate simulation. This operator command runs real
Terraform. It takes the same constrained sentence, accepts only versions
1 and 2 for 15 or 30 minutes, and maps those two fields to a fixed root.
By default it uses an example parser. With `--model-intent` the local
Qwen model proposes a version and lifetime; the command validates those
fields and still maps them to the same fixed root. It never accepts
generated Terraform.

## Rehearse the operator workflow without AWS

From the repository root, with Terraform 1.10+ and `uv` installed:

```bash
./scripts/previewctl plan "Deploy version 2 for 15 minutes."
./scripts/previewctl apply --approve <SHA256-from-plan>
./scripts/previewctl verify
./scripts/previewctl destroy
```

Replace the placeholder with the actual hash. Review the actions before
copying it. Terraform creates only an in-state `terraform_data` record.
An altered plan or incorrect approval is rejected before apply; an occupied
slot must be destroyed before a new plan. This path creates no endpoint.

## First session in a standard AWS account: read-only

1. Sign in to the intended AWS project and select **Ohio
   (us-east-2)**. The `academy` target name is historical; this Terraform
   root uses standard AWS services and does not require a Learner Lab.
2. Authenticate the operator terminal with a non-root identity and
   [short-lived credentials](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-authentication.html).
   Keep credentials out of chat, shell history, recordings and the
   repository. Use an identity with read permissions for the first plan.
3. Check the identity privately with
   `aws sts get-caller-identity --query Account --output text`. The plan
   must also find an existing default VPC, a default subnet and the public
   AL2023 AMI parameter. Missing permissions or a missing default VPC
   are reasons to stop before apply.
4. Set `DEPLOY_ACCOUNT_ID` to the verified account and `OPERATOR_CIDR` to the
   demo laptop's current public IPv4 with `/32`. Run the read-only plan:

```bash
./scripts/previewctl --target academy plan "Deploy version 2 for 15 minutes." \
  --account-id "$DEPLOY_ACCOUNT_ID" --operator-cidr "$OPERATOR_CIDR"
```

For the model-led demo, add `--model-intent` to the plan command and use
“Let me test the updated sign-up form for a quarter hour.” Check that the
summary reports version 2 and 15 minutes before approving the saved hash.

Expect exactly one EC2 instance, one security group, and one TCP 8000
ingress rule. The root reuses the account's default networking and does not create a VPC,
NAT gateway, load balancer, IAM role, or image registry. Account ID binding
prevents a later command from using credentials for a different account.

## After explicit cost approval

Run the following only once the live plan has been reviewed and the cost
approved. The command applies the exact saved plan, polls `/readyz`
for the requested version, then tests both synthetic form inputs. The terminal logs timestamp each Terraform
stage and report apply and readiness durations separately. The HTTP
endpoint is limited to the operator's IP; use the demo laptop and synthetic
inputs.

```bash
./scripts/previewctl --target academy apply --approve <SHA256-from-plan>
./scripts/previewctl --target academy verify
make destroy-preview-aws
```

If Terraform runs from CloudShell, add `--skip-verify` to the apply
command. CloudShell is outside the laptop's allowed IP range. From the
laptop, open the returned endpoint and check
`curl --fail --max-time 5 "$PREVIEW_ENDPOINT/readyz"`; the result must
show `{"ready": true, "version": 2}` for the example. Keep Terraform state
and cleanup in the same operator workspace where apply ran.

If apply or verification fails, preserve
`.aiplatform/preview-terraform/academy/` and use the same AWS account to
destroy before retrying. Do not discard the state or try a different account.
Check EC2 system console output for boot errors and compare the current
public IP with the approved CIDR. If Terraform lost state after an
interruption, have the operator check the intended account's EC2, EBS and security
groups for resources belonging to this preview before relaunching. The
runner will refuse to claim cleanup when `apply.pending` exists without
managed state. Only remove that marker after verifying the account has no
leftover preview resources; reconcile any orphans before restarting.
Verify teardown in AWS as well as in Terraform state. Instance shutdown
is scheduled with a persistent systemd timer as a backstop; it does not
delete the security group, and it cannot help if the boot script never runs.

Estimated Ohio on-demand cost before any credits: **$0.02690/hour**
or **$19.63 for 730 hours**, for one t3.small, one public
IPv4 and 8 GiB gp2. This excludes tax and traffic. Sources:
[EC2](https://aws.amazon.com/ec2/instance-types/t3/),
[public IPv4](https://aws.amazon.com/vpc/pricing/),
[EBS](https://aws.amazon.com/ebs/general-purpose/).
The [Ohio smoke tests](../benchmarks/2026-11-12-ohio-preview-smoke.md)
verified readiness twice. The second apply command reached readiness and
passed both form submissions in 22.32 seconds. Its destroy command took
28.16 seconds. AWS inventory confirmed cleanup after both runs.

## Acceptance evidence

| Check | Evidence |
| --- | --- |
| Approved local plan, apply, verification and cleanup | Three CLI cycles; final Terraform state had no managed resources. |
| Wrong or changed saved plan, simultaneous commands, health failure | Automated preview tests in `make check`. |
| Network, version and lifetime restrictions | Mocked Academy plan tests plus OPA and Checkov. |
| Sample version behavior and health response | Both versions tested over loopback with the same invalid email. |
| Real AWS plan, boot, endpoint and teardown | Two approved runs reached version 2 readiness in Ohio; AWS inventory confirmed removal after each. |
| Form POST behavior in AWS | The second run verified that version 2 rejects a synthetic invalid email and accepts a synthetic valid one. |
| Live model interpretation | Two accepted requests and an unsupported request rejected through the preview API; one model-driven local Terraform lifecycle and one live AWS plan. |
| Tester experience and hosted multi-user access | Browser simulation available; independent browser rehearsal and remote access pending. |

## Boundaries

One slot, one region, one instance, one source IP, one local operator and
local state. The single instance demonstrates deterministic provisioning
and network isolation; it does not demonstrate cloud high availability,
autoscaling or multi-user hosted access. The browser currently demonstrates
the UX; it is not connected to this operator command. Both can use the
same local model adapter. A hosted, authenticated control plane is separate work.
