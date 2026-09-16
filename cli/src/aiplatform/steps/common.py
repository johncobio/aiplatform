"""Steps shared by every target."""

from aiplatform.config.quantity import format_memory
from aiplatform.steps.pipeline import Context, Step


class ValidateConfigStep(Step):
    """The config was already parsed to build the context; this step surfaces it."""

    name = "Configuration validated"

    def run(self, ctx: Context) -> str | None:
        cfg = ctx["config"]
        return f"{cfg.name} ({cfg.environment})"


class ResolveModelStep(Step):
    name = "Model resolved"

    def run(self, ctx: Context) -> str | None:
        spec = ctx["config"].model_spec
        return f"{spec.name} via {spec.backend}, needs ≥ {format_memory(spec.min_memory_bytes)}"
