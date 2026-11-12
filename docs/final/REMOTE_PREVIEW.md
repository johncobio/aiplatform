# Remote self-service rehearsal

One guest uses a browser on a different computer. The operator owns AWS
credentials, the exact-plan approval, and cleanup. The guest never
installs tooling or types in credentials.

The [hosted AWS rehearsal](../benchmarks/2026-11-12-remote-portal-smoke.md)
passed from an automated guest client, and both stacks were removed after
the run. Deploy the portal before issuing a new invite. A separate browser
rehearsal from the tester's actual network is recommended.

## Portal infrastructure (Ohio)

After cost approval, deploy the reviewed portal plan using the same
checkout where it was prepared. Keep the plan, Lambda zip and state
private. Verify the SHA256 of **both** saved files immediately before
apply; Terraform reads the zip from disk at apply time.

```bash
export AWS_PROFILE=aiinfra
export TF_VAR_expected_account_id="$(aws sts get-caller-identity --region us-east-2 --query Account --output text)"
terraform -chdir=infra/terraform/environments/preview-portal init -input=false
terraform -chdir=infra/terraform/environments/preview-portal plan -input=false -out=.terraform/portal.tfplan
shasum -a 256 infra/terraform/environments/preview-portal/.terraform/{portal.tfplan,portal.zip}
# Stop and review the plan and cost before applying the matching files.
terraform -chdir=infra/terraform/environments/preview-portal apply -input=false .terraform/portal.tfplan
PORTAL_URL="$(terraform -chdir=infra/terraform/environments/preview-portal output -raw portal_url)"
./scripts/remote-preview probe "$PORTAL_URL"
```

The probe checks the HTML, JavaScript, and unauthenticated API denial
over HTTPS before issuing an invite. It retries temporary network and
gateway errors and reports the route if it fails.
The only public surface is the invite landing page and guest API. The
Lambda role has no infrastructure permissions. A guest with the bearer
link can submit one request, and only from a network with usable public
IPv4. Keep the invite private; only its hash is retained. The invite
accepts submissions for 30 minutes and its status is retained for up to
two hours before the app stops serving it. DynamoDB deletes expired rows
asynchronously.

## Demo

### Instant access for a classmate

Run this once per guest shortly before class, after deploying and probing
the portal:

```bash
./scripts/remote-preview invite "$PORTAL_URL" --instant
```

Give the guest only the HTTPS link. They open it and click **Compare
versions**; no deployment request or operator approval is needed during
the demo. The invite must be opened within 30 minutes of issue, and the
guest gets 15 minutes from first opening it. Use a separate invite for
each guest and keep the same network during the session.

This is the real form running in the already deployed Lambda. It shows
the version 1 bug and the version 2 fix; it does not launch a new EC2
instance. Use the saved [Ohio evidence](../benchmarks/2026-11-12-remote-portal-smoke.md)
when explaining the separate infrastructure workflow.

### Full Terraform workflow, when needed

1. Operator: run `./scripts/remote-preview invite "$PORTAL_URL"`. Give the
   tester only the HTTPS invite link. Keep the receipt in your terminal.
2. Tester: open the invite and click **Send request**. The default is
   “Deploy version 2 for 15 minutes.” No IP sharing is needed; the gateway
   records the source IPv4. Stay on that network.
3. Operator: run `./scripts/remote-preview inspect "$RECEIPT"`, then
   `./scripts/remote-preview plan "$RECEIPT"`. Review version, lifetime,
   and the three planned creates. If you have the local model on your
   operator host, append `--model-intent` to interpret a paraphrase.
4. Operator: after approving the EC2 cost, run
   `./scripts/remote-preview apply "$RECEIPT" --approve "$PLAN_SHA"`.
   The guest watches the status change and receives the actual EC2 URL
   when Terraform issues it. The page does not claim health verification
   from an operator network that cannot reach the guest-only endpoint.
5. Tester: open **Open AWS preview**. Submit `not-an-email`, then
   `student@example.com`. Version 2 should reject the first and accept the
   second. Only use synthetic inputs; the preview uses HTTP.
6. Operator: from the same checkout run
   `./scripts/remote-preview destroy "$RECEIPT"`. It destroys the EC2
   preview from the same state and closes the portal request. Confirm the
   AWS inventory is empty. After the demo, `make destroy-preview-portal`
   removes the HTTPS portal and its table, role and log groups.

The operator can use CloudShell with the private checkout, `uv`, Terraform
and AWS CLI installed; omit the named profile export if using CloudShell's
ambient credentials. Both planning and applying must use the same operator
workspace. The default phrase does not require Ollama or a personal laptop.
The browser requester cannot apply, and does not need access to CloudShell.

If an apply is interrupted, preserve
`.aiplatform/remote-preview-runner/academy/` and retry destroy with the
same receipt. If the record has already been deleted by DynamoDB TTL, use
the existing workspace directly for recovery:

```bash
./scripts/remote-preview destroy "$RECEIPT" --without-portal
```

Verify there are no leftovers before starting another preview.
Portal destroy alone does not
clean up a separately provisioned EC2 preview.

## Expected demo costs

For a class rehearsal of about 1,000 HTTPS requests, estimate **under
$0.10/month for the portal at that usage level** before credits, including
small logs and table usage. This is an estimate, not a spending cap. The
EC2 preview is separately about **$0.007 per 15 minutes** at on-demand
rates, before credits and excluding tax and transfer. Tear both down
after testing. See [API Gateway pricing](https://aws.amazon.com/api-gateway/pricing/),
[Lambda pricing](https://aws.amazon.com/lambda/pricing/), and
[DynamoDB pricing](https://aws.amazon.com/dynamodb/pricing/).
