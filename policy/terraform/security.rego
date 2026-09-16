# Terraform security policies (conftest --parser hcl2). Each .tf file is one
# input document; every resource instance is a list of bodies:
#   {"resource": {"aws_instance": {"this": [ {...} ]}}, "variable": {"x": [ {...} ]}}
package terraform

import rego.v1

# resources(kind) yields {name, body} pairs for every instance of a resource type.
resources(kind) := [{"name": name, "body": body} |
	some name, bodies in object.get(input, ["resource", kind], {})
	some body in bodies
]

variables := [{"name": name, "body": body} |
	some name, bodies in object.get(input, ["variable"], {})
	some body in bodies
]

# --- No world-open ingress -------------------------------------------------

deny contains msg if {
	some r in resources("aws_vpc_security_group_ingress_rule")
	r.body.cidr_ipv4 == "0.0.0.0/0"
	msg := sprintf("aws_vpc_security_group_ingress_rule.%s allows 0.0.0.0/0", [r.name])
}

deny contains msg if {
	some r in resources("aws_security_group")
	some ingress in r.body.ingress
	"0.0.0.0/0" in ingress.cidr_blocks
	msg := sprintf("aws_security_group.%s has an ingress rule open to 0.0.0.0/0", [r.name])
}

deny contains msg if {
	some v in variables
	contains(v.name, "cidr")
	some d in v.body.default
	d == "0.0.0.0/0"
	msg := sprintf("variable %s defaults to 0.0.0.0/0", [v.name])
}

# --- Encryption and instance hardening -----------------------------------

deny contains msg if {
	some r in resources("aws_instance")
	some dev in r.body.root_block_device
	not dev.encrypted == true
	msg := sprintf("aws_instance.%s root volume is not encrypted", [r.name])
}

deny contains msg if {
	some r in resources("aws_instance")
	not imdsv2_required(r.body)
	msg := sprintf("aws_instance.%s must require IMDSv2 (metadata_options.http_tokens = \"required\")", [r.name])
}

imdsv2_required(body) if {
	some mo in body.metadata_options
	mo.http_tokens == "required"
}

deny contains msg if {
	some r in resources("aws_s3_bucket_public_access_block")
	some field in ["block_public_acls", "block_public_policy", "ignore_public_acls", "restrict_public_buckets"]
	not r.body[field] == true
	msg := sprintf("aws_s3_bucket_public_access_block.%s must set %s = true", [r.name, field])
}

deny contains msg if {
	some r in resources("aws_s3_bucket_acl")
	startswith(r.body.acl, "public")
	msg := sprintf("aws_s3_bucket_acl.%s grants a public ACL", [r.name])
}

deny contains msg if {
	some r in resources("aws_ecr_repository")
	not r.body.image_tag_mutability == "IMMUTABLE"
	msg := sprintf("aws_ecr_repository.%s must use IMMUTABLE tags", [r.name])
}
