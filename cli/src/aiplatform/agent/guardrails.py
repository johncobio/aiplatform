"""Guardrail steps every proposal passes before a human sees a pull request.

Steps that do not apply to the change set raise StepSkipped with a reason, so
the report is explicit about what was and was not checked.
"""

import contextlib
import os
import shutil
import subprocess
import time
from pathlib import Path

from aiplatform import shell
from aiplatform.agent.cost import estimate, load_limits
from aiplatform.agent.models import Proposal
from aiplatform.config.loader import load_config
from aiplatform.errors import ConfigError, StepError
from aiplatform.steps.pipeline import Context, Step, StepSkipped

ALLOWED_PREFIXES = (
    "services/",
    "deploy/workloads/",
    "deploy/environments/",
    "deploy/helm/llm-workload/values.yaml",
    "infra/terraform/",
)
FORBIDDEN_PREFIXES = (".github/", "policy/", "deploy/argocd/", "deploy/platform.yaml", ".checkov")


def _changed(ctx: Context) -> list[str]:
    return ctx.get("changed", [])


def _touches(ctx: Context, *prefixes: str, suffix: str | None = None) -> list[str]:
    return [
        p
        for p in _changed(ctx)
        if (not prefixes or p.startswith(prefixes)) and (suffix is None or p.endswith(suffix))
    ]


class ApplyProposalStep(Step):
    """Apply the proposal on a scratch git worktree so checks see the whole tree."""

    name = "Proposal applied to scratch branch"

    def __init__(self, run: shell.Runner = shell.run) -> None:
        super().__init__()
        self._run = run

    def run(self, ctx: Context) -> str | None:
        proposal: Proposal = ctx["proposal"]
        repo: Path = ctx["repo"]
        for change in proposal.files:
            if change.path.startswith(FORBIDDEN_PREFIXES) or ".." in change.path.split("/"):
                raise StepError(f"proposal touches a protected path: {change.path}")
            if not change.path.startswith(ALLOWED_PREFIXES):
                raise StepError(f"proposal touches a path outside the allowed areas: {change.path}")
            if change.action == "write" and change.content is None:
                raise StepError(f"proposal writes {change.path} without content")
        branch = ctx.get("branch") or f"propose/{ctx['slug']}-{time.strftime('%Y%m%d-%H%M%S')}"
        worktree = ctx.get("worktree") or Path(ctx["scratch"]) / branch.replace("/", "-")
        if worktree.exists():
            shutil.rmtree(worktree)
        self._run(
            ["git", "worktree", "add", "-b", branch, str(worktree), ctx.get("base", "main")],
            cwd=str(repo),
        )
        for change in proposal.files:
            target = worktree / change.path
            if change.action == "delete":
                target.unlink(missing_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(change.content or "")
        ctx["branch"], ctx["worktree"] = branch, worktree
        ctx["changed"] = [c.path for c in proposal.files]
        return f"{len(proposal.files)} file(s) on {branch}"


class WorkloadConfigStep(Step):
    name = "Workload configs validated"

    def run(self, ctx: Context) -> str | None:
        files = _touches(ctx, "services/", suffix="aiplatform.yaml")
        if not files:
            raise StepSkipped("no aiplatform.yaml changed")
        for rel in files:
            path = ctx["worktree"] / rel
            if not path.exists():
                continue
            try:
                load_config(path)
            except ConfigError as e:
                raise StepError(str(e)) from None
        return ", ".join(files)


class TerraformFmtStep(Step):
    name = "terraform fmt"

    def __init__(self, run: shell.Runner = shell.run) -> None:
        super().__init__()
        self._run = run

    def run(self, ctx: Context) -> str | None:
        if not _touches(ctx, "infra/terraform/", suffix=".tf"):
            raise StepSkipped("no .tf changed")
        shell.require("terraform")
        proc = self._run(
            ["terraform", "fmt", "-check", "-recursive", "infra/terraform"],
            cwd=str(ctx["worktree"]),
            check=False,
        )
        if proc.returncode != 0:
            raise StepError(f"unformatted: {proc.stdout.strip() or proc.stderr.strip()}")
        return "clean"


class TerraformValidateStep(Step):
    name = "terraform validate"

    def __init__(self, run: shell.Runner = shell.run) -> None:
        super().__init__()
        self._run = run

    def run(self, ctx: Context) -> str | None:
        tf_files = _touches(ctx, "infra/terraform/", suffix=".tf")
        if not tf_files:
            raise StepSkipped("no .tf changed")
        dirs = sorted({str(Path(f).parent) for f in tf_files})
        env = {
            **os.environ,
            "TF_PLUGIN_CACHE_DIR": str(Path.home() / ".terraform.d" / "plugin-cache"),
        }
        Path(env["TF_PLUGIN_CACHE_DIR"]).mkdir(parents=True, exist_ok=True)
        for d in dirs:
            cwd = str(ctx["worktree"] / d)
            self._run(["terraform", "init", "-backend=false", "-input=false"], cwd=cwd, env=env)
            self._run(["terraform", "validate", "-no-color"], cwd=cwd, env=env)
        return ", ".join(dirs)


class TerraformPlanStep(Step):
    name = "terraform plan"

    def __init__(self, run: shell.Runner = shell.run) -> None:
        super().__init__()
        self._run = run

    def run(self, ctx: Context) -> str | None:
        roots = sorted(
            {
                str(Path(f).parent)
                for f in _touches(ctx, "infra/terraform/environments/", suffix=".tf")
            }
        )
        if not roots:
            raise StepSkipped("no environment root changed")
        if not any(os.environ.get(k) for k in ("AWS_PROFILE", "AWS_ACCESS_KEY_ID", "AWS_ROLE_ARN")):
            raise StepSkipped("no AWS credentials in the environment (plan runs in the AWS phase)")
        summaries = []
        for root in roots:
            cwd = ctx["worktree"] / root
            if not (cwd / "backend.hcl").exists():
                raise StepSkipped(f"{root}/backend.hcl missing; state bucket not bootstrapped")
            self._run(
                ["terraform", "init", "-input=false", "-backend-config=backend.hcl"], cwd=str(cwd)
            )
            proc = self._run(
                ["terraform", "plan", "-input=false", "-no-color", "-out=tfplan"], cwd=str(cwd)
            )
            line = next(
                (ln for ln in proc.stdout.splitlines() if ln.startswith("Plan:")), "no changes"
            )
            summaries.append(f"{root}: {line}")
        ctx["plan_summary"] = summaries
        return "; ".join(summaries)


class CheckovStep(Step):
    name = "Checkov (Terraform security scan)"

    def __init__(self, run: shell.Runner = shell.run) -> None:
        super().__init__()
        self._run = run

    def run(self, ctx: Context) -> str | None:
        if not _touches(ctx, "infra/terraform/", suffix=".tf"):
            raise StepSkipped("no .tf changed")
        shell.require("uvx", "Install uv: brew install uv")
        proc = self._run(
            ["uvx", "checkov", "--config-file", ".checkov.yaml"],
            cwd=str(ctx["worktree"]),
            check=False,
        )
        summary = next((ln for ln in proc.stdout.splitlines() if "Passed checks" in ln), "").strip()
        if proc.returncode != 0:
            failed = [
                ln.strip() for ln in proc.stdout.splitlines() if ln.strip().startswith("Check:")
            ]
            raise StepError(summary + "; " + "; ".join(failed[:5]))
        return summary or "passed"


class ConftestTerraformStep(Step):
    name = "OPA policies (Terraform)"

    def __init__(self, run: shell.Runner = shell.run) -> None:
        super().__init__()
        self._run = run

    def run(self, ctx: Context) -> str | None:
        tf_files = _touches(ctx, "infra/terraform/", suffix=".tf")
        if not tf_files:
            raise StepSkipped("no .tf changed")
        shell.require("conftest", "Install: brew install conftest")
        cmd = [
            "conftest",
            "test",
            "--parser",
            "hcl2",
            "-p",
            "policy/terraform",
            "-d",
            "policy/data",
            "-n",
            "terraform",
            "--no-color",
            *tf_files,
        ]
        proc = self._run(cmd, cwd=str(ctx["worktree"]), check=False)
        if proc.returncode != 0:
            raise StepError(_conftest_failures(proc))
        return proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "passed"


class KubernetesPolicyStep(Step):
    """helm lint + render every affected workload and run the Kubernetes OPA policies."""

    name = "Helm render + OPA policies (Kubernetes)"

    def __init__(self, run: shell.Runner = shell.run) -> None:
        super().__init__()
        self._run = run

    def run(self, ctx: Context) -> str | None:
        wt: Path = ctx["worktree"]
        touched = _touches(ctx, "deploy/", "services/")
        if not touched:
            raise StepSkipped("no chart, values or workload changed")
        shell.require("helm")
        shell.require("conftest", "Install: brew install conftest")
        chart = wt / "deploy" / "helm" / "llm-workload"
        renders: list[tuple[str, list[str]]] = []
        for values in sorted(wt.glob("deploy/workloads/*/*.values.yaml")):
            env = values.parent.name
            renders.append(
                (
                    f"{env}/{values.stem}",
                    [
                        "-f",
                        str(wt / "deploy" / "environments" / env / "values.yaml"),
                        "-f",
                        str(values),
                    ],
                )
            )
        for cfg_path in sorted(wt.glob("services/*/aiplatform.yaml")):
            cfg = load_config(cfg_path)
            from aiplatform.targets.kind import build_values

            gen = wt / ".aiplatform" / "render" / f"{cfg.name}.values.yaml"
            gen.parent.mkdir(parents=True, exist_ok=True)
            import yaml

            gen.write_text(
                yaml.safe_dump(build_values(cfg, f"aiplatform/{cfg.name}:proposal", "proposal"))
            )
            renders.append(
                (
                    f"{cfg.environment}/{cfg.name} (aiplatform.yaml)",
                    [
                        "-f",
                        str(wt / "deploy" / "environments" / cfg.environment / "values.yaml"),
                        "-f",
                        str(gen),
                    ],
                )
            )
        if not renders:
            raise StepSkipped("nothing to render")
        self._run(
            [
                "helm",
                "lint",
                str(chart),
                "--strict",
                "--set",
                "image.tag=x",
                "--set",
                "ingress.host=x",
            ]
        )
        for label, args in renders:
            rendered = self._run(
                ["helm", "template", label.split("/")[-1].split(" ")[0], str(chart), *args]
            ).stdout
            proc = self._run(
                [
                    "conftest",
                    "test",
                    "-p",
                    "policy/kubernetes",
                    "-d",
                    "policy/data",
                    "-n",
                    "kubernetes",
                    "--no-color",
                    "-",
                ],
                cwd=str(wt),
                input=rendered,
                check=False,
            )
            if proc.returncode != 0:
                raise StepError(f"{label}: {_conftest_failures(proc)}")
        return f"{len(renders)} workload render(s) passed"


class CostEstimateStep(Step):
    name = "Cost estimate within budget"

    def run(self, ctx: Context) -> str | None:
        wt: Path = ctx["worktree"]
        est = estimate(wt)
        budget = ctx.get("budget") or load_limits(wt)["monthly_budget_usd"]
        ctx["cost"], ctx["budget"] = est, budget
        if est.total > budget:
            raise StepError(f"estimated ${est.total:.2f}/month exceeds budget ${budget:.2f}/month")
        return f"${est.total:.2f}/month of ${budget:.2f} (estimate)"


def _conftest_failures(proc: subprocess.CompletedProcess) -> str:
    fails = [ln.strip() for ln in proc.stdout.splitlines() if ln.startswith("FAIL")]
    if fails:
        return "; ".join(fails)
    return (proc.stderr or proc.stdout).strip()[-300:] or f"conftest exited {proc.returncode}"


def guard_steps(run: shell.Runner = shell.run) -> list[Step]:
    """The checks, in order. Shared by `propose` and `guard`."""
    return [
        WorkloadConfigStep(),
        TerraformFmtStep(run),
        TerraformValidateStep(run),
        TerraformPlanStep(run),
        CheckovStep(run),
        ConftestTerraformStep(run),
        KubernetesPolicyStep(run),
        CostEstimateStep(),
    ]


def changed_files(run: shell.Runner, repo: Path, base: str = "main") -> list[str]:
    """Files changed in the working tree relative to `base` (for `aiplatform guard`)."""
    proc = run(["git", "diff", "--name-only", base, "--"], cwd=str(repo), check=False)
    untracked = run(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=str(repo), check=False
    )
    files = {
        ln.strip() for ln in (proc.stdout + "\n" + untracked.stdout).splitlines() if ln.strip()
    }
    return sorted(files)


def worktree_cleanup(
    run: shell.Runner, repo: Path, worktree: Path, branch: str | None = None
) -> None:
    """Remove the scratch worktree; drop the local branch too once it is pushed or rejected."""
    with contextlib.suppress(subprocess.SubprocessError):
        run(["git", "worktree", "remove", "--force", str(worktree)], cwd=str(repo), check=False)
        if branch:
            run(["git", "branch", "-D", branch], cwd=str(repo), check=False)
