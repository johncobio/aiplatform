# ec2-service

Runs one container on a Graviton EC2 instance. Stepping stone before EKS.

- Amazon Linux 2023 arm64 AMI resolved from the public SSM parameter.
- IAM role: `AmazonSSMManagedInstanceCore` + pull from **one** ECR repository.
- No SSH: use `aws ssm start-session --target <instance_id>`.
- IMDSv2 required, encrypted gp3 root volume, security group limited to
  `allowed_cidrs` (refuses `0.0.0.0/0`).
- Changing `image` replaces the instance (user data change), which is a
  crude but honest immutable deployment. Model files are cached on the
  instance volume and lost on replacement.

Cost while running (us-east-1, on-demand): t4g.small ≈ $0.0168/h ≈ $12/month;
20 GB gp3 ≈ $1.60/month.
