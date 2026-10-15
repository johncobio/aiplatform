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
  operator_cidr = "192.0.2.10/32"
}

run "restricted_demo_plan" {
  command = plan
  assert {
    condition     = aws_vpc_security_group_ingress_rule.inference.cidr_ipv4 == "192.0.2.10/32" && aws_vpc_security_group_ingress_rule.inference.from_port == 8000 && aws_vpc_security_group_ingress_rule.inference.to_port == 8000
    error_message = "Only the operator may reach the demo API."
  }
  assert {
    condition     = aws_instance.academy_demo.instance_type == "t3.small" && aws_instance.academy_demo.credit_specification[0].cpu_credits == "standard"
    error_message = "Keep the approved size and prohibit unlimited CPU credit charges."
  }
  assert {
    condition     = aws_instance.academy_demo.root_block_device[0].encrypted && aws_instance.academy_demo.root_block_device[0].delete_on_termination && aws_instance.academy_demo.instance_initiated_shutdown_behavior == "terminate"
    error_message = "Root storage and automatic shutdown must support safe cleanup."
  }
}

run "reject_world_open" {
  command = plan
  variables {
    operator_cidr = "0.0.0.0/0"
  }
  expect_failures = [var.operator_cidr]
}

run "reject_shared_network" {
  command = plan
  variables {
    operator_cidr = "192.0.2.0/24"
  }
  expect_failures = [var.operator_cidr]
}
