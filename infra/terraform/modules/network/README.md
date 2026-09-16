# network

VPC with two public subnets (two AZs), an internet gateway and a public route
table. No NAT gateway by design (cost). The default security group is emptied.

Inputs: `name`, `cidr`, `public_subnet_cidrs`, `tags`.
Outputs: `vpc_id`, `vpc_cidr`, `public_subnet_ids`, `availability_zones`.
