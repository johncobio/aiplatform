"""`aiplatform logs`: stream workload logs from the target."""

from typing import Annotated

import typer

from aiplatform.commands.common import DirOption, TargetOption, build_context, fail, resolve_target
from aiplatform.errors import AiPlatformError


def logs(
    directory: DirOption = None,
    target: TargetOption = "local",
    follow: Annotated[bool, typer.Option("--follow", "-f", help="Stream new log lines")] = False,
    tail: Annotated[int, typer.Option(help="Number of recent lines to show")] = 100,
) -> None:
    """Show logs for the deployed workload."""
    try:
        ctx = build_context(directory)
        resolve_target(target).logs(ctx, follow=follow, tail=tail)
    except AiPlatformError as e:
        fail(e)
    except KeyboardInterrupt:
        pass
