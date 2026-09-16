"""`aiplatform validate`: check aiplatform.yaml and resolve the model catalog."""

from aiplatform.commands.common import DirOption, build_context, console, fail
from aiplatform.config.quantity import format_memory
from aiplatform.errors import AiPlatformError


def validate(directory: DirOption = None) -> None:
    """Validate the workload configuration without deploying anything."""
    try:
        ctx = build_context(directory)
    except AiPlatformError as e:
        fail(e)
        return
    cfg = ctx["config"]
    spec = cfg.model_spec
    console.print(f"[green]✓[/green] Configuration validated [dim]{ctx['config_path']}[/dim]")
    console.print(
        f"  {cfg.name} · {cfg.environment} · model {spec.name} ({spec.backend}) · "
        f"cpu {cfg.cpu_cores:g} · memory {format_memory(cfg.memory_bytes)} · "
        f"replicas {cfg.autoscaling.min}-{cfg.autoscaling.max}"
    )
