"""`aiplatform propose`: natural language → proposed changes → guardrails → pull request."""

import re
from pathlib import Path
from typing import Annotated

import typer

from aiplatform.agent import guardrails, report
from aiplatform.agent.pr import OpenPullRequestStep
from aiplatform.agent.providers import ClaudeProvider, FileProvider
from aiplatform.commands.common import console, err_console, fail, run_pipeline
from aiplatform.errors import AiPlatformError
from aiplatform.paths import repo_root
from aiplatform.shell import run as shell_run


def propose(
    request: Annotated[str, typer.Argument(help="What you want, in plain language")],
    from_file: Annotated[
        Path | None, typer.Option("--from-file", help="Use a JSON Proposal instead of the model")
    ] = None,
    budget: Annotated[
        float | None, typer.Option(help="Monthly budget in USD (default: policy/data/limits.yaml)")
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Run guardrails, write the report, open no PR")
    ] = False,
    model: Annotated[str, typer.Option(help="Claude model id")] = "claude-opus-5",
    base: Annotated[str, typer.Option(help="Base branch for the PR")] = "main",
) -> None:
    """Propose infrastructure changes with guardrails and a pull request for human approval."""
    try:
        repo = repo_root()
        provider = FileProvider(from_file) if from_file else ClaudeProvider(model=model)
        console.print(f"[dim]provider: {provider.name}[/dim]")
        from aiplatform.agent.context import build_context

        proposal = provider.propose(request, build_context(repo))
    except AiPlatformError as e:
        fail(e)
        return
    console.print(f"[bold]{proposal.summary}[/bold]")
    for f in proposal.files:
        console.print(f"  • {f.path} ({f.action})")

    slug = re.sub(r"[^a-z0-9]+", "-", proposal.summary.lower()).strip("-")[:40] or "change"
    scratch = repo / ".aiplatform" / "proposals"
    scratch.mkdir(parents=True, exist_ok=True)
    ctx = {
        "proposal": proposal,
        "repo": repo,
        "slug": slug,
        "scratch": scratch,
        "budget": budget,
        "base": base,
    }
    steps = [guardrails.ApplyProposalStep(shell_run), *guardrails.guard_steps(shell_run)]
    result = run_pipeline(steps, ctx)

    body = report.render(request, proposal, ctx, provider.name)
    ctx["pr_body"] = body
    report_path = scratch / f"{slug}.md"
    report_path.write_text(body)
    console.print(f"[dim]report: {report_path}[/dim]")

    if not result.succeeded:
        err_console.print("[red]guardrails failed; no pull request opened[/red]")
        if ctx.get("worktree"):
            guardrails.worktree_cleanup(shell_run, repo, ctx["worktree"], ctx.get("branch"))
        raise typer.Exit(code=3)
    if dry_run:
        console.print("[yellow]dry run: guardrails passed, no pull request opened[/yellow]")
        guardrails.worktree_cleanup(shell_run, repo, ctx["worktree"], ctx.get("branch"))
        return
    pr = run_pipeline([OpenPullRequestStep(shell_run)], ctx)
    guardrails.worktree_cleanup(shell_run, repo, ctx["worktree"], ctx.get("branch"))
    if pr.succeeded:
        console.print(f"\nReview and merge to apply: [bold]{ctx.get('pr_url')}[/bold]")
    else:
        raise typer.Exit(code=3)
