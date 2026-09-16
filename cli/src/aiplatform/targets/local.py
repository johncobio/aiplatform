"""`local` target: run the workload as a Docker container on this machine.

Mirrors what the Kubernetes targets do (build, run with resource limits,
readiness gate) so the developer experience is identical across targets.
"""

import json
import logging
from collections.abc import Callable
from pathlib import Path

from aiplatform import http, shell
from aiplatform.config.schema import WorkloadConfig
from aiplatform.errors import StepError, TargetError
from aiplatform.state import StateStore
from aiplatform.steps.docker import BuildImageStep, DockerAvailableStep
from aiplatform.steps.health import HealthCheckStep
from aiplatform.steps.pipeline import Context, Step
from aiplatform.steps.record import RecordReleaseStep
from aiplatform.targets.base import Target, TargetStatus

log = logging.getLogger(__name__)

MODEL_CACHE_DIR = Path.home() / ".aiplatform" / "models"
CONTAINER_MODEL_DIR = "/models"


def _container_name(cfg: WorkloadConfig) -> str:
    return f"aiplatform-{cfg.environment}-{cfg.name}"


class LocalDockerTarget(Target):
    name = "local"

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
            raise TargetError(f"model {cfg.model!r} requires a GPU; the local target is CPU-only")
        return [
            DockerAvailableStep(self._run),
            BuildImageStep(self._run),
            _Run(self),
            HealthCheckStep(self._wait),
            RecordReleaseStep(self.name),
        ]

    def rollback_steps(self, ctx: Context) -> list[Step]:
        return [
            DockerAvailableStep(self._run),
            _SelectPrevious(),
            _Run(self),
            HealthCheckStep(self._wait),
            RecordReleaseStep(self.name),
        ]

    def destroy_steps(self, ctx: Context) -> list[Step]:
        return [DockerAvailableStep(self._run), _Remove(self)]

    # Queries -------------------------------------------------------------

    def status(self, ctx: Context) -> TargetStatus:
        cfg: WorkloadConfig = ctx["config"]
        endpoint = f"http://localhost:{cfg.port}"
        proc = self._run(["docker", "inspect", _container_name(cfg)], check=False)
        if proc.returncode != 0 or not proc.stdout.strip():
            return TargetStatus(running=False, ready=False, detail="container not found")
        info = json.loads(proc.stdout)[0]
        running = info["State"]["Status"] == "running"
        code, body = self._probe(f"{endpoint}/readyz") if running else (0, "")
        return TargetStatus(
            running=running,
            ready=code == 200,
            image=info["Config"]["Image"],
            started_at=info["State"].get("StartedAt", ""),
            endpoint=endpoint,
            detail=info["State"]["Status"] if not running else body.strip()[:120],
        )

    def logs(self, ctx: Context, follow: bool, tail: int) -> None:
        cfg: WorkloadConfig = ctx["config"]
        cmd = ["docker", "logs", "--tail", str(tail)]
        if follow:
            cmd.append("--follow")
        cmd.append(_container_name(cfg))
        self._run(cmd, capture=False)

    # Internals used by steps --------------------------------------------

    def run_container(self, ctx: Context, image: str) -> None:
        cfg: WorkloadConfig = ctx["config"]
        spec = cfg.model_spec
        name = _container_name(cfg)
        self._run(["docker", "rm", "-f", name], check=False)
        MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        env = {
            "LLM_BACKEND": spec.backend,
            "LLM_MODEL_NAME": spec.name,
            "LLM_MODEL_URL": spec.artifact_url,
            "LLM_MODEL_DIR": CONTAINER_MODEL_DIR,
            "LLM_CONTEXT_LENGTH": str(spec.context_length),
            "LLM_THREADS": str(max(1, int(cfg.cpu_cores))),
            "PORT": str(cfg.port),
            **cfg.env,
        }
        cmd = [
            "docker", "run", "--detach",
            "--name", name,
            "--label", "aiplatform.workload=" + cfg.name,
            "--label", "aiplatform.environment=" + cfg.environment,
            "--label", "aiplatform.image=" + image,
            "--cpus", f"{cfg.cpu_cores:g}",
            "--memory", str(cfg.memory_bytes),
            "-p", f"{cfg.port}:{cfg.port}",
            "-v", f"{MODEL_CACHE_DIR}:{CONTAINER_MODEL_DIR}",
            "--restart", "unless-stopped",
        ]  # fmt: skip
        for k, v in env.items():
            cmd += ["-e", f"{k}={v}"]
        cmd.append(image)
        self._run(cmd)
        ctx["container"] = name
        ctx["endpoint"] = f"http://localhost:{cfg.port}"


class _SelectPrevious(Step):
    name = "Previous release selected"

    def run(self, ctx: Context) -> str | None:
        cfg: WorkloadConfig = ctx["config"]
        state: StateStore = ctx["state"]
        prev = state.load(cfg.environment, cfg.name).previous()
        if prev is None:
            raise StepError("no previous release to roll back to")
        ctx["image"], ctx["tag"] = prev.image, prev.tag
        return prev.image


class _Run(Step):
    name = "Container started"

    def __init__(self, target: LocalDockerTarget) -> None:
        super().__init__()
        self.t = target

    def run(self, ctx: Context) -> str | None:
        self.t.run_container(ctx, ctx["image"])
        return ctx["container"]


class _Remove(Step):
    name = "Container removed"

    def __init__(self, target: LocalDockerTarget) -> None:
        super().__init__()
        self.t = target

    def run(self, ctx: Context) -> str | None:
        cfg: WorkloadConfig = ctx["config"]
        name = _container_name(cfg)
        self.t._run(["docker", "rm", "-f", name], check=False)
        ctx["state"].clear_current(cfg.environment, cfg.name)
        return name
