"""`kind` target: deploy to a local kind cluster with the llm-workload Helm chart.

The Helm chart is the deployment contract; the future `eks` target reuses it
and differs only in how the image reaches the cluster (ECR push instead of
`kind load`) and in environment values (ingress class, storage class).
"""

import json
import logging
from collections.abc import Callable

import yaml

from aiplatform import http, paths, shell
from aiplatform.config.quantity import format_memory
from aiplatform.config.schema import WorkloadConfig
from aiplatform.errors import StepError, TargetError
from aiplatform.steps.docker import BuildImageStep, DockerAvailableStep
from aiplatform.steps.health import HealthCheckStep
from aiplatform.steps.pipeline import Context, Step
from aiplatform.steps.record import RecordReleaseStep
from aiplatform.targets.base import Target, TargetStatus

log = logging.getLogger(__name__)

CLUSTER_NAME = "aiplatform"
KUBE_CONTEXT = f"kind-{CLUSTER_NAME}"
LOCAL_DOMAIN = "127.0.0.1.nip.io"  # resolves to the laptop; stands in for a real DNS name


def namespace_for(environment: str) -> str:
    return f"aiplatform-{environment}"


def ingress_host(cfg: WorkloadConfig) -> str:
    return f"{cfg.name}.{cfg.environment}.{LOCAL_DOMAIN}"


def _number(value: float) -> int | float:
    return int(value) if float(value).is_integer() else value


def format_cpu(cores: float) -> str:
    """Kubernetes CPU quantity: whole cores as '2', fractions as millicores '500m'."""
    if cores == int(cores):
        return str(int(cores))
    return f"{int(round(cores * 1000))}m"


def build_values(cfg: WorkloadConfig, image: str, tag: str) -> dict:
    """Translate aiplatform.yaml into chart values.

    Requests are half the CPU limit (bursting allowed) and equal to the memory
    limit (models must not be OOM-killed under pressure).
    """
    spec = cfg.model_spec
    repository, _, _ = image.rpartition(":")
    values: dict = {
        "nameOverride": cfg.name,
        "environment": cfg.environment,
        "engine": {"type": cfg.engine_type},
        "port": cfg.port,
        "model": {
            "backend": spec.backend,
            "name": spec.name,
            "url": spec.artifact_url,
            "hfRepo": spec.hf_repo,
            "contextLength": spec.context_length,
            "threads": max(1, int(cfg.cpu_cores)),
        },
        "env": dict(cfg.env),
        "resources": {
            "requests": {
                "cpu": format_cpu(max(0.1, cfg.cpu_cores / 2)),
                "memory": format_memory(cfg.memory_bytes),
            },
            "limits": {
                "cpu": format_cpu(cfg.cpu_cores),
                "memory": format_memory(cfg.memory_bytes),
            },
        },
        "replicaCount": max(1, cfg.autoscaling.min),
        "autoscaling": {
            "enabled": cfg.autoscaling.max > 1,
            "minReplicas": max(1, cfg.autoscaling.min),
            "maxReplicas": cfg.autoscaling.max,
            "metric": cfg.autoscaling.metric,
            "target": _number(cfg.autoscaling.effective_target),
        },
        "ingress": {"host": ingress_host(cfg)},
    }
    if cfg.builds_image:
        values["image"] = {"repository": repository, "tag": tag}
    return values


class EngineImageStep(Step):
    """Upstream engines ship their own image; nothing to build, load or push."""

    name = "Engine image resolved"

    def run(self, ctx: Context) -> str | None:
        cfg: WorkloadConfig = ctx["config"]
        ctx["image"] = f"engine/{cfg.engine_type}"
        ctx["tag"] = cfg.engine_type
        return f"{cfg.engine_type} (upstream image pinned in the chart)"


class KindTarget(Target):
    name = "kind"

    def __init__(
        self,
        runner: shell.Runner = shell.run,
        wait_for_http: Callable[..., float] = http.wait_for_http,
        probe: Callable[[str], tuple[int, str]] = http.probe,
    ) -> None:
        self._run = runner
        self._wait = wait_for_http
        self._probe = probe

    # Steps ---------------------------------------------------------------

    def deploy_steps(self, ctx: Context) -> list[Step]:
        cfg: WorkloadConfig = ctx["config"]
        if cfg.model_spec.requires_gpu:
            raise TargetError(f"model {cfg.model!r} requires a GPU; kind clusters are CPU-only")
        image_steps: list[Step] = (
            [DockerAvailableStep(self._run), BuildImageStep(self._run), _LoadImage(self)]
            if cfg.builds_image
            else [EngineImageStep()]
        )
        return [
            _ClusterReachable(self),
            *image_steps,
            _HelmUpgrade(self),
            _RolloutStatus(self),
            HealthCheckStep(self._wait),
            RecordReleaseStep(self.name),
        ]

    def rollback_steps(self, ctx: Context) -> list[Step]:
        return [
            _ClusterReachable(self),
            _HelmRollback(self),
            _RolloutStatus(self),
            HealthCheckStep(self._wait),
            RecordReleaseStep(self.name),
        ]

    def destroy_steps(self, ctx: Context) -> list[Step]:
        return [_ClusterReachable(self), _HelmUninstall(self)]

    # Queries -------------------------------------------------------------

    def status(self, ctx: Context) -> TargetStatus:
        cfg: WorkloadConfig = ctx["config"]
        endpoint = f"http://{ingress_host(cfg)}"
        proc = self._run(
            self.kubectl(cfg, "get", "deployment", cfg.name, "-o", "json"), check=False
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return TargetStatus(running=False, ready=False, detail="deployment not found")
        info = json.loads(proc.stdout)
        st = info.get("status", {})
        desired = info["spec"].get("replicas", 0)
        ready = st.get("readyReplicas", 0)
        image = info["spec"]["template"]["spec"]["containers"][0]["image"]
        code, body = self._probe(f"{endpoint}/readyz") if ready else (0, "")
        return TargetStatus(
            running=ready > 0,
            ready=code == 200,
            image=image,
            started_at=info["metadata"].get("creationTimestamp", ""),
            endpoint=endpoint,
            detail=f"{ready}/{desired} replicas ready"
            + (f" · {body.strip()[:80]}" if body else ""),
        )

    def logs(self, ctx: Context, follow: bool, tail: int) -> None:
        cfg: WorkloadConfig = ctx["config"]
        cmd = self.kubectl(
            cfg, "logs", "-l", f"app.kubernetes.io/instance={cfg.name}",
            "--all-containers", "--prefix", "--tail", str(tail),
        )  # fmt: skip
        if follow:
            cmd.append("--follow")
        self._run(cmd, capture=False)

    # Helpers -------------------------------------------------------------

    def kubectl(self, cfg: WorkloadConfig, *args: str) -> list[str]:
        return ["kubectl", "--context", KUBE_CONTEXT, "-n", namespace_for(cfg.environment), *args]

    def helm(self, cfg: WorkloadConfig, *args: str) -> list[str]:
        return ["helm", "--kube-context", KUBE_CONTEXT, "-n", namespace_for(cfg.environment), *args]

    def current_image(self, cfg: WorkloadConfig) -> str:
        proc = self._run(
            self.kubectl(
                cfg,
                "get",
                "deployment",
                cfg.name,
                "-o",
                "jsonpath={.spec.template.spec.containers[0].image}",
            )  # fmt: skip
        )
        return proc.stdout.strip()


class _ClusterReachable(Step):
    name = "Kubernetes cluster reachable"

    def __init__(self, target: KindTarget) -> None:
        super().__init__()
        self.t = target

    def run(self, ctx: Context) -> str | None:
        for tool in ("kind", "kubectl", "helm"):
            shell.require(tool, "Install it with `brew install " + tool + "`.")
        proc = self.t._run(["kind", "get", "clusters"], check=False)
        if CLUSTER_NAME not in proc.stdout.split():
            raise StepError(f"kind cluster {CLUSTER_NAME!r} not found; run `aiplatform cluster up`")
        proc = self.t._run(
            ["kubectl", "--context", KUBE_CONTEXT, "get", "nodes", "-o", "name"], check=False
        )
        if proc.returncode != 0:
            raise StepError(
                f"cannot reach cluster via context {KUBE_CONTEXT}: {proc.stderr.strip()}"
            )
        return f"{KUBE_CONTEXT}, {len(proc.stdout.split())} node(s)"


class _LoadImage(Step):
    name = "Image loaded into cluster"

    def __init__(self, target: KindTarget) -> None:
        super().__init__()
        self.t = target

    def run(self, ctx: Context) -> str | None:
        self.t._run(["kind", "load", "docker-image", ctx["image"], "--name", CLUSTER_NAME])
        return ctx["image"]


class _HelmUpgrade(Step):
    name = "Helm release upgraded"

    def __init__(self, target: KindTarget) -> None:
        super().__init__()
        self.t = target

    def run(self, ctx: Context) -> str | None:
        cfg: WorkloadConfig = ctx["config"]
        values = build_values(cfg, ctx["image"], ctx["tag"])
        generated = (
            ctx["workload_dir"] / ".aiplatform" / cfg.environment / f"{cfg.name}.values.yaml"
        )
        generated.parent.mkdir(parents=True, exist_ok=True)
        generated.write_text(yaml.safe_dump(values, sort_keys=False))

        env_values = paths.env_values_path(cfg.environment)
        if not env_values.is_file():
            raise StepError(f"no environment values for {cfg.environment!r}: {env_values}")

        cmd = self.t.helm(
            cfg, "upgrade", "--install", cfg.name, str(paths.chart_path()),
            "--create-namespace",
            "-f", str(env_values),
            "-f", str(generated),
            "--history-max", "10",
        )  # fmt: skip
        self.t._run(cmd)
        ctx["endpoint"] = f"http://{ingress_host(cfg)}"
        ctx["namespace"] = namespace_for(cfg.environment)
        return f"{cfg.name} in {ctx['namespace']}"


class _RolloutStatus(Step):
    name = "Rollout complete"

    def __init__(self, target: KindTarget) -> None:
        super().__init__()
        self.t = target

    def run(self, ctx: Context) -> str | None:
        cfg: WorkloadConfig = ctx["config"]
        timeout = int(ctx.get("timeout", 600))
        self.t._run(
            self.t.kubectl(
                cfg, "rollout", "status", f"deployment/{cfg.name}", f"--timeout={timeout}s"
            )
        )
        proc = self.t._run(
            self.t.kubectl(
                cfg, "get", "deployment", cfg.name, "-o", "jsonpath={.status.readyReplicas}"
            ),
            check=False,
        )
        return f"{proc.stdout.strip() or '?'} replica(s) ready"


class _HelmRollback(Step):
    name = "Helm release rolled back"

    def __init__(self, target: KindTarget) -> None:
        super().__init__()
        self.t = target

    def run(self, ctx: Context) -> str | None:
        cfg: WorkloadConfig = ctx["config"]
        proc = self.t._run(self.t.helm(cfg, "history", cfg.name, "-o", "json"), check=False)
        if proc.returncode != 0:
            raise StepError(f"no Helm release {cfg.name!r} in {namespace_for(cfg.environment)}")
        history = json.loads(proc.stdout or "[]")
        if len(history) < 2:
            raise StepError("no previous Helm revision to roll back to")
        target_rev = history[-2]["revision"]
        self.t._run(self.t.helm(cfg, "rollback", cfg.name, str(target_rev), "--history-max", "10"))
        image = self.t.current_image(cfg)
        ctx["image"], ctx["tag"] = image, image.rpartition(":")[2]
        ctx["endpoint"] = f"http://{ingress_host(cfg)}"
        return f"revision {target_rev} → {image}"


class _HelmUninstall(Step):
    name = "Helm release removed"

    def __init__(self, target: KindTarget) -> None:
        super().__init__()
        self.t = target

    def run(self, ctx: Context) -> str | None:
        cfg: WorkloadConfig = ctx["config"]
        self.t._run(self.t.helm(cfg, "uninstall", cfg.name, "--ignore-not-found"))
        ctx["state"].clear_current(cfg.environment, cfg.name)
        return f"{cfg.name} from {namespace_for(cfg.environment)}"
