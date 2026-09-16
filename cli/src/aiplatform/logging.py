"""Logging setup for the CLI: human-readable, controlled by --verbose."""

import logging

from rich.logging import RichHandler


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=False, show_path=verbose, markup=False)],
        force=True,
    )
    # Only our own loggers at DEBUG; keep third parties quiet.
    logging.getLogger("aiplatform").setLevel(level)
