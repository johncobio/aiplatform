"""Persist the release in local state so `status` and `rollback` work."""

from aiplatform.config.schema import WorkloadConfig
from aiplatform.state import Release, StateStore
from aiplatform.steps.pipeline import Context, Step


class RecordReleaseStep(Step):
    name = "Release recorded"

    def __init__(self, target_name: str) -> None:
        super().__init__()
        self.target_name = target_name

    def run(self, ctx: Context) -> str | None:
        cfg: WorkloadConfig = ctx["config"]
        state: StateStore = ctx["state"]
        state.record(
            cfg.environment,
            cfg.name,
            Release(
                tag=ctx["tag"],
                image=ctx["image"],
                target=self.target_name,
                endpoint=ctx["endpoint"],
            ),
        )
        return ctx["tag"]
