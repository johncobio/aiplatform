mock_provider "aws" {
  mock_data "aws_vpc" {
    defaults = { id = "vpc-0123456789abcdef0" }
  }
  mock_data "aws_subnets" {
    defaults = { ids = ["subnet-0123456789abcdef0"] }
  }
  mock_data "aws_ssm_parameter" {
    defaults = { value = "ami-0123456789abcdef0" }
  }
}

variables {
  expected_account_id = "000000000000" # Synthetic fixture only.
  operator_cidr       = "192.0.2.10/32"
  preview_version     = 2
  preview_minutes     = 15
}

run "restricted_preview" {
  command = plan
  assert {
    condition = (
      aws_vpc_security_group_ingress_rule.preview.cidr_ipv4 == var.operator_cidr &&
      aws_vpc_security_group_ingress_rule.preview.from_port == 8000 &&
      aws_vpc_security_group_ingress_rule.preview.to_port == 8000
    )
    error_message = "Only the operator may reach TCP 8000."
  }
  assert {
    condition = (
      aws_instance.academy_demo.instance_type == "t3.small" &&
      aws_instance.academy_demo.credit_specification[0].cpu_credits == "standard" &&
      aws_instance.academy_demo.metadata_options[0].http_tokens == "required"
    )
    error_message = "Keep the allowlisted instance, standard credits and IMDSv2."
  }
  assert {
    condition = (
      aws_instance.academy_demo.root_block_device[0].encrypted &&
      aws_instance.academy_demo.root_block_device[0].volume_type == "gp2" &&
      aws_instance.academy_demo.root_block_device[0].delete_on_termination &&
      aws_instance.academy_demo.instance_initiated_shutdown_behavior == "terminate" &&
      strcontains(aws_instance.academy_demo.user_data, "+15 minutes") &&
      strcontains(aws_instance.academy_demo.user_data, "Persistent=true") &&
      strcontains(aws_instance.academy_demo.user_data, "sample.py 2 0.0.0.0 8000")
    )
    error_message = "The approved version and lifetime must reach the host with safe cleanup."
  }
}

run "reject_wide_cidr" {
  command = plan
  variables {
    operator_cidr = "0.0.0.0/0"
  }
  expect_failures = [var.operator_cidr]
}

run "reject_unknown_version_and_lifetime" {
  command = plan
  variables {
    preview_version = 3
    preview_minutes = 120
  }
  expect_failures = [var.preview_version, var.preview_minutes]
}

run "reject_multicast" {
  command = plan
  variables {
    operator_cidr = "224.0.0.1/32"
  }
  expect_failures = [var.operator_cidr]
}
