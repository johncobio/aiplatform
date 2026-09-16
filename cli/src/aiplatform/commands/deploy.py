"""`aiplatform deploy`: validate → build → run → health check."""

from aiplatform.commands.common import (
    DirOption,
    TargetOption,
    TimeoutOption,
    build_context,
    console,
    exit_for,
    fail,
    resolve_target,
    run_pipeline,
)
from aiplatform.errors import AiPlatformError
from aiplatform.steps.common import ResolveModelStep, ValidateConfigStep


def deploy(
    directory: DirOption = None,
    target: TargetOption = "local",
    timeout: TimeoutOption = 600,
) -> None:
    """Deploy the workload described by aiplatform.yaml."""
    try:
        ctx = build_context(directory, timeout=timeout)
        tgt = resolve_target(target)
        steps = [ValidateConfigStep(), ResolveModelStep()] + tgt.deploy_steps(ctx)
    except AiPlatformError as e:
        fail(e)
        return
    result = run_pipeline(steps, ctx)
    if result.succeeded:
        console.print()
        console.print(f"Endpoint: [bold]{ctx['endpoint']}[/bold]")
        console.print(
            f"[dim]Deployed in {result.total_seconds:.1f}s. "
            f"Try: curl {ctx['endpoint']}/v1/models[/dim]"
        )
    exit_for(result)
