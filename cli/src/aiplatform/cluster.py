"""Local platform cluster lifecycle: kind + ingress-nginx + metrics-server.

This is the local equivalent of the EKS Terraform stack: the cluster and the
platform add-ons every workload relies on.
"""

import logging

from aiplatform import paths, shell
from aiplatform.errors import StepError
from aiplatform.steps.pipeline import Context, Step
from aiplatform.targets.kind import CLUSTER_NAME, KUBE_CONTEXT

log = logging.getLogger(__name__)

# Pinned add-on chart versions (checked 2026-09-16). Bump deliberately.
INGRESS_NGINX_CHART = "4.15.1"
INGRESS_NGINX_REPO = "https://kubernetes.github.io/ingress-nginx"
METRICS_SERVER_CHART = "3.14.0"
METRICS_SERVER_REPO = "https://kubernetes-sigs.github.io/metrics-server/"
ARGOCD_CHART = "10.9.1"  # Argo CD v3.5.3
ARGOCD_REPO = "https://argoproj.github.io/argo-helm"
KUBE_PROMETHEUS_STACK_CHART = "91.4.1"  # Prometheus Operator v0.94.0
KUBE_PROMETHEUS_STACK_REPO = "https://prometheus-community.github.io/helm-charts"
OTEL_COLLECTOR_CHART = "0.173.1"  # collector 0.160.0
OTEL_COLLECTOR_REPO = "https://open-telemetry.github.io/opentelemetry-helm-charts"
OBSERVABILITY_NAMESPACE = "observability"


def cluster_exists(run: shell.Runner) -> bool:
    proc = run(["kind", "get", "clusters"], check=False)
    return CLUSTER_NAME in proc.stdout.split()


class ToolsAvailable(Step):
    name = "Tools available"

    def run(self, ctx: Context) -> str | None:
        for tool in ("docker", "kind", "kubectl", "helm"):
            shell.require(tool, f"Install it with `brew install {tool}`.")
        return "docker, kind, kubectl, helm"


class CreateCluster(Step):
    name = "kind cluster created"

    def __init__(self, run: shell.Runner) -> None:
        super().__init__()
        self._run = run

    def run(self, ctx: Context) -> str | None:
        if cluster_exists(self._run):
            return f"{CLUSTER_NAME} already exists"
        self._run(
            [
                "kind",
                "create",
                "cluster",
                "--config",
                str(paths.kind_config_path()),
                "--wait",
                "120s",
            ]
        )
        return CLUSTER_NAME


class InstallAddon(Step):
    def __init__(
        self, run: shell.Runner, name: str, repo: str, version: str, namespace: str
    ) -> None:
        self.name = f"{name} installed"
        super().__init__()
        self._run = run
        self.addon, self.repo, self.version, self.namespace = name, repo, version, namespace

    def run(self, ctx: Context) -> str | None:
        values = paths.kind_addon_values(self.addon)
        cmd = [
            "helm", "--kube-context", KUBE_CONTEXT, "upgrade", "--install", self.addon, self.addon,
            "--repo", self.repo, "--version", self.version,
            "-n", self.namespace, "--create-namespace",
            "-f", str(values), "--wait", "--timeout", "600s",
        ]  # fmt: skip
        self._run(cmd)
        return f"chart {self.version} in {self.namespace}"


class IngressReady(Step):
    name = "Ingress controller ready"

    def __init__(self, run: shell.Runner) -> None:
        super().__init__()
        self._run = run

    def run(self, ctx: Context) -> str | None:
        self._run(
            [
                "kubectl",
                "--context",
                KUBE_CONTEXT,
                "-n",
                "ingress-nginx",
                "wait",
                "pod",
                "-l",
                "app.kubernetes.io/component=controller",
                "--for=condition=Ready",
                "--timeout=180s",
            ]  # fmt: skip
        )
        return "http://*.<env>.127.0.0.1.nip.io"


class ApplyGitOpsConfig(Step):
    name = "GitOps project and ApplicationSet applied"

    def __init__(self, run: shell.Runner) -> None:
        super().__init__()
        self._run = run

    def run(self, ctx: Context) -> str | None:
        manifests = paths.repo_root() / "deploy" / "argocd"
        self._run(["kubectl", "--context", KUBE_CONTEXT, "apply", "-f", str(manifests)])
        return "deploy/argocd"


class ApplyObservabilityConfig(Step):
    """Jaeger, plus Grafana dashboards shipped as labelled ConfigMaps."""

    name = "Observability config applied"

    def __init__(self, run: shell.Runner) -> None:
        super().__init__()
        self._run = run

    def run(self, ctx: Context) -> str | None:
        base = paths.repo_root() / "deploy" / "observability"
        kubectl = ["kubectl", "--context", KUBE_CONTEXT]
        for manifest in sorted(base.glob("*.yaml")):
            self._run([*kubectl, "apply", "-f", str(manifest)])
        dashboards = sorted((base / "dashboards").glob("*.json"))
        for dash in dashboards:
            name = f"dashboard-{dash.stem}"
            render = self._run(
                [
                    *kubectl,
                    "-n",
                    OBSERVABILITY_NAMESPACE,
                    "create",
                    "configmap",
                    name,
                    f"--from-file={dash.name}={dash}",
                    "--dry-run=client",
                    "-o",
                    "yaml",
                ]  # fmt: skip
            )
            labelled = render.stdout.replace(
                "metadata:\n", 'metadata:\n  labels:\n    grafana_dashboard: "1"\n', 1
            )
            self._run([*kubectl, "apply", "-f", "-"], input=labelled)
        return f"jaeger + {len(dashboards)} dashboard(s)"


class DeleteCluster(Step):
    name = "kind cluster deleted"

    def __init__(self, run: shell.Runner) -> None:
        super().__init__()
        self._run = run

    def run(self, ctx: Context) -> str | None:
        if not cluster_exists(self._run):
            raise StepError(f"kind cluster {CLUSTER_NAME!r} does not exist")
        self._run(["kind", "delete", "cluster", "--name", CLUSTER_NAME])
        return CLUSTER_NAME


def up_steps(run: shell.Runner = shell.run) -> list[Step]:
    return [
        ToolsAvailable(),
        CreateCluster(run),
        InstallAddon(
            run, "ingress-nginx", INGRESS_NGINX_REPO, INGRESS_NGINX_CHART, "ingress-nginx"
        ),
        IngressReady(run),
        InstallAddon(
            run, "metrics-server", METRICS_SERVER_REPO, METRICS_SERVER_CHART, "kube-system"
        ),
        InstallAddon(run, "argo-cd", ARGOCD_REPO, ARGOCD_CHART, "argocd"),
        ApplyGitOpsConfig(run),
        InstallAddon(
            run,
            "kube-prometheus-stack",
            KUBE_PROMETHEUS_STACK_REPO,
            KUBE_PROMETHEUS_STACK_CHART,
            OBSERVABILITY_NAMESPACE,
        ),  # fmt: skip
        InstallAddon(
            run,
            "opentelemetry-collector",
            OTEL_COLLECTOR_REPO,
            OTEL_COLLECTOR_CHART,
            OBSERVABILITY_NAMESPACE,
        ),  # fmt: skip
        ApplyObservabilityConfig(run),
    ]


def down_steps(run: shell.Runner = shell.run) -> list[Step]:
    return [ToolsAvailable(), DeleteCluster(run)]
