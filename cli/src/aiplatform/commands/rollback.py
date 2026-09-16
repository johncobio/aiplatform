"""`aiplatform rollback`: redeploy the previous release."""

from aiplatform.commands.common import (
    DirOption,
    EnvOption,
    ImageTagOption,
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


def rollback(
    directory: DirOption = None,
    target: TargetOption = "local",
    timeout: TimeoutOption = 600,
    env: EnvOption = None,
    image_tag: ImageTagOption = None,
) -> None:
    """Roll back to the previous release recorded for this workload."""
    try:
        ctx = build_context(directory, timeout=timeout, environment=env, image_tag=image_tag)
        steps = resolve_target(target).rollback_steps(ctx)
    except AiPlatformError as e:
        fail(e)
        return
    result = run_pipeline(steps, ctx)
    if result.succeeded:
        console.print(f"\nRolled back to [bold]{ctx['image']}[/bold] · {ctx['endpoint']}")
    exit_for(result)
