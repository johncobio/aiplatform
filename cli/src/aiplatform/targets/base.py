"""Deployment target interface.

A target turns a validated workload config into running infrastructure. Each
operation is expressed as a list of steps so the CLI can render them uniformly.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from aiplatform.steps.pipeline import Context, Step


@dataclass
class TargetStatus:
    running: bool
    ready: bool
    image: str = ""
    started_at: str = ""
    endpoint: str = ""
    detail: str = ""


class Target(ABC):
    name: str
    supports_gpu: bool = False

    @abstractmethod
    def deploy_steps(self, ctx: Context) -> list[Step]: ...

    @abstractmethod
    def rollback_steps(self, ctx: Context) -> list[Step]: ...

    @abstractmethod
    def destroy_steps(self, ctx: Context) -> list[Step]: ...

    @abstractmethod
    def status(self, ctx: Context) -> TargetStatus: ...

    @abstractmethod
    def logs(self, ctx: Context, follow: bool, tail: int) -> None: ...
