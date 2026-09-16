"""`gitops` target: deploy by committing desired state; Argo CD does the rest.

Flow: verify the CI-built image exists → write
deploy/workloads/<env>/<name>.values.yaml → git commit + push → nudge Argo CD
→ wait until the Application is Synced and Healthy → probe the ingress.
Rollback writes the previous image tag the same way; destroy deletes the file.
"""

import json
import logging
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import yaml

from aiplatform import http, shell
from aiplatform.config.schema import WorkloadConfig
from aiplatform.errors import StepError, TargetError
from aiplatform.paths import repo_root
from aiplatform.platform import PlatformConfig, load_platform
from aiplatform.state import StateStore
from aiplatform.steps.health import HealthCheckStep
from aiplatform.steps.pipeline import Context, Step
from aiplatform.steps.record import RecordReleaseStep
from aiplatform.targets.base import Target, TargetStatus
from aiplatform.targets.kind import (
    KUBE_CONTEXT,
    KindTarget,
    build_values,
    ingress_host,
    namespace_for,
)

log = logging.getLogger(__name__)


def synced_revisions(sync: dict) -> list[str]:
    """Single-source apps report `revision`; multi-source apps report `revisions`."""
    revs = list(sync.get("revisions") or [])
    if sync.get("revision"):
        revs.insert(0, sync["revision"])
    return revs


def last_build_sha(run: shell.Runner, repo: Path, context_dir: Path) -> str:
    """Short SHA of the last commit that touched the build context.

    CI builds an image only when the service directory changes, so this is the
    commit whose image exists in the registry. HEAD is usually a values-only
    commit made by an earlier GitOps deploy.
    """
    try:
        rel = str(context_dir.resolve().relative_to(repo.resolve()))
    except ValueError:
        rel = "."
    proc = run(["git", "log", "-1", "--format=%h", "--abbrev=7", "--", rel], cwd=str(repo))
    sha = proc.stdout.strip()
    if not sha:
        raise StepError(f"no commits touch {rel!r}; commit the service before deploying")
    return sha


class GitOpsTarget(Target):
    name = "gitops"

    def __init__(
        self,
        runner: shell.Runner = shell.run,
        wait_for_http: Callable[..., float] = http.wait_for_http,
        probe: Callable[[str], tuple[int, str]] = http.probe,
        platform: PlatformConfig | None = None,
        repo: Path | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._run = runner
        self._wait = wait_for_http
        self._probe = probe
        self._platform = platform
        self._repo = repo
        self._sleep = sleep
        self._kind = KindTarget(runner=runner, wait_for_http=wait_for_http, probe=probe)

    @property
    def platform(self) -> PlatformConfig:
        if self._platform is None:
            self._platform = load_platform()
        return self._platform

    @property
    def repo(self) -> Path:
        if self._repo is None:
            self._repo = repo_root()
        return self._repo

    # Steps ---------------------------------------------------------------

    def deploy_steps(self, ctx: Context) -> list[Step]:
        cfg: WorkloadConfig = ctx["config"]
        if cfg.model_spec.requires_gpu:
            raise TargetError(f"model {cfg.model!r} requires a GPU; the local cluster is CPU-only")
        return [
            _ArgoReady(self),
            _NoDirectRelease(self),
            _ImageAvailable(self),
            _WriteDesiredState(self),
            _GitCommitPush(self, "deploy"),
            _ArgoSynced(self),
            HealthCheckStep(self._wait),
            RecordReleaseStep(self.name),
        ]

    def rollback_steps(self, ctx: Context) -> list[Step]:
        return [
            _ArgoReady(self),
            _SelectPrevious(),
            _WriteDesiredState(self),
            _GitCommitPush(self, "rollback"),
            _ArgoSynced(self),
            HealthCheckStep(self._wait),
            RecordReleaseStep(self.name),
        ]

    def destroy_steps(self, ctx: Context) -> list[Step]:
        return [
            _ArgoReady(self),
            _RemoveDesiredState(self),
            _GitCommitPush(self, "remove"),
            _ArgoGone(self),
        ]

    # Queries -------------------------------------------------------------

    def status(self, ctx: Context) -> TargetStatus:
        cfg: WorkloadConfig = ctx["config"]
        base = self._kind.status(ctx)
        proc = self._run(
            self.kubectl_argo("get", "application", self.app_name(cfg), "-o", "json"), check=False
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            base.detail = "no Argo CD Application · " + base.detail
            return base
        st = json.loads(proc.stdout).get("status", {})
        sync = st.get("sync", {}).get("status", "?")
        health = st.get("health", {}).get("status", "?")
        revs = synced_revisions(st.get("sync", {}))
        rev = revs[0][:7] if revs else ""
        base.detail = f"argocd {sync}/{health} @ {rev} · " + base.detail
        return base

    def logs(self, ctx: Context, follow: bool, tail: int) -> None:
        self._kind.logs(ctx, follow, tail)

    # Helpers -------------------------------------------------------------

    def app_name(self, cfg: WorkloadConfig) -> str:
        return f"{cfg.environment}-{cfg.name}"

    def values_path(self, cfg: WorkloadConfig) -> Path:
        return (
            self.repo
            / self.platform.gitops.workloads_dir
            / cfg.environment
            / f"{cfg.name}.values.yaml"
        )

    def kubectl_argo(self, *args: str) -> list[str]:
        return ["kubectl", "--context", KUBE_CONTEXT, "-n", self.platform.argocd.namespace, *args]

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        return self._run(["git", *args], cwd=str(self.repo), check=check)

    def application(self, cfg: WorkloadConfig) -> dict | None:
        proc = self._run(
            self.kubectl_argo("get", "application", self.app_name(cfg), "-o", "json"), check=False
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        return json.loads(proc.stdout)


class _ArgoReady(Step):
    name = "Argo CD reachable"

    def __init__(self, t: GitOpsTarget) -> None:
        super().__init__()
        self.t = t

    def run(self, ctx: Context) -> str | None:
        for tool in ("git", "kubectl"):
            shell.require(tool)
        proc = self.t._run(
            self.t.kubectl_argo(
                "get", "applicationset", self.t.platform.argocd.applicationset, "-o", "name"
            ),
            check=False,
        )
        if proc.returncode != 0:
            raise StepError("Argo CD ApplicationSet not found; run `aiplatform cluster up`")
        branch = self.t.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        want = self.t.platform.gitops.branch
        if branch != want:
            raise StepError(f"gitops deploys commit to {want!r} but you are on {branch!r}")
        return f"{proc.stdout.strip()} · branch {branch}"


class _NoDirectRelease(Step):
    name = "No conflicting direct release"

    def __init__(self, t: GitOpsTarget) -> None:
        super().__init__()
        self.t = t

    def run(self, ctx: Context) -> str | None:
        cfg: WorkloadConfig = ctx["config"]
        proc = self.t._run(
            [
                "helm",
                "--kube-context",
                KUBE_CONTEXT,
                "-n",
                namespace_for(cfg.environment),
                "status",
                cfg.name,
            ],
            check=False,
        )
        if proc.returncode == 0:
            raise StepError(
                f"{cfg.name} is deployed directly with Helm in {namespace_for(cfg.environment)}; "
                "run `aiplatform destroy --target kind` first or use another environment"
            )
        return None


class _ImageAvailable(Step):
    name = "Image available in registry"

    def __init__(self, t: GitOpsTarget) -> None:
        super().__init__()
        self.t = t

    def run(self, ctx: Context) -> str | None:
        cfg: WorkloadConfig = ctx["config"]
        if ctx.get("image_tag"):
            tag = ctx["image_tag"]
        else:
            context_dir = Path(ctx["workload_dir"]) / cfg.context
            tag = f"sha-{last_build_sha(self.t._run, self.t.repo, context_dir)}"
        image = f"{self.t.platform.registry}/{cfg.name}:{tag}"
        proc = self.t._run(["docker", "manifest", "inspect", image], check=False)
        if proc.returncode != 0:
            raise StepError(
                f"{image} not found. CI publishes images for commits on "
                f"{self.t.platform.gitops.branch}; has the build finished? "
                "Use --image-tag to pick another tag."
            )
        ctx["image"], ctx["tag"] = image, tag
        return image


class _SelectPrevious(Step):
    name = "Previous release selected"

    def run(self, ctx: Context) -> str | None:
        cfg: WorkloadConfig = ctx["config"]
        state: StateStore = ctx["state"]
        prev = state.load(cfg.environment, cfg.name).previous()
        if prev is None:
            raise StepError("no previous release to roll back to")
        ctx["image"], ctx["tag"] = prev.image, prev.tag
        return prev.image


class _WriteDesiredState(Step):
    name = "Desired state written"

    def __init__(self, t: GitOpsTarget) -> None:
        super().__init__()
        self.t = t

    def run(self, ctx: Context) -> str | None:
        cfg: WorkloadConfig = ctx["config"]
        values = build_values(cfg, ctx["image"], ctx["tag"])
        path = self.t.values_path(cfg)
        path.parent.mkdir(parents=True, exist_ok=True)
        header = (
            "# Generated by `aiplatform deploy --target gitops`; Argo CD reconciles this file.\n"
        )
        path.write_text(header + yaml.safe_dump(values, sort_keys=False))
        ctx["desired_state_path"] = path
        ctx["endpoint"] = f"http://{ingress_host(cfg)}"
        return str(path.relative_to(self.t.repo))


class _RemoveDesiredState(Step):
    name = "Desired state removed"

    def __init__(self, t: GitOpsTarget) -> None:
        super().__init__()
        self.t = t

    def run(self, ctx: Context) -> str | None:
        cfg: WorkloadConfig = ctx["config"]
        path = self.t.values_path(cfg)
        if not path.exists():
            raise StepError(f"{path.relative_to(self.t.repo)} does not exist; nothing to remove")
        path.unlink()
        ctx["desired_state_path"] = path
        return str(path.relative_to(self.t.repo))


class _GitCommitPush(Step):
    name = "Change committed and pushed"

    def __init__(self, t: GitOpsTarget, verb: str) -> None:
        super().__init__()
        self.t = t
        self.verb = verb

    def run(self, ctx: Context) -> str | None:
        cfg: WorkloadConfig = ctx["config"]
        path: Path = ctx["desired_state_path"]
        rel = str(path.relative_to(self.t.repo))
        self.t.git("add", "-A", "--", rel)
        if self.t.git("diff", "--cached", "--quiet", "--", rel, check=False).returncode == 0:
            ctx["pushed_sha"] = self.t.git("rev-parse", "HEAD").stdout.strip()
            return "no change; desired state already committed"
        msg = f"{self.verb}({cfg.environment}): {cfg.name} {ctx.get('tag', '')}".rstrip()
        self.t.git("commit", "-q", "-m", msg, "--", rel)
        self.t.git("push", "-q", "origin", self.t.platform.gitops.branch)
        ctx["pushed_sha"] = self.t.git("rev-parse", "HEAD").stdout.strip()
        return f"{ctx['pushed_sha'][:7]} {msg}"


class _ArgoSynced(Step):
    name = "Argo CD synced"

    def __init__(self, t: GitOpsTarget) -> None:
        super().__init__()
        self.t = t

    def run(self, ctx: Context) -> str | None:
        cfg: WorkloadConfig = ctx["config"]
        timeout = float(ctx.get("timeout", 600))
        want = ctx["pushed_sha"]
        deadline = time.monotonic() + timeout
        appset = self.t.platform.argocd.applicationset
        # Nudge the ApplicationSet so a new values file is picked up without waiting for the poll.
        self.t._run(
            self.t.kubectl_argo(
                "annotate",
                "applicationset",
                appset,
                "argocd.argoproj.io/application-set-refresh=true",
                "--overwrite",
            ),
            check=False,
        )
        app = None
        while time.monotonic() < deadline:
            app = self.t.application(cfg)
            if app is not None:
                break
            self.t._sleep(3)
        if app is None:
            raise StepError(
                f"Argo CD Application {self.t.app_name(cfg)!r} was not created "
                f"within {timeout:.0f}s"
            )

        self.t._run(
            self.t.kubectl_argo(
                "annotate",
                "application",
                self.t.app_name(cfg),
                "argocd.argoproj.io/refresh=normal",
                "--overwrite",
            ),
            check=False,
        )
        last = ""
        while time.monotonic() < deadline:
            app = self.t.application(cfg) or {}
            st = app.get("status", {})
            sync, health = st.get("sync", {}), st.get("health", {})
            revs = synced_revisions(sync)
            rev = revs[0] if revs else ""
            last = (
                f"sync={sync.get('status', '?')} health={health.get('status', '?')} rev={rev[:7]}"
            )
            log.debug("argo %s: %s", self.t.app_name(cfg), last)
            synced = sync.get("status") == "Synced" and health.get("status") == "Healthy"
            if synced and want in revs:
                return f"{self.t.app_name(cfg)} {last}"
            if st.get("operationState", {}).get("phase") in ("Failed", "Error"):
                msg = st["operationState"].get("message", "")[:300]
                raise StepError(f"Argo CD sync failed: {msg}")
            self.t._sleep(5)
        raise StepError(
            f"Argo CD did not reach Synced/Healthy at {want[:7]} within {timeout:.0f}s ({last})"
        )


class _ArgoGone(Step):
    name = "Argo CD application removed"

    def __init__(self, t: GitOpsTarget) -> None:
        super().__init__()
        self.t = t

    def run(self, ctx: Context) -> str | None:
        cfg: WorkloadConfig = ctx["config"]
        timeout = float(ctx.get("timeout", 600))
        self.t._run(
            self.t.kubectl_argo(
                "annotate",
                "applicationset",
                self.t.platform.argocd.applicationset,
                "argocd.argoproj.io/application-set-refresh=true",
                "--overwrite",
            ),
            check=False,
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.t.application(cfg) is None:
                ctx["state"].clear_current(cfg.environment, cfg.name)
                return self.t.app_name(cfg)
            self.t._sleep(5)
        raise StepError(f"Application {self.t.app_name(cfg)!r} still exists after {timeout:.0f}s")
