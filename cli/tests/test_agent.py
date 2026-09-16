import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aiplatform.agent import guardrails, report
from aiplatform.agent.cost import estimate
from aiplatform.agent.models import FileChange, Proposal
from aiplatform.agent.providers import ClaudeProvider, FileProvider
from aiplatform.errors import AgentError
from aiplatform.steps.pipeline import Pipeline, Step, StepSkipped, StepStatus

REPO = Path(__file__).resolve().parents[2]

PROPOSAL = Proposal(
    summary="Add document-agent workload",
    rationale="Serve the catalog model with 3 replicas.",
    files=[
        FileChange(
            path="services/document-agent/aiplatform.yaml",
            content=(
                "name: document-agent\nmodel: qwen2.5-0.5b-instruct\nengine: llamacpp-server\n"
                "cpu: 1\nmemory: 1Gi\nenvironment: staging\nautoscaling:\n  min: 2\n  max: 3\n"
            ),
        )
    ],
    risks=["Check the ingress host"],
)


# --- providers -------------------------------------------------------------


def test_file_provider_round_trip(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(PROPOSAL.model_dump_json())
    assert FileProvider(path).propose("x", "ctx").summary == PROPOSAL.summary


def test_file_provider_rejects_invalid(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"summary": "no files"}))
    with pytest.raises(AgentError, match="invalid proposal file"):
        FileProvider(path).propose("x", "ctx")


class FakeMessages:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def test_claude_provider_uses_structured_output():
    response = SimpleNamespace(
        stop_reason="end_turn",
        parsed_output=PROPOSAL,
        usage=SimpleNamespace(input_tokens=1, output_tokens=2),
    )
    client = SimpleNamespace(messages=FakeMessages(response))
    provider = ClaudeProvider(client=client, model="claude-opus-5")
    assert provider.propose("make it HA", "context").summary == PROPOSAL.summary
    call = client.messages.calls[0]
    assert call["model"] == "claude-opus-5"
    assert call["output_format"] is Proposal
    assert call["thinking"] == {"type": "adaptive"}
    assert "make it HA" in call["messages"][0]["content"]
    assert "context" in call["messages"][0]["content"]


def test_claude_provider_surfaces_refusal():
    response = SimpleNamespace(stop_reason="refusal", parsed_output=None, usage=None)
    provider = ClaudeProvider(client=SimpleNamespace(messages=FakeMessages(response)))
    with pytest.raises(AgentError, match="declined"):
        provider.propose("x", "y")


# --- pipeline skip ---------------------------------------------------------


def test_pipeline_records_skipped_steps():
    class Skip(Step):
        name = "maybe"

        def run(self, ctx):
            raise StepSkipped("not applicable")

    ctx = {}
    result = Pipeline().run([Skip()], ctx)
    assert result.succeeded
    assert ctx["report"] == [
        {"step": "maybe", "status": StepStatus.SKIPPED, "detail": "not applicable"}
    ]


# --- cost ------------------------------------------------------------------


def test_cost_estimate_uses_max_replicas_and_memory(tmp_path):
    (tmp_path / "policy" / "data").mkdir(parents=True)
    (tmp_path / "policy" / "prices.yaml").write_text(
        "hourly_usd:\n  instance: {t4g.small: 0.0168}\n  eks_cluster: 0.1\n"
        "  nat_gateway: 0.045\n  alb: 0.0225\n"
        "per_gib_hour_usd: 0.01\nhours_per_month: 100\n"
    )
    svc = tmp_path / "services" / "demo"
    svc.mkdir(parents=True)
    (svc / "aiplatform.yaml").write_text(
        "name: demo\nmodel: qwen2.5-0.5b-instruct\ncpu: 1\nmemory: 2Gi\nenvironment: dev\n"
        "autoscaling: {min: 1, max: 4}\n"
    )
    env = tmp_path / "infra" / "terraform" / "environments" / "dev"
    env.mkdir(parents=True)
    (env / "variables.tf").write_text(
        'variable "instance_type" {\n  type = string\n  default = "t4g.small"\n}\n'
        'variable "enable_compute" {\n  default = true\n}\n'
    )
    (env / "main.tf").write_text('resource "aws_nat_gateway" "n" {}\n')
    est = estimate(tmp_path)

    def item(fragment):
        return next(i.monthly_usd for i in est.items if fragment in i.description)

    assert item("workload `demo`") == pytest.approx(4 * 2 * 0.01 * 100)  # 8.0
    assert item("t4g.small") == pytest.approx(0.0168 * 100)  # 1.68
    assert item("NAT gateway") == pytest.approx(4.5)
    assert est.total == pytest.approx(8.0 + 1.68 + 4.5)


# --- guardrails ------------------------------------------------------------


def test_apply_step_rejects_protected_paths(runner, tmp_path):
    bad = Proposal(
        summary="x", rationale="y", files=[FileChange(path=".github/workflows/ci.yml", content="")]
    )
    ctx = {"proposal": bad, "repo": tmp_path, "slug": "x", "scratch": tmp_path}
    result = Pipeline().run([guardrails.ApplyProposalStep(runner)], ctx)
    assert not result.succeeded and "protected" in result.error


def test_apply_step_rejects_paths_outside_allowed_areas(runner, tmp_path):
    bad = Proposal(
        summary="x", rationale="y", files=[FileChange(path="cli/src/evil.py", content="")]
    )
    ctx = {"proposal": bad, "repo": tmp_path, "slug": "x", "scratch": tmp_path}
    result = Pipeline().run([guardrails.ApplyProposalStep(runner)], ctx)
    assert not result.succeeded and "outside" in result.error


def test_terraform_steps_skip_without_tf_changes(runner, tmp_path):
    ctx = {"worktree": tmp_path, "changed": ["services/x/aiplatform.yaml"]}
    steps = [
        guardrails.TerraformFmtStep(runner),
        guardrails.TerraformValidateStep(runner),
        guardrails.CheckovStep(runner),
        guardrails.ConftestTerraformStep(runner),
    ]
    result = Pipeline().run(steps, ctx)
    assert result.succeeded
    assert all(e["status"] == StepStatus.SKIPPED for e in ctx["report"])
    assert not runner.calls


def test_plan_step_skips_without_aws_credentials(runner, tmp_path, monkeypatch):
    for k in ("AWS_PROFILE", "AWS_ACCESS_KEY_ID", "AWS_ROLE_ARN"):
        monkeypatch.delenv(k, raising=False)
    ctx = {"worktree": tmp_path, "changed": ["infra/terraform/environments/dev/main.tf"]}
    Pipeline().run([guardrails.TerraformPlanStep(runner)], ctx)
    assert ctx["report"][0]["status"] == StepStatus.SKIPPED
    assert "credentials" in ctx["report"][0]["detail"]


def test_cost_step_fails_over_budget():
    ctx = {"worktree": REPO, "budget": 0.01, "changed": []}
    result = Pipeline().run([guardrails.CostEstimateStep()], ctx)
    assert not result.succeeded and "exceeds budget" in result.error


def test_cost_step_passes_within_budget_on_this_repo():
    ctx = {"worktree": REPO, "budget": 1000, "changed": []}
    assert Pipeline().run([guardrails.CostEstimateStep()], ctx).succeeded
    assert ctx["cost"].total > 0


def test_workload_config_step_validates_changed_yaml(tmp_path):
    svc = tmp_path / "services" / "bad"
    svc.mkdir(parents=True)
    (svc / "aiplatform.yaml").write_text(
        "name: Bad_Name\nmodel: qwen2.5-0.5b-instruct\ncpu: 1\nmemory: 1Gi\nenvironment: dev\n"
    )
    ctx = {"worktree": tmp_path, "changed": ["services/bad/aiplatform.yaml"]}
    result = Pipeline().run([guardrails.WorkloadConfigStep()], ctx)
    assert not result.succeeded and "name" in result.error


# --- report ----------------------------------------------------------------


def test_report_renders_guardrail_table_and_checklist():
    ctx = {"report": [{"step": "terraform fmt", "status": "skipped", "detail": "no .tf changed"}]}
    body = report.render("make it HA", PROPOSAL, ctx, "file")
    assert "| terraform fmt | ⏭️ skipped | no .tf changed |" in body
    assert "- [ ] Check the ingress host" in body
    assert "services/document-agent/aiplatform.yaml" in body
