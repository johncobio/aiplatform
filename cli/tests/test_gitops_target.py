import json
from pathlib import Path

import pytest
import yaml

from aiplatform.platform import PlatformConfig
from aiplatform.state import Release, StateStore
from aiplatform.steps.pipeline import Pipeline
from aiplatform.targets.gitops import GitOpsTarget

PLATFORM = PlatformConfig.model_validate(
    {
        "registry": "ghcr.io/acme/aiplatform",
        "gitops": {"repo": "https://example/r.git", "branch": "main"},
    }
)
ARGO_APP = "kubectl --context kind-aiplatform -n argocd get application dev-demo -o json"


def synced_app(sha, multi_source=True):
    sync = (
        {"status": "Synced", "revisions": [sha, sha]}
        if multi_source
        else {"status": "Synced", "revision": sha}
    )
    return json.dumps({"status": {"sync": sync, "health": {"status": "Healthy"}}})


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "deploy" / "helm" / "llm-workload").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def gitops_runner(runner):
    runner.responses["kubectl --context kind-aiplatform -n argocd get applicationset"] = (
        "applicationset.argoproj.io/aiplatform-workloads"
    )
    runner.responses["git rev-parse --abbrev-ref HEAD"] = "main\n"
    runner.responses["git log -1 --format=%h --abbrev=7 -- . :(exclude)./aiplatform.yaml"] = (
        "abc1234\n"
    )
    runner.responses["git rev-parse HEAD"] = "deadbeefcafe\n"
    runner.responses["kubectl --context kind-aiplatform -n aiplatform-dev get deployment"] = ""
    runner.failures["helm --kube-context kind-aiplatform -n aiplatform-dev status"] = (
        1  # no direct release
    )
    runner.failures["git diff --cached --quiet"] = 1  # there is a staged change
    runner.responses[ARGO_APP] = synced_app("deadbeefcafe")
    return runner


def make_target(runner, repo):
    return GitOpsTarget(
        runner=runner,
        wait_for_http=lambda *a, **k: 0.0,
        platform=PLATFORM,
        repo=repo,
        sleep=lambda s: None,
    )


def make_ctx(config, tmp_path, **extra):
    return {
        "config": config,
        "workload_dir": tmp_path,
        "state": StateStore(tmp_path / ".aiplatform"),
        "timeout": 5,
        **extra,
    }


def test_deploy_writes_values_commits_and_waits_for_sync(config, repo, gitops_runner):
    t = make_target(gitops_runner, repo)
    ctx = make_ctx(config, repo)
    result = Pipeline().run(t.deploy_steps(ctx), ctx)
    assert result.succeeded, result.error

    assert (
        gitops_runner.find("docker", "manifest")[0][-1]
        == "ghcr.io/acme/aiplatform/demo:sha-abc1234"
    )
    values = yaml.safe_load((repo / "deploy/workloads/dev/demo.values.yaml").read_text())
    assert values["image"] == {"repository": "ghcr.io/acme/aiplatform/demo", "tag": "sha-abc1234"}
    assert values["environment"] == "dev" and values["nameOverride"] == "demo"

    commit = gitops_runner.find("git", "commit")[0]
    assert "deploy(dev): demo sha-abc1234" in commit
    assert gitops_runner.find("git", "push")[0][-1] == "main"
    assert any("application-set-refresh" in " ".join(c) for c in gitops_runner.calls)
    assert ctx["state"].load("dev", "demo").current.tag == "sha-abc1234"


def test_deploy_accepts_single_source_revision(config, repo, gitops_runner):
    gitops_runner.responses[ARGO_APP] = synced_app("deadbeefcafe", multi_source=False)
    ctx = make_ctx(config, repo)
    assert Pipeline().run(make_target(gitops_runner, repo).deploy_steps(ctx), ctx).succeeded


def test_default_tag_comes_from_last_commit_touching_context(config, repo, gitops_runner):
    ctx = make_ctx(config, repo)
    assert Pipeline().run(make_target(gitops_runner, repo).deploy_steps(ctx), ctx).succeeded
    log_call = [c for c in gitops_runner.calls if c[:2] == ["git", "log"]][0]
    assert log_call[-3:] == ["--", ".", ":(exclude)./aiplatform.yaml"]


def test_deploy_respects_explicit_image_tag(config, repo, gitops_runner):
    t = make_target(gitops_runner, repo)
    ctx = make_ctx(config, repo, image_tag="sha-0000000")
    assert Pipeline().run(t.deploy_steps(ctx), ctx).succeeded
    assert gitops_runner.find("docker", "manifest")[0][-1].endswith(":sha-0000000")


def test_deploy_fails_when_image_missing(config, repo, gitops_runner):
    gitops_runner.failures["docker manifest"] = 1
    t = make_target(gitops_runner, repo)
    ctx = make_ctx(config, repo)
    result = Pipeline().run(t.deploy_steps(ctx), ctx)
    assert not result.succeeded and "not found" in result.error
    assert not gitops_runner.find("git", "commit")


def test_deploy_refuses_wrong_branch(config, repo, gitops_runner):
    gitops_runner.responses["git rev-parse --abbrev-ref HEAD"] = "feature\n"
    result = Pipeline().run(
        make_target(gitops_runner, repo).deploy_steps(make_ctx(config, repo)),
        make_ctx(config, repo),
    )
    assert not result.succeeded and "feature" in result.error


def test_deploy_refuses_when_direct_helm_release_exists(config, repo, gitops_runner):
    del gitops_runner.failures["helm --kube-context kind-aiplatform -n aiplatform-dev status"]
    result = Pipeline().run(
        make_target(gitops_runner, repo).deploy_steps(make_ctx(config, repo)),
        make_ctx(config, repo),
    )
    assert not result.succeeded and "destroy --target kind" in result.error


def test_sync_timeout_reports_last_status(config, repo, gitops_runner):
    gitops_runner.responses[ARGO_APP] = json.dumps(
        {
            "status": {
                "sync": {"status": "OutOfSync", "revision": "old"},
                "health": {"status": "Progressing"},
            }
        }
    )
    ctx = make_ctx(config, repo)
    ctx["timeout"] = 0.01
    result = Pipeline().run(make_target(gitops_runner, repo).deploy_steps(ctx), ctx)
    assert not result.succeeded and "OutOfSync" in result.error


def test_sync_failure_is_reported(config, repo, gitops_runner):
    gitops_runner.responses[ARGO_APP] = json.dumps(
        {
            "status": {
                "sync": {"status": "OutOfSync"},
                "health": {"status": "Degraded"},
                "operationState": {"phase": "Failed", "message": "ImagePullBackOff"},
            }
        }
    )
    ctx = make_ctx(config, repo)
    result = Pipeline().run(make_target(gitops_runner, repo).deploy_steps(ctx), ctx)
    assert not result.succeeded and "ImagePullBackOff" in result.error


def test_rollback_rewrites_previous_tag(config, repo, gitops_runner):
    store = StateStore(repo / ".aiplatform")
    store.record(
        "dev",
        "demo",
        Release(
            tag="sha-1111111", image="ghcr.io/acme/aiplatform/demo:sha-1111111", target="gitops"
        ),
    )
    store.record(
        "dev",
        "demo",
        Release(
            tag="sha-2222222", image="ghcr.io/acme/aiplatform/demo:sha-2222222", target="gitops"
        ),
    )
    ctx = make_ctx(config, repo)
    result = Pipeline().run(make_target(gitops_runner, repo).rollback_steps(ctx), ctx)
    assert result.succeeded, result.error
    values = yaml.safe_load((repo / "deploy/workloads/dev/demo.values.yaml").read_text())
    assert values["image"]["tag"] == "sha-1111111"
    assert "rollback(dev): demo sha-1111111" in gitops_runner.find("git", "commit")[0]


def test_destroy_deletes_file_and_waits_for_app_removal(config, repo, gitops_runner):
    path = repo / "deploy/workloads/dev/demo.values.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("x: 1\n")
    gitops_runner.failures[ARGO_APP] = 1  # application already gone
    ctx = make_ctx(config, repo)
    result = Pipeline().run(make_target(gitops_runner, repo).destroy_steps(ctx), ctx)
    assert result.succeeded, result.error
    assert not path.exists()
    assert "remove(dev): demo" in gitops_runner.find("git", "commit")[0]


def test_status_includes_argo_state(config, repo, gitops_runner):
    gitops_runner.responses[
        "kubectl --context kind-aiplatform -n aiplatform-dev get deployment"
    ] = json.dumps(
        {
            "metadata": {},
            "spec": {"replicas": 1, "template": {"spec": {"containers": [{"image": "i:t"}]}}},
            "status": {"readyReplicas": 1},
        }
    )
    t = GitOpsTarget(
        runner=gitops_runner, probe=lambda url: (200, "ok"), platform=PLATFORM, repo=repo
    )
    st = t.status(make_ctx(config, repo))
    assert st.ready and "argocd Synced/Healthy" in st.detail


def test_values_path_layout(config, repo, runner):
    t = make_target(runner, repo)
    assert t.values_path(config) == Path(repo) / "deploy/workloads/dev/demo.values.yaml"


def test_upstream_engine_skips_registry_check(config, repo, gitops_runner):
    cfg = config.model_copy(update={"engine": "llamacpp-server"})
    ctx = make_ctx(cfg, repo)
    result = Pipeline().run(make_target(gitops_runner, repo).deploy_steps(ctx), ctx)
    assert result.succeeded, result.error
    assert not gitops_runner.find("docker", "manifest")
    values = yaml.safe_load((repo / "deploy/workloads/dev/demo.values.yaml").read_text())
    assert values["engine"]["type"] == "llamacpp-server" and "image" not in values
