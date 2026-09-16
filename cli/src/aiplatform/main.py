"""Typer application wiring the command modules together."""

from typing import Annotated

import typer

from aiplatform import __version__
from aiplatform.commands import (
    cluster,
    deploy,
    destroy,
    init,
    logs,
    models,
    rollback,
    status,
    validate,
)
from aiplatform.logging import configure_logging

app = typer.Typer(
    name="aiplatform",
    help="Self-service platform for deploying containerized LLM workloads.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


def _version(value: bool) -> None:
    if value:
        typer.echo(f"aiplatform {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show step details and commands")
    ] = False,
    version: Annotated[
        bool, typer.Option("--version", callback=_version, is_eager=True, help="Print version")
    ] = False,
) -> None:
    configure_logging(verbose)


app.command()(init.init)
app.command()(validate.validate)
app.command()(deploy.deploy)
app.command()(status.status)
app.command()(logs.logs)
app.command()(rollback.rollback)
app.command()(destroy.destroy)
app.command()(models.models)
app.add_typer(cluster.app, name="cluster")

if __name__ == "__main__":
    app()
