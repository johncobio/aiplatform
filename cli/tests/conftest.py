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
        joined = " ".join(cmd)
        failure = self._match(self.failures, joined)
        if failure is not None:
            from aiplatform.errors import CommandError

            if kwargs.get("check", True):
                raise CommandError(cmd, failure, "simulated failure")
            return subprocess.CompletedProcess(cmd, failure, stdout="", stderr="simulated failure")
        stdout = self._match(self.responses, joined) or ""
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")

    @staticmethod
    def _match(table, joined):
        """Longest key that is a prefix of the joined command wins."""
        for key in sorted(table, key=len, reverse=True):
            if joined.startswith(key):
                return table[key]
        return None

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
