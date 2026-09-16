# 0003 — V1 AWS target is a single Graviton EC2 instance

2026-09-16 · Accepted

## Context

The roadmap asks for "something functional on AWS" in V1 and EKS in V2. EKS
costs ≈ $73/month for the control plane alone before nodes, plus ≈ $32/month
per NAT gateway and ≈ $16/month per ALB. The owner is a student.

## Decision

V1 deploys the container to one `t4g.small` (2 vCPU, 2 GiB, Graviton) in a
public subnet, pulled from ECR, managed through SSM (no SSH). The `network`
and `ecr` modules are designed to be reused unchanged by the V2 `eks` module.
The `ec2-service` module is explicitly disposable.

Estimated cost while running: ≈ $12/month for the instance + a few cents for
ECR storage. Nothing else is billable. `terraform destroy` removes it all.

## Consequences

- Real AWS deployment, IAM, ECR, and Terraform practice without EKS pricing.
- Some throwaway work (`ec2-service`, user-data script). Accepted because it
  is small and the modules that matter carry forward.
- No load balancer in V1; the endpoint is the instance's public IP with a
  security group restricted to the operator's CIDR.
