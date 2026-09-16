"""Shared helpers for command modules: option types, context building, exits."""

import logging
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from aiplatform.config import find_config, load_config
from aiplatform.errors import AiPlatformError
from aiplatform.state import StateStore
from aiplatform.steps.pipeline import Context, Pipeline, PipelineResult, Step
from aiplatform.steps.reporter import ConsoleReporter
from aiplatform.targets import Target, get_target

log = logging.getLogger(__name__)
console = Console()
err_console = Console(stderr=True)

DirOption = Annotated[
    Path,
    typer.Option("--dir", "-C", help="Directory containing aiplatform.yaml", show_default="cwd"),
]
TargetOption = Annotated[str, typer.Option("--target", "-t", help="Deployment target")]
EnvOption = Annotated[
    str | None,
    typer.Option("--env", "-e", help="Override `environment` from aiplatform.yaml"),
]
ImageTagOption = Annotated[
    str | None,
    typer.Option(
        "--image-tag", help="Deploy an existing image tag instead of the default (gitops)"
    ),
]
TimeoutOption = Annotated[
    int,
    typer.Option("--timeout", help="Seconds to wait for readiness (first run downloads the model)"),
]


def build_context(
    directory: Path | None,
    timeout: int = 600,
    environment: str | None = None,
    image_tag: str | None = None,
) -> Context:
    workload_dir = (directory or Path.cwd()).resolve()
    path = find_config(workload_dir)
    config = load_config(path)
    if environment and environment != config.environment:
        config = load_config_override(config, environment)
    return {
        "image_tag": image_tag,
        "config": config,
        "config_path": path,
        "workload_dir": workload_dir,
        "state": StateStore(workload_dir / ".aiplatform"),
        "timeout": timeout,
    }


def load_config_override(config, environment: str):
    from pydantic import ValidationError

    from aiplatform.config.schema import WorkloadConfig
    from aiplatform.errors import ConfigError

    try:
        return WorkloadConfig.model_validate({**config.model_dump(), "environment": environment})
    except ValidationError as e:
        raise ConfigError(f"--env {environment!r}: {e.errors()[0]['msg']}") from None


def resolve_target(name: str) -> Target:
    return get_target(name)


def run_pipeline(steps: list[Step], ctx: Context) -> PipelineResult:
    reporter = ConsoleReporter(console=console, show_timing=log.isEnabledFor(logging.DEBUG))
    return Pipeline(reporter=reporter).run(steps, ctx)


def fail(err: AiPlatformError | str, code: int = 1) -> None:
    message = str(err)
    err_console.print(f"[red]error:[/red] {message}", highlight=False)
    raise typer.Exit(code=getattr(err, "exit_code", code))


def exit_for(result: PipelineResult) -> None:
    if not result.succeeded:
        raise typer.Exit(code=3)
