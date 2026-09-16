# Single-instance container host. V1 stepping stone; replaced by EKS in V2.
# Access is via SSM Session Manager only: no key pair, no port 22.

data "aws_region" "current" {}

# Latest Amazon Linux 2023 arm64 AMI via the public SSM parameter (no hardcoded AMI ids).
data "aws_ssm_parameter" "al2023_arm64" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64"
}

# ---------- IAM: least privilege ----------

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "this" {
  name               = "${var.name}-instance"
  assume_role_policy = data.aws_iam_policy_document.assume.json
  tags               = var.tags
}

# Session Manager (shell access without SSH) – AWS managed policy.
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.this.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "ecr_pull" {
  # GetAuthorizationToken does not support resource-level permissions.
  statement {
    sid       = "EcrAuth"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    sid = "EcrPullFromWorkloadRepo"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = [var.ecr_repository_arn]
  }
}

resource "aws_iam_role_policy" "ecr_pull" {
  name   = "ecr-pull"
  role   = aws_iam_role.this.id
  policy = data.aws_iam_policy_document.ecr_pull.json
}

resource "aws_iam_instance_profile" "this" {
  name = "${var.name}-instance"
  role = aws_iam_role.this.name
  tags = var.tags
}

# ---------- Network ----------

resource "aws_security_group" "this" {
  name        = "${var.name}-svc"
  description = "Container port from allowed CIDRs; all egress (image pull, model download)"
  vpc_id      = var.vpc_id
  tags        = merge(var.tags, { Name = "${var.name}-svc" })
}

resource "aws_vpc_security_group_ingress_rule" "app" {
  for_each = toset(var.allowed_cidrs)

  security_group_id = aws_security_group.this.id
  description       = "service port"
  cidr_ipv4         = each.value
  from_port         = var.container_port
  to_port           = var.container_port
  ip_protocol       = "tcp"
  tags              = var.tags
}

resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.this.id
  description       = "all egress"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  tags              = var.tags
}

# ---------- Instance ----------

locals {
  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    region         = data.aws_region.current.region
    image          = var.image
    container_port = var.container_port
    memory_mb      = var.container_memory_mb
    env            = var.container_env
  })
}

resource "aws_instance" "this" {
  ami                         = nonsensitive(data.aws_ssm_parameter.al2023_arm64.value)
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = [aws_security_group.this.id]
  iam_instance_profile        = aws_iam_instance_profile.this.name
  associate_public_ip_address = true
  ebs_optimized               = true
  user_data                   = local.user_data
  user_data_replace_on_change = true # a new image tag re-creates the instance (immutable infra)

  metadata_options {
    http_tokens                 = "required" # IMDSv2 only
    http_put_response_hop_limit = 1
  }

  root_block_device {
    volume_type = "gp3"
    volume_size = var.root_volume_gb
    encrypted   = true
  }

  tags = merge(var.tags, { Name = var.name })
}
