# 0013 — Rehearse a temporary preview before integrating AWS

**Status:** Accepted for the local rehearsal.

The grading workflow needs something a tester can use quickly: verify a real
application change on a temporary preview, then watch the operator remove it.
The existing infrastructure proposal command edits repository files in a
scratch worktree; it is a separate workflow and is unsuitable as the web
request contract.

Use a small loopback FastAPI process with a build-free browser UI. Reuse
FastAPI and Uvicorn from the existing stack for typed HTTP validation and
serving. Separate the typed request and runner state from the HTTP layer.
Use an expiring invite, a guest session and explicit operator approval.
The simulated runner has one slot, checks ownership on preview access and
enforces the requested lifetime. The sign-up form has two fixed versions.

Keeping the portal local and the runner simulated gives the class an easy
rehearsal with no AWS costs or model availability dependencies. It provides
no evidence about AWS deployment speed or recovery. State is intentionally
discarded on process stop. The cloud integration must preserve the bounded
spec and approval boundary, while replacing the mock with fixed Terraform
modules, real health checks, durable state and reliable cleanup.
