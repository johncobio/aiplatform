# Terraform cost guardrails: expensive resource types and instance families
# need an explicit human decision, never an agent's default.
package terraform

import rego.v1

allowed_type_regex := data.limits.allowed_instance_type_regex

deny contains msg if {
	some r in resources("aws_instance")
	t := r.body.instance_type
	is_string(t)
	not startswith(t, "${")
	not regex.match(allowed_type_regex, t)
	msg := sprintf("aws_instance.%s instance_type %q is outside the allowed Graviton sizes", [r.name, t])
}

deny contains msg if {
	some v in variables
	v.name == "instance_type"
	is_string(v.body.default)
	not regex.match(allowed_type_regex, v.body.default)
	msg := sprintf("variable instance_type defaults to %q, outside the allowed Graviton sizes", [v.body.default])
}

deny contains msg if {
	some r in resources("aws_eks_node_group")
	some t in r.body.instance_types
	not startswith(t, "${")
	not regex.match(allowed_type_regex, t)
	msg := sprintf("aws_eks_node_group.%s uses instance type %q outside the allowed Graviton sizes", [r.name, t])
}

# NAT gateways cost ~$32/month each before traffic; the platform design avoids them (ADR 0003).
deny contains msg if {
	some r in resources("aws_nat_gateway")
	msg := sprintf("aws_nat_gateway.%s: NAT gateways are not allowed (public-subnet design, ADR 0003)", [r.name])
}

warn contains msg if {
	some r in resources("aws_eks_cluster")
	msg := sprintf("aws_eks_cluster.%s adds ~$73/month for the control plane; confirm the budget", [r.name])
}

warn contains msg if {
	some r in resources("aws_lb")
	msg := sprintf("aws_lb.%s adds ~$16/month plus LCU charges", [r.name])
}
