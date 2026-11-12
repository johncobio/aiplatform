import http.client
import json
import shutil

import pytest

from preview_demo.previewctl import verify
from preview_demo.terraform_runner import RunnerError, Workspace
from preview_demo.workflow import Spec


@pytest.mark.skipif(shutil.which("terraform") is None, reason="Terraform integration test")
def test_real_local_plan_approval_and_cleanup(tmp_path):
    with Workspace("local", base=tmp_path) as workspace:
        approval, changes = workspace.plan(Spec(2, 15))
        assert changes == ["terraform_data.preview: create"]
        with pytest.raises(RunnerError, match="does not match"):
            workspace.apply("wrong")
        assert not workspace.has_resources()
        plan = workspace.path / "preview.tfplan"
        saved = plan.read_bytes()
        plan.write_bytes(saved + b"changed")
        with pytest.raises(RunnerError, match="does not match"):
            workspace.apply(approval)
        plan.write_bytes(saved)
        assert workspace.apply(approval) == {"version": 2, "minutes": 15}
        assert workspace.has_resources()
        with pytest.raises(RunnerError, match="destroy"):
            workspace.plan(Spec(1, 30))
        workspace.destroy()
        workspace.destroy()
        assert not workspace.has_resources()
        assert workspace.plan(Spec(1, 30))[1] == ["terraform_data.preview: create"]


def test_workspace_blocks_concurrent_operator(tmp_path):
    with (
        Workspace("local", base=tmp_path),
        pytest.raises(RunnerError, match="already running"),
        Workspace("local", base=tmp_path),
    ):
        pass


def test_terraform_failure_shows_stage_and_diagnostics(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    with (
        Workspace("local", base=tmp_path) as workspace,
        pytest.raises(RunnerError, match="init.*terraform"),
    ):
        workspace.plan(Spec(2, 15))


def test_health_failure_preserves_diagnostic(monkeypatch):
    def unreachable(*_args, **_kwargs):
        raise ConnectionRefusedError("connection refused")

    monkeypatch.setattr(http.client.HTTPConnection, "request", unreachable)
    with pytest.raises(RunnerError, match="verify: connection refused.*boot logs"):
        verify({"endpoint": "http://127.0.0.1:8000", "version": 2}, seconds=0)


def test_destroy_does_not_claim_cleanup_after_untracked_apply(tmp_path):
    with Workspace("local", base=tmp_path) as workspace:
        (workspace.path / "apply.pending").touch()
        with pytest.raises(RunnerError, match="unresolved apply"):
            workspace.destroy()


def test_plan_rejects_ingress_that_does_not_match_operator(tmp_path, monkeypatch):
    with Workspace("academy", base=tmp_path) as workspace:
        plan = {
            "variables": {"operator_cidr": {"value": "8.8.8.8/32"}},
            "resource_changes": [
                {
                    "mode": "managed",
                    "address": "aws_vpc_security_group_ingress_rule.preview",
                    "change": {
                        "actions": ["create"],
                        "after": {
                            "cidr_ipv4": "0.0.0.0/0",
                            "ip_protocol": "tcp",
                            "from_port": 8000,
                            "to_port": 8000,
                        },
                    },
                }
            ],
        }
        monkeypatch.setattr(workspace, "run", lambda *_args: json.dumps(plan))
        with pytest.raises(RunnerError, match="Unexpected planned ingress"):
            workspace.inspect_plan(workspace.saved_plan, "create")
