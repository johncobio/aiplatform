"""Turn a validated proposal into a pull request: the human approval gate."""

from pathlib import Path

from aiplatform import shell
from aiplatform.errors import StepError
from aiplatform.steps.pipeline import Context, Step


class OpenPullRequestStep(Step):
    name = "Pull request opened for review"

    def __init__(self, run: shell.Runner = shell.run) -> None:
        super().__init__()
        self._run = run

    def run(self, ctx: Context) -> str | None:
        wt: Path = ctx["worktree"]
        proposal = ctx["proposal"]
        shell.require("gh", "Install the GitHub CLI: brew install gh")
        self._run(["git", "add", "-A"], cwd=str(wt))
        if (
            self._run(["git", "diff", "--cached", "--quiet"], cwd=str(wt), check=False).returncode
            == 0
        ):
            raise StepError("proposal produced no change relative to main")
        self._run(["git", "commit", "-q", "-m", f"propose: {proposal.summary}"], cwd=str(wt))
        self._run(["git", "push", "-q", "-u", "origin", ctx["branch"]], cwd=str(wt))
        body_file = wt / ".aiplatform" / "pr-body.md"
        body_file.parent.mkdir(parents=True, exist_ok=True)
        body_file.write_text(ctx["pr_body"])
        proc = self._run(
            [
                "gh",
                "pr",
                "create",
                "--base",
                ctx.get("base", "main"),
                "--head",
                ctx["branch"],
                "--title",
                f"propose: {proposal.summary}",
                "--body-file",
                str(body_file),
                "--label",
                "aiplatform-proposal",
            ],  # fmt: skip
            cwd=str(wt),
            check=False,
        )
        if proc.returncode != 0 and "label" in (proc.stderr or ""):
            proc = self._run(
                [
                    "gh",
                    "pr",
                    "create",
                    "--base",
                    ctx.get("base", "main"),
                    "--head",
                    ctx["branch"],
                    "--title",
                    f"propose: {proposal.summary}",
                    "--body-file",
                    str(body_file),
                ],  # fmt: skip
                cwd=str(wt),
            )
        elif proc.returncode != 0:
            raise StepError(proc.stderr.strip()[-300:])
        ctx["pr_url"] = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
        return ctx["pr_url"]
