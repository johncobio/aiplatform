from aiplatform import cluster
from aiplatform.steps.pipeline import Pipeline


def test_up_skips_create_when_cluster_exists(runner, monkeypatch):
    monkeypatch.setattr(cluster.shell, "require", lambda *a, **k: None)
    runner.responses["kind get"] = "aiplatform\n"
    result = Pipeline().run(cluster.up_steps(runner), {})
    assert result.succeeded, result.error
    assert not runner.find("kind", "create")
    charts = [c[c.index("--install") + 1] for c in runner.find("helm") if "--install" in c]
    assert charts == [
        "ingress-nginx",
        "metrics-server",
        "argo-cd",
        "kube-prometheus-stack",
        "opentelemetry-collector",
    ]
    versions = [c[c.index("--version") + 1] for c in runner.find("helm")]
    assert versions == [
        cluster.INGRESS_NGINX_CHART,
        cluster.METRICS_SERVER_CHART,
        cluster.ARGOCD_CHART,
        cluster.KUBE_PROMETHEUS_STACK_CHART,
        cluster.OTEL_COLLECTOR_CHART,
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
    assert "argo-cd" in charts
    apply = [c for c in runner.find("kubectl") if "apply" in c][0]
    assert apply[-1].endswith("deploy/argocd")


def test_up_applies_observability_manifests_and_dashboards(runner, monkeypatch):
    monkeypatch.setattr(cluster.shell, "require", lambda *a, **k: None)
    runner.responses["kind get"] = "aiplatform\n"
    runner.responses["kubectl --context kind-aiplatform -n observability create configmap"] = (
        "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: dashboard-x\ndata: {}\n"
    )
    result = Pipeline().run(cluster.up_steps(runner), {})
    assert result.succeeded, result.error
    applied = [c[-1] for c in runner.find("kubectl") if "apply" in c]
    assert any(a.endswith("deploy/observability/jaeger.yaml") for a in applied)
    assert any(a.endswith("deploy/observability/namespace.yaml") for a in applied)
    assert "-" in applied  # dashboard configmap piped via stdin
