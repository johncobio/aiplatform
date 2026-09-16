# Developer entrypoints. Every target is safe to run locally unless marked AWS.
.DEFAULT_GOAL := help
SHELL := /bin/bash

CLI      := cli
SERVICE  := services/llm-service
TF_DIRS  := $(shell find infra/terraform -name '*.tf' -not -path '*/.terraform/*' -exec dirname {} \; | sort -u)

.PHONY: help setup check lint test test-cli test-service tf-fmt tf-validate helm-lint run-local status logs destroy-local cluster-up cluster-down run-kind destroy-kind run-gitops destroy-gitops dashboard loadtest policy guard chaos

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: ## Install dev dependencies for the CLI and the service
	cd $(CLI) && uv sync --extra dev
	cd $(SERVICE) && uv sync --extra dev

check: lint test tf-validate helm-lint policy ## Everything CI runs

lint: ## Ruff lint + format check
	cd $(CLI) && uv run ruff check . && uv run ruff format --check .
	cd $(SERVICE) && uv run ruff check . && uv run ruff format --check .

fmt: ## Auto-format Python and Terraform
	cd $(CLI) && uv run ruff check --fix . && uv run ruff format .
	cd $(SERVICE) && uv run ruff check --fix . && uv run ruff format .
	terraform fmt -recursive infra/terraform

test: test-cli test-service ## All unit tests

test-cli:
	cd $(CLI) && uv run pytest

test-service:
	cd $(SERVICE) && uv run pytest

tf-fmt: ## Check Terraform formatting
	terraform fmt -check -recursive infra/terraform

tf-validate: tf-fmt ## terraform init -backend=false && validate for every root/module
	@for d in $(TF_DIRS); do \
	  echo "== $$d"; \
	  (cd $$d && terraform init -backend=false -input=false >/dev/null && terraform validate) || exit 1; \
	done

policy: ## OPA/Conftest policies for Terraform and the rendered chart (what `aiplatform propose` enforces)
	conftest test --parser hcl2 -p policy/terraform -d policy/data -n terraform $$(find infra/terraform -name '*.tf' -not -path '*/.terraform/*')
	helm template ci deploy/helm/llm-workload --set image.tag=ci --set ingress.host=ci.local --set autoscaling.enabled=true -f deploy/environments/dev/values.yaml | conftest test -p policy/kubernetes -d policy/data -n kubernetes -

guard: ## Run the proposal guardrails on the working tree (terraform, checkov, OPA, cost)
	cd $(CLI) && uv run aiplatform guard --all

helm-lint: ## Lint and render the workload chart
	helm lint deploy/helm/llm-workload --set image.tag=ci --set ingress.host=ci.local --strict
	helm template ci deploy/helm/llm-workload --set image.tag=ci --set ingress.host=ci.local -f deploy/environments/dev/values.yaml >/dev/null
	./scripts/check_chart.sh

cluster-up: ## Create the local kind cluster with ingress-nginx and metrics-server
	cd $(CLI) && uv run aiplatform cluster up

cluster-down: ## Delete the local kind cluster
	cd $(CLI) && uv run aiplatform cluster down

run-kind: ## Deploy the sample service to the kind cluster via Helm
	cd $(CLI) && uv run aiplatform deploy --dir ../$(SERVICE) --target kind

destroy-kind: ## Uninstall the sample service from the kind cluster
	cd $(CLI) && uv run aiplatform destroy --dir ../$(SERVICE) --target kind

run-gitops: ## Deploy the sample service to staging through Git + Argo CD
	cd $(CLI) && uv run aiplatform deploy --dir ../$(SERVICE) --target gitops --env staging

destroy-gitops: ## Remove the staging workload from Git (Argo CD prunes it)
	cd $(CLI) && uv run aiplatform destroy --dir ../$(SERVICE) --target gitops --env staging

dashboard: ## Regenerate the Grafana dashboard JSON and validate its queries against Prometheus
	python3 scripts/gen_dashboard.py deploy/observability/dashboards/llm-inference.json
	python3 scripts/check_dashboard.py deploy/observability/dashboards/llm-inference.json http://prometheus.127.0.0.1.nip.io environment=staging workload=llm-service

LOADTEST_URL ?= http://llm-service.staging.127.0.0.1.nip.io
SCENARIO ?= smoke
VUS ?= 2
DURATION ?= 2m

loadtest: ## Run a k6 scenario (SCENARIO=smoke|steady|ramp|step VUS=n DURATION=2m LOADTEST_URL=...)
	k6 run -e BASE_URL=$(LOADTEST_URL) -e SCENARIO=$(SCENARIO) -e VUS=$(VUS) -e DURATION=$(DURATION) loadtest/k6/chat.js

EXPERIMENT ?= pod-kill
chaos: ## Run a chaos experiment with load and measured recovery (EXPERIMENT=pod-kill|adapter-outage|ingress-restart)
	python3 chaos/experiment.py $(EXPERIMENT) --env dev --workload qwen-server

run-local: ## Deploy the sample service locally with the CLI
	cd $(CLI) && uv run aiplatform deploy --dir ../$(SERVICE) --target local

status: ## Show local deployment status
	cd $(CLI) && uv run aiplatform status --dir ../$(SERVICE)

logs: ## Tail local deployment logs
	cd $(CLI) && uv run aiplatform logs --dir ../$(SERVICE) -f

destroy-local: ## Remove the local container
	cd $(CLI) && uv run aiplatform destroy --dir ../$(SERVICE)
