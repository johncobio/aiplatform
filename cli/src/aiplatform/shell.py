"""Run external commands (docker, terraform, ...) with logging and typed errors."""

import logging
import shutil
import subprocess
from collections.abc import Callable

from aiplatform.errors import CommandError, StepError

log = logging.getLogger(__name__)

Runner = Callable[..., subprocess.CompletedProcess]


def run(
    cmd: list[str],
    *,
    check: bool = True,
    capture: bool = True,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Execute `cmd`. Raises CommandError on non-zero exit when `check` is set."""
    log.debug("$ %s", " ".join(cmd))
    proc = subprocess.run(  # noqa: S603 - argv list, no shell
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=capture,
        check=False,
    )
    if capture and proc.stdout:
        log.debug("stdout: %s", proc.stdout.strip()[-2000:])
    if capture and proc.stderr:
        log.debug("stderr: %s", proc.stderr.strip()[-2000:])
    if check and proc.returncode != 0:
        raise CommandError(cmd, proc.returncode, proc.stderr if capture else "")
    return proc


def require(binary: str, hint: str = "") -> None:
    """Fail early with a clear message when a required tool is missing."""
    if shutil.which(binary) is None:
        raise StepError(f"required tool `{binary}` not found on PATH. {hint}".strip())
