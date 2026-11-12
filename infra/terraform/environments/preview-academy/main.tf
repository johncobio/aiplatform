data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

data "aws_ssm_parameter" "al2023_x86" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_security_group" "preview" {
  name_prefix = "aiplatform-preview-"
  description = "Single-operator preview; no SSH or outbound connections"
  vpc_id      = data.aws_vpc.default.id
}

resource "aws_vpc_security_group_ingress_rule" "preview" {
  security_group_id = aws_security_group.preview.id
  description       = "Temporary sample form from the operator only"
  cidr_ipv4         = var.operator_cidr
  ip_protocol       = "tcp"
  from_port         = 8000
  to_port           = 8000
}

resource "aws_instance" "academy_demo" {
  #checkov:skip=CKV2_AWS_41:ADR 0014. The inline preview runs without AWS API calls; no role is needed.
  ami                                  = nonsensitive(data.aws_ssm_parameter.al2023_x86.value)
  instance_type                        = "t3.small"
  subnet_id                            = sort(data.aws_subnets.default.ids)[0]
  vpc_security_group_ids               = [aws_security_group.preview.id]
  associate_public_ip_address          = true
  ebs_optimized                        = true
  instance_initiated_shutdown_behavior = "terminate"
  user_data = templatefile("${path.module}/bootstrap.sh.tftpl", {
    sample  = filebase64("${path.module}/sample.py")
    version = var.preview_version
    minutes = var.preview_minutes
  })
  user_data_replace_on_change = true

  credit_specification {
    cpu_credits = "standard"
  }
  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    http_endpoint               = "enabled"
    instance_metadata_tags      = "disabled"
  }
  root_block_device {
    volume_type           = "gp2"
    volume_size           = 8
    encrypted             = true
    delete_on_termination = true
  }
  tags = {
    Name        = "aiplatform-academy-preview"
    Project     = "aiplatform"
    Environment = "academy"
    ManagedBy   = "terraform"
  }
}
