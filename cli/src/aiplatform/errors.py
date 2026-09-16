"""Typed errors. Library code raises these; the CLI turns them into messages."""


class AiPlatformError(Exception):
    """Base class for all platform errors."""

    exit_code = 1


class ConfigError(AiPlatformError):
    """The workload configuration is missing or invalid."""

    exit_code = 2


class StepError(AiPlatformError):
    """A pipeline step failed for an expected reason."""

    exit_code = 3


class CommandError(StepError):
    """An external command (docker, terraform, ...) exited non-zero."""

    def __init__(self, cmd: list[str], returncode: int, stderr: str = "") -> None:
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr.strip()
        tail = f": {self.stderr[-800:]}" if self.stderr else ""
        super().__init__(f"`{' '.join(cmd)}` exited with {returncode}{tail}")


class TargetError(AiPlatformError):
    """A deployment target cannot satisfy the request."""

    exit_code = 4


class AgentError(AiPlatformError):
    """The proposal provider could not produce a usable proposal."""

    exit_code = 5
