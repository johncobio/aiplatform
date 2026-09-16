# Policies for rendered Kubernetes manifests (helm template | conftest).
package kubernetes

import rego.v1

is_workload if input.kind in {"Deployment", "StatefulSet", "DaemonSet", "Job"}

containers contains c if {
	is_workload
	some c in input.spec.template.spec.containers
}

containers contains c if {
	is_workload
	some c in input.spec.template.spec.initContainers
}

name := sprintf("%s/%s", [input.kind, input.metadata.name])

deny contains msg if {
	some c in containers
	not c.resources.limits.memory
	msg := sprintf("%s container %s has no memory limit", [name, c.name])
}

deny contains msg if {
	some c in containers
	not c.resources.requests.cpu
	msg := sprintf("%s container %s has no cpu request", [name, c.name])
}

deny contains msg if {
	some c in containers
	endswith(c.image, ":latest")
	msg := sprintf("%s container %s uses the :latest tag", [name, c.name])
}

deny contains msg if {
	some c in containers
	not contains(c.image, ":")
	not contains(c.image, "@")
	msg := sprintf("%s container %s image %q has no tag or digest", [name, c.name, c.image])
}

deny contains msg if {
	is_workload
	not input.spec.template.spec.securityContext.runAsNonRoot == true
	msg := sprintf("%s must set pod securityContext.runAsNonRoot: true", [name])
}

deny contains msg if {
	some c in containers
	c.securityContext.privileged == true
	msg := sprintf("%s container %s is privileged", [name, c.name])
}

deny contains msg if {
	some c in containers
	not c.securityContext.allowPrivilegeEscalation == false
	msg := sprintf("%s container %s must set allowPrivilegeEscalation: false", [name, c.name])
}

deny contains msg if {
	some c in containers
	mem := units.parse_bytes(c.resources.limits.memory)
	mem > data.limits.max_memory_gi_per_replica * 1024 * 1024 * 1024
	msg := sprintf("%s container %s memory limit %s exceeds %d Gi", [name, c.name, c.resources.limits.memory, data.limits.max_memory_gi_per_replica])
}

deny contains msg if {
	input.kind == "HorizontalPodAutoscaler"
	input.spec.maxReplicas > data.limits.max_replicas
	msg := sprintf("%s maxReplicas %d exceeds the platform cap of %d", [name, input.spec.maxReplicas, data.limits.max_replicas])
}

deny contains msg if {
	input.kind == "Service"
	input.spec.type == "LoadBalancer"
	msg := sprintf("%s: use an Ingress instead of a LoadBalancer Service (one ALB per service is a cost trap)", [name])
}
