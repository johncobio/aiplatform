"""`aiplatform guard`: run the proposal guardrails against the current checkout."""

from typing import Annotated

import typer

from aiplatform.agent import guardrails
from aiplatform.commands.common import console, exit_for, fail, run_pipeline
from aiplatform.errors import AiPlatformError
from aiplatform.paths import repo_root
from aiplatform.shell import run as shell_run


def guard(
    budget: Annotated[float | None, typer.Option(help="Monthly budget in USD")] = None,
    base: Annotated[
        str, typer.Option(help="Compare against this ref to find changed files")
    ] = "main",
    all_files: Annotated[
        bool, typer.Option("--all", help="Check everything, not only changed files")
    ] = False,
) -> None:
    """Run terraform/Checkov/OPA/cost guardrails on the working tree (what CI runs on PRs)."""
    try:
        repo = repo_root()
    except AiPlatformError as e:
        fail(e)
        return
    if all_files:
        changed = [
            str(p.relative_to(repo))
            for p in repo.rglob("*")
            if p.is_file() and ".git" not in p.parts
        ]
    else:
        changed = guardrails.changed_files(shell_run, repo, base)
    console.print(
        f"[dim]{len(changed)} changed file(s) vs {base}[/dim]"
        if not all_files
        else "[dim]all files[/dim]"
    )
    ctx = {"repo": repo, "worktree": repo, "changed": changed, "budget": budget}
    result = run_pipeline(guardrails.guard_steps(shell_run), ctx)
    if ctx.get("cost"):
        console.print(ctx["cost"].markdown())
    exit_for(result)
