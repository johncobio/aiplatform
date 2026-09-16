"""Docker steps shared by targets that build images locally."""

import subprocess
import time
from pathlib import Path

from aiplatform import shell
from aiplatform.config.schema import WorkloadConfig
from aiplatform.errors import StepError
from aiplatform.steps.pipeline import Context, Step


def image_tag() -> str:
    """Timestamp plus short git SHA when available: sortable and traceable."""
    ts = time.strftime("%Y%m%d-%H%M%S")
    try:
        sha = subprocess.run(  # noqa: S603,S607
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
        ).stdout.strip()
    except OSError:
        sha = ""
    return f"{ts}-{sha}" if sha else ts


def image_name(cfg: WorkloadConfig, tag: str, registry: str = "") -> str:
    prefix = f"{registry.rstrip('/')}/" if registry else ""
    return f"{prefix}aiplatform/{cfg.name}:{tag}"


class DockerAvailableStep(Step):
    name = "Docker available"

    def __init__(self, runner: shell.Runner = shell.run) -> None:
        super().__init__()
        self._run = runner

    def run(self, ctx: Context) -> str | None:
        shell.require("docker", "Install Docker Desktop and make sure it is running.")
        proc = self._run(["docker", "info", "--format", "{{.ServerVersion}}"], check=False)
        if proc.returncode != 0:
            raise StepError("docker daemon is not reachable; is Docker Desktop running?")
        return proc.stdout.strip() or None


class BuildImageStep(Step):
    name = "Docker image built"

    def __init__(self, runner: shell.Runner = shell.run, registry: str = "") -> None:
        super().__init__()
        self._run = runner
        self.registry = registry

    def run(self, ctx: Context) -> str | None:
        cfg: WorkloadConfig = ctx["config"]
        context_dir = (Path(ctx["workload_dir"]) / cfg.context).resolve()
        if not (context_dir / "Dockerfile").is_file():
            raise StepError(f"no Dockerfile in build context {context_dir}")
        tag = image_tag()
        image = image_name(cfg, tag, self.registry)
        self._run(["docker", "build", "-t", image, str(context_dir)])
        ctx["image"], ctx["tag"] = image, tag
        return image
