from aiplatform import cluster
from aiplatform.steps.pipeline import Pipeline


def test_up_skips_create_when_cluster_exists(runner, monkeypatch):
    monkeypatch.setattr(cluster.shell, "require", lambda *a, **k: None)
    runner.responses["kind get"] = "aiplatform\n"
    result = Pipeline().run(cluster.up_steps(runner), {})
    assert result.succeeded, result.error
    assert not runner.find("kind", "create")
    charts = [c[c.index("--install") + 1] for c in runner.find("helm") if "--install" in c]
    assert charts == ["ingress-nginx", "metrics-server", "argo-cd"]
    versions = [c[c.index("--version") + 1] for c in runner.find("helm")]
    assert versions == [
        cluster.INGRESS_NGINX_CHART,
        cluster.METRICS_SERVER_CHART,
        cluster.ARGOCD_CHART,
    ]


def test_up_creates_cluster_when_missing(runner, monkeypatch):
    monkeypatch.setattr(cluster.shell, "require", lambda *a, **k: None)
    runner.responses["kind get"] = ""
    result = Pipeline().run(cluster.up_steps(runner), {})
    assert result.succeeded, result.error
    create = runner.find("kind", "create")[0]
    assert "--config" in create and create[create.index("--config") + 1].endswith(
        "deploy/kind/cluster.yaml"
    )


def test_down_fails_when_missing(runner, monkeypatch):
    monkeypatch.setattr(cluster.shell, "require", lambda *a, **k: None)
    runner.responses["kind get"] = ""
    result = Pipeline().run(cluster.down_steps(runner), {})
    assert not result.succeeded


def test_up_installs_argocd_and_applies_gitops_config(runner, monkeypatch):
    monkeypatch.setattr(cluster.shell, "require", lambda *a, **k: None)
    runner.responses["kind get"] = "aiplatform\n"
    result = Pipeline().run(cluster.up_steps(runner), {})
    assert result.succeeded, result.error
    charts = [c[c.index("--install") + 1] for c in runner.find("helm") if "--install" in c]
    assert charts[-1] == "argo-cd"
    apply = [c for c in runner.find("kubectl") if "apply" in c][0]
    assert apply[-1].endswith("deploy/argocd")
