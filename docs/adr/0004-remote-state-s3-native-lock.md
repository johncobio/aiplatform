# 0004 — Remote Terraform state in S3 with native lockfile

2026-09-16 · Accepted

## Context

Remote state is needed for CI (V3) and for the AI agent workflow (V7).
The classic pattern uses S3 + a DynamoDB table for locking.

## Decision

Use the S3 backend with `use_lockfile = true` (Terraform ≥ 1.10), which locks
via a `.tflock` object in the bucket. One bucket per AWS account, one key per
environment (`env/<env>/terraform.tfstate`). The bucket is created by a tiny
`bootstrap/` stack with local state, versioning, default encryption, and
public access blocked.

## Consequences

- No DynamoDB table to manage or pay for.
- The bootstrap stack's state file is local and gitignored; the bucket name is
  passed as a variable, never committed.
