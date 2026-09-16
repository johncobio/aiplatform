import itertools
import json
from pathlib import Path

import pytest
import yaml

from aiplatform.state import StateStore
from aiplatform.steps import docker as docker_steps
from aiplatform.steps.pipeline import Pipeline
from aiplatform.targets.kind import KindTarget, build_values, format_cpu


@pytest.fixture(autouse=True)
def unique_tags(monkeypatch):
    counter = itertools.count(1)
    monkeypatch.setattr(docker_steps, "image_tag", lambda: f"tag{next(counter)}")


@pytest.fixture
def kind_runner(runner):
    runner.responses["kind get"] = "aiplatform\n"
    runner.responses["kubectl --context"] = "node/aiplatform-control-plane\n"
    return runner


def make_ctx(config, tmp_path):
    (tmp_path / "Dockerfile").write_text("FROM scratch\n")
    return {
        "config": config,
        "workload_dir": tmp_path,
        "state": StateStore(tmp_path / ".aiplatform"),
        "timeout": 5,
    }


@pytest.mark.parametrize(
    ("cores", "expected"), [(2.0, "2"), (0.5, "500m"), (1.5, "1500m"), (0.25, "250m")]
)
def test_format_cpu(cores, expected):
    assert format_cpu(cores) == expected


def test_build_values_maps_config(config):
    v = build_values(config, "aiplatform/demo:t1", "t1")
    assert v["image"] == {"repository": "aiplatform/demo", "tag": "t1"}
    assert v["resources"]["limits"] == {"cpu": "500m", "memory": "1.0Gi"}
    assert v["resources"]["requests"]["cpu"] == "250m"
    assert v["resources"]["requests"]["memory"] == "1.0Gi"
    assert v["autoscaling"]["enabled"] is False  # max replicas is 1
    assert v["ingress"]["host"] == "demo.dev.127.0.0.1.nip.io"
    assert v["model"]["url"].endswith(".gguf")
    assert v["env"] == {"LOG_LEVEL": "DEBUG"}


def test_build_values_enables_hpa_when_max_gt_1(config):
    cfg = config.model_copy(
        update={"autoscaling": config.autoscaling.model_copy(update={"max": 4})}
    )
    v = build_values(cfg, "img:t", "t")
    assert v["autoscaling"] == {"enabled": True, "minReplicas": 1, "maxReplicas": 4}


def test_deploy_pipeline_builds_loads_and_upgrades(config, tmp_path, kind_runner):
    target = KindTarget(runner=kind_runner, wait_for_http=lambda *a, **k: 0.0)
    ctx = make_ctx(config, tmp_path)
    result = Pipeline().run(target.deploy_steps(ctx), ctx)
    assert result.succeeded, result.error

    assert kind_runner.find("docker", "build")
    load = kind_runner.find("kind", "load")[0]
    assert load[3] == "aiplatform/demo:tag1" and load[-1] == "aiplatform"

    helm = kind_runner.find("helm")[0]
    assert "upgrade" in helm and "--install" in helm
    assert helm[helm.index("-n") + 1] == "aiplatform-dev"
    assert "--create-namespace" in helm
    values_files = [helm[i + 1] for i, a in enumerate(helm) if a == "-f"]
    assert values_files[0].endswith("deploy/environments/dev/values.yaml")
    generated = yaml.safe_load(Path(values_files[1]).read_text())
    assert generated["image"]["tag"] == "tag1"

    rollout = [c for c in kind_runner.calls if "rollout" in c][0]
    assert "deployment/demo" in rollout and "--timeout=5s" in rollout

    assert ctx["endpoint"] == "http://demo.dev.127.0.0.1.nip.io"
    assert ctx["state"].load("dev", "demo").current.tag == "tag1"


def test_deploy_fails_when_cluster_missing(config, tmp_path, runner):
    runner.responses["kind get"] = ""
    target = KindTarget(runner=runner, wait_for_http=lambda *a, **k: 0.0)
    ctx = make_ctx(config, tmp_path)
    result = Pipeline().run(target.deploy_steps(ctx), ctx)
    assert not result.succeeded
    assert "cluster up" in result.error
    assert not runner.find("docker", "build")


def test_rollback_uses_helm_history(config, tmp_path, kind_runner):
    kind_runner.responses["helm --kube-context"] = json.dumps(
        [{"revision": 1, "status": "superseded"}, {"revision": 2, "status": "deployed"}]
    )
    target = KindTarget(runner=kind_runner, wait_for_http=lambda *a, **k: 0.0)
    ctx = make_ctx(config, tmp_path)
    # current_image() reads the deployment image via kubectl jsonpath
    kind_runner.responses["kubectl --context"] = "aiplatform/demo:tag1"
    result = Pipeline().run(target.rollback_steps(ctx), ctx)
    assert result.succeeded, result.error
    rollback = [c for c in kind_runner.calls if "rollback" in c][0]
    assert rollback[rollback.index("rollback") + 2] == "1"
    assert not kind_runner.find("docker", "build")
    assert ctx["state"].load("dev", "demo").current.image == "aiplatform/demo:tag1"


def test_rollback_requires_two_revisions(config, tmp_path, kind_runner):
    kind_runner.responses["helm --kube-context"] = json.dumps([{"revision": 1}])
    target = KindTarget(runner=kind_runner, wait_for_http=lambda *a, **k: 0.0)
    result = Pipeline().run(
        target.rollback_steps(make_ctx(config, tmp_path)), make_ctx(config, tmp_path)
    )
    assert not result.succeeded and "previous" in result.error


def test_destroy_uninstalls_release(config, tmp_path, kind_runner):
    target = KindTarget(runner=kind_runner)
    ctx = make_ctx(config, tmp_path)
    result = Pipeline().run(target.destroy_steps(ctx), ctx)
    assert result.succeeded, result.error
    assert any("uninstall" in c for c in kind_runner.calls)


def test_status_reads_deployment(config, tmp_path, kind_runner):
    kind_runner.responses["kubectl --context"] = json.dumps(
        {
            "metadata": {"creationTimestamp": "2026-09-16T00:00:00Z"},
            "spec": {
                "replicas": 2,
                "template": {"spec": {"containers": [{"image": "aiplatform/demo:t9"}]}},
            },
            "status": {"readyReplicas": 2},
        }
    )
    target = KindTarget(runner=kind_runner, probe=lambda url: (200, '{"status":"ready"}'))
    st = target.status(make_ctx(config, tmp_path))
    assert st.running and st.ready
    assert st.image == "aiplatform/demo:t9"
    assert "2/2" in st.detail
