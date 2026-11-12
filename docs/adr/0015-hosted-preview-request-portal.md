# 0015 — Host the request portal without exposing provisioning permissions

**Status:** Hosted request, preview verification, and cleanup validated in Ohio.
Future cloud deployments remain cost-gated.

Use API Gateway HTTP API for a managed HTTPS entry point and an on-demand
Python Lambda for the browser UI and request API. DynamoDB persists one row
per invite. Its conditional writes prevent concurrent resubmission and
out-of-order status changes. Use the Python SDK included in Lambda to avoid
vendoring an additional runtime; the operator continues to use AWS CLI and
the existing Terraform runner.

The browser uses a random invite fragment exchanged as a bearer header.
The table stores only its SHA256, and application expiry is enforced even
before asynchronous DynamoDB TTL deletion. A request is bound to API
Gateway's observed IPv4, not a user-supplied IP header. The public Lambda
paths cannot invoke operator actions. An operator with IAM permission
invokes the same function directly and applies the exact reviewed plan in
an isolated workspace. The Lambda execution role can only read and write
one table and emit its own logs; it has no EC2, IAM, or Terraform access.

Use bounded API and DynamoDB throughput, reserved Lambda concurrency,
encrypted storage, and seven-day CloudWatch logs with no bodies or bearer
tokens. Records are ephemeral; point-in-time restore, customer-managed
keys, a private VPC integration, a dead-letter queue for synchronous
requests, code signing, and tracing are outside this demo's scope. The
operator must close the EC2 preview before destroying the portal. The
existing preview expiry timer is a backstop.

The guest portal uses HTTPS. The returned sample app still uses HTTP
restricted to one guest IPv4 and fake inputs. The operator command remains
a supervised step; it can run from a cloud terminal. Its no-model mode
supports the exact sample sentence; optional Ollama interpretation needs
a model on the operator host. A managed model, a hosted operator UI,
and an HTTPS preview workload can be added separately.
