# Ohio preview: two live smoke tests

On November 12, 2026, the approved saved plan deployed version 2 for a
15-minute lease in `us-east-2`. A local Qwen request produced the spec;
the plan created one t3.small, one security group, and one ingress rule.
The encrypted 8 GiB boot volume was owned by the instance. The preview
accepted connections on port 8000 from the operator IP only.

| Observation | First run: readiness | Second run: readiness and form |
| --- | ---: | ---: |
| Read-only Terraform plan stage | 4.66 s | 3.60 s |
| Terraform apply stage | 17.60 s | 17.60 s |
| Readiness polling after reading Terraform output | 2.20 s | 2.19 s |
| Two synthetic form checks together | Not measured | 0.28 s |
| Operator apply command through all completed checks | 22.41 s | 22.32 s |
| Operator destroy command, including cleanup planning | 30.96 s | 28.16 s |

The operator ran `./scripts/previewctl --target academy apply --approve
<saved-plan-hash>`. The verifier accepted HTTP 200 with
`{"ready": true, "version": 2}`. A supplemental form test script failed
before sending either test input on the first run. In the second run, the
maintained verifier got HTTP 200 for both submissions and confirmed that
version 2 rejected `not-an-email` and accepted `student@example.com`.
The 0.28 seconds is the combined check duration for that one pair.

`./scripts/previewctl --target academy destroy` succeeded in both runs.
After each one, AWS EC2 inventory showed no active preview instance,
matching preview security group, or known preview EBS volume. Terraform
state contained no resources, and there was no pending apply. The URL,
source IP, and resource identifiers are omitted. These are smoke-test
observations, not a latency distribution, an availability claim, or a bill.
