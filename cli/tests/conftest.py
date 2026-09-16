import subprocess
from dataclasses import dataclass, field

import pytest

from aiplatform.config.schema import WorkloadConfig


@dataclass
class FakeRunner:
    """Records commands and returns canned outputs by command prefix match."""

    responses: dict[str, str] = field(default_factory=dict)
    failures: dict[str, int] = field(default_factory=dict)
    calls: list[list[str]] = field(default_factory=list)

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        key = " ".join(cmd[:2])
        if key in self.failures:
            from aiplatform.errors import CommandError

            raise CommandError(cmd, self.failures[key], "simulated failure")
        return subprocess.CompletedProcess(cmd, 0, stdout=self.responses.get(key, ""), stderr="")

    def find(self, *prefix):
        return [c for c in self.calls if c[: len(prefix)] == list(prefix)]


@pytest.fixture
def runner():
    return FakeRunner()


@pytest.fixture
def config():
    return WorkloadConfig.model_validate(
        {
            "name": "demo",
            "model": "qwen2.5-0.5b-instruct",
            "cpu": "500m",
            "memory": "1Gi",
            "environment": "dev",
            "port": 8123,
            "env": {"LOG_LEVEL": "DEBUG"},
        }
    )
