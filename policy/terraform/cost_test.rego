package terraform

import rego.v1

instance_fixture(name, size, environment) := {"resource": {"aws_instance": {name: [{
    "instance_type": size,
    "tags": {"Environment": environment, "Project": "aiplatform"},
    "metadata_options": [{"http_tokens": "required"}],
    "root_block_device": [{"encrypted": true}],
}]}}}

# Removing the narrow exception must reject the approved Academy host again.
test_academy_small_allowed if {
    violations := deny with input as instance_fixture("academy_demo", "t3.small", "academy")
    count(violations) == 0
}

test_academy_larger_size_denied if {
    violations := deny with input as instance_fixture("academy_demo", "t3.medium", "academy")
    count(violations) == 1
}

test_other_environment_still_denied if {
    violations := deny with input as instance_fixture("academy_demo", "t3.small", "dev")
    count(violations) == 1
}

test_other_instance_still_denied if {
    violations := deny with input as instance_fixture("another_host", "t3.small", "academy")
    count(violations) == 1
}
