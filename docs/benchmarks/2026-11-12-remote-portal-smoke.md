# Remote preview portal: hosted rehearsal

## Successful retry

The second run exercised the public Ohio HTTPS endpoint with an automated
guest client. The landing page and script loaded, unauthenticated API
access was denied, and one invite accepted one submission while rejecting
a duplicate. The operator saved and approved a three-create Terraform
plan. The guest API returned the resulting AWS endpoint only after apply.

The live version 2 workload reported ready, rejected `not-an-email`,
and accepted `student@example.com`. Destroy closed the guest request and
removed the endpoint from its status. AWS inventory and both Terraform
states confirmed cleanup of the preview and portal.

| Observation | Duration |
| --- | ---: |
| Portal Terraform apply | 21.25 s |
| HTTPS probe, including assets and authentication boundary | 10.17 s |
| Preview apply command through readiness and form checks | 23.10 s |
| Preview destroy and request close | 29.77 s |
| Portal destroy, including cleanup planning | 21.37 s |

The guest and operator were exercised by separate interfaces from the same
test machine. An independent browser rehearsal from another network is
still pending. See the [remote runbook](../final/REMOTE_PREVIEW.md) for
the commands. No active endpoints or private invite data are recorded.

## First attempt

The reviewed Ohio Terraform plan created the HTTP API, Lambda function,
DynamoDB table, role and log groups. Terraform apply completed in
**21.80 seconds**. The HTTPS smoke client then hit a socket read timeout
before completing the invite workflow. That client failed to retry this
exception, so the run does not establish why the HTTPS response was slow.
No guest preview or EC2 instance was created.

Portal destroy completed in **20.17 seconds**, including cleanup planning.
Terraform state and AWS inventory confirmed removal of the API, Lambda,
table, role and log groups, with no active preview instance or security
group. There is no active endpoint to reuse.

After teardown, the public static routes were decoupled from DynamoDB
client initialization and a retrying probe was added. Tests cover a raw
read timeout followed by a 503 and successful responses. The retry above
used `./scripts/remote-preview probe "$PORTAL_URL"` before creating an invite.
