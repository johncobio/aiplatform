"""A tiny, explicit step runner.

Every platform command is a list of `Step`s executed in order. The pipeline
owns reporting (the ✓/✗ checklist) and failure handling so individual steps
stay focused on one action.
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from aiplatform.errors import AiPlatformError

log = logging.getLogger(__name__)

Context = dict[str, Any]


class StepStatus(StrEnum):
    OK = "ok"
    FAILED = "failed"


class Step(ABC):
    """One unit of work. Subclasses set `name` and implement `run`."""

    name: str

    def __init__(self) -> None:
        if not getattr(self, "name", None):
            raise TypeError(f"{type(self).__name__} must define a non-empty `name`")

    @abstractmethod
    def run(self, ctx: Context) -> str | None:
        """Do the work. Return an optional short detail string for the report."""


class Reporter(Protocol):
    def step_started(self, name: str) -> None: ...

    def step_finished(
        self, name: str, status: StepStatus, detail: str | None, seconds: float
    ) -> None: ...


class NullReporter:
    def step_started(self, name: str) -> None:
        return None

    def step_finished(
        self, name: str, status: StepStatus, detail: str | None, seconds: float
    ) -> None:
        return None


@dataclass
class PipelineResult:
    succeeded: bool
    failed_step: str | None = None
    error: str | None = None
    total_seconds: float = 0.0


class Pipeline:
    def __init__(self, reporter: Reporter | None = None) -> None:
        self.reporter = reporter or NullReporter()

    def run(self, steps: list[Step], ctx: Context) -> PipelineResult:
        started = time.monotonic()
        for step in steps:
            self.reporter.step_started(step.name)
            t0 = time.monotonic()
            log.debug("step %s: start", step.name)
            try:
                detail = step.run(ctx)
            except AiPlatformError as e:
                return self._fail(step, str(e), t0, started)
            except Exception as e:  # noqa: BLE001 - a step must never crash the CLI
                log.debug("step %s: unexpected error", step.name, exc_info=True)
                return self._fail(step, f"{type(e).__name__}: {e}", t0, started)
            seconds = time.monotonic() - t0
            log.debug("step %s: ok in %.2fs", step.name, seconds)
            self.reporter.step_finished(step.name, StepStatus.OK, detail, seconds)
        return PipelineResult(succeeded=True, total_seconds=time.monotonic() - started)

    def _fail(self, step: Step, error: str, t0: float, started: float) -> PipelineResult:
        seconds = time.monotonic() - t0
        log.debug("step %s: failed in %.2fs: %s", step.name, seconds, error)
        self.reporter.step_finished(step.name, StepStatus.FAILED, error, seconds)
        return PipelineResult(
            succeeded=False,
            failed_step=step.name,
            error=error,
            total_seconds=time.monotonic() - started,
        )
