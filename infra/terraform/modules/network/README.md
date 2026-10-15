# network

VPC with two public subnets (two AZs), an internet gateway and a public route
table. No NAT gateway by design (cost). The default security group is emptied.

Inputs: `name`, `cidr`, `public_subnet_cidrs`, `tags`.
`availability_zone_names` pins the allowed zone identities (defaults to
`us-east-1a` and `us-east-1b`). Environment roots select region-a and region-b;
verify both exist in the target account before planning.
Outputs: `vpc_id`, `vpc_cidr`, `public_subnet_ids`, `availability_zones`.
