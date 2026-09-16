import itertools
import json

import pytest

from aiplatform.state import StateStore
from aiplatform.steps.pipeline import Pipeline
from aiplatform.targets import local as local_mod
from aiplatform.targets.local import LocalDockerTarget


@pytest.fixture(autouse=True)
def unique_tags(monkeypatch):
    counter = itertools.count(1)
    monkeypatch.setattr(local_mod, "_image_tag", lambda: f"tag{next(counter)}")


def make_ctx(config, tmp_path):
    (tmp_path / "Dockerfile").write_text("FROM scratch\n")
    return {
        "config": config,
        "workload_dir": tmp_path,
        "state": StateStore(tmp_path / ".aiplatform"),
        "timeout": 5,
    }


def test_deploy_builds_runs_with_limits_and_records_release(config, tmp_path, runner):
    target = LocalDockerTarget(runner=runner, wait_for_http=lambda *a, **k: 0.0)
    ctx = make_ctx(config, tmp_path)
    result = Pipeline().run(target.deploy_steps(ctx), ctx)
    assert result.succeeded, result.error

    build = runner.find("docker", "build")[0]
    assert "-t" in build and any(t.startswith("aiplatform/demo:") for t in build)

    run = runner.find("docker", "run")[0]
    assert "--cpus" in run and run[run.index("--cpus") + 1] == "0.5"
    assert "--memory" in run and run[run.index("--memory") + 1] == str(1024**3)
    assert "-p" in run and run[run.index("-p") + 1] == "8123:8123"
    assert "LLM_MODEL_URL=" + config.model_spec.artifact_url in run
    assert "LOG_LEVEL=DEBUG" in run
    assert "--user" not in run  # container image sets its own user
    assert run[-1].startswith("aiplatform/demo:")

    st = ctx["state"].load("dev", "demo")
    assert st.current is not None
    assert ctx["endpoint"] == "http://localhost:8123"


def test_deploy_fails_cleanly_when_build_fails(config, tmp_path, runner):
    runner.failures["docker build"] = 1
    target = LocalDockerTarget(runner=runner, wait_for_http=lambda *a, **k: 0.0)
    ctx = make_ctx(config, tmp_path)
    result = Pipeline().run(target.deploy_steps(ctx), ctx)
    assert not result.succeeded
    assert result.failed_step == "Docker image built"
    assert not runner.find("docker", "run")


def test_rollback_reruns_previous_image_without_build(config, tmp_path, runner):
    target = LocalDockerTarget(runner=runner, wait_for_http=lambda *a, **k: 0.0)
    ctx = make_ctx(config, tmp_path)
    Pipeline().run(target.deploy_steps(ctx), ctx)
    first = ctx["image"]
    runner.calls.clear()

    Pipeline().run(target.deploy_steps(ctx), ctx)
    runner.calls.clear()

    result = Pipeline().run(target.rollback_steps(ctx), ctx)
    assert result.succeeded, result.error
    assert not runner.find("docker", "build")
    assert runner.find("docker", "run")[0][-1] == first
    assert ctx["state"].load("dev", "demo").current.image == first


def test_status_reports_container(config, tmp_path, runner):
    runner.responses["docker inspect"] = json.dumps(
        [
            {
                "State": {"Status": "running", "StartedAt": "2026-09-16T00:00:00Z"},
                "Config": {"Image": "aiplatform/demo:abc"},
            }
        ]
    )
    target = LocalDockerTarget(runner=runner, probe=lambda url: (200, '{"status":"ready"}'))
    status = target.status(make_ctx(config, tmp_path))
    assert status.running is True
    assert status.image == "aiplatform/demo:abc"
    assert status.ready is True


def test_destroy_removes_container_and_clears_state(config, tmp_path, runner):
    target = LocalDockerTarget(runner=runner, wait_for_http=lambda *a, **k: 0.0)
    ctx = make_ctx(config, tmp_path)
    Pipeline().run(target.deploy_steps(ctx), ctx)
    result = Pipeline().run(target.destroy_steps(ctx), ctx)
    assert result.succeeded
    assert runner.find("docker", "rm")
    assert ctx["state"].load("dev", "demo").current is None
