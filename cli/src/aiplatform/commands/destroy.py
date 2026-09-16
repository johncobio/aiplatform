"""`aiplatform destroy`: remove the running workload from the target."""

from aiplatform.commands.common import (
    DirOption,
    EnvOption,
    TargetOption,
    build_context,
    exit_for,
    fail,
    resolve_target,
    run_pipeline,
)
from aiplatform.errors import AiPlatformError


def destroy(
    directory: DirOption = None, target: TargetOption = "local", env: EnvOption = None
) -> None:
    """Tear down the workload on the target (keeps release history)."""
    try:
        ctx = build_context(directory, environment=env)
        steps = resolve_target(target).destroy_steps(ctx)
    except AiPlatformError as e:
        fail(e)
        return
    exit_for(run_pipeline(steps, ctx))
