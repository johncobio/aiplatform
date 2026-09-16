"""`aiplatform cluster up|down|status`: the local kind platform cluster."""

from typing import Annotated

import typer

from aiplatform import addons as addons_mod
from aiplatform import cluster as cluster_mod
from aiplatform import shell
from aiplatform.commands.common import console, exit_for, fail, run_pipeline
from aiplatform.errors import AiPlatformError
from aiplatform.targets.kind import CLUSTER_NAME, KUBE_CONTEXT

app = typer.Typer(
    help="Manage the local kind cluster and its platform add-ons.", no_args_is_help=True
)


@app.command()
def up() -> None:
    """Create the kind cluster with ingress-nginx and metrics-server (idempotent)."""
    result = run_pipeline(cluster_mod.up_steps(), {})
    if result.succeeded:
        console.print(f"\nCluster ready. kubectl context: [bold]{KUBE_CONTEXT}[/bold]")
        console.print(
            "Argo CD UI: [bold]http://argocd.127.0.0.1.nip.io[/bold] (user admin, password: "
            "`kubectl -n argocd get secret argocd-initial-admin-secret "
            "-o jsonpath='{.data.password}' | base64 -d`)"
        )
    exit_for(result)


@app.command()
def down() -> None:
    """Delete the kind cluster and everything in it."""
    exit_for(run_pipeline(cluster_mod.down_steps(), {}))


@app.command()
def status() -> None:
    """Show cluster nodes and installed Helm releases."""
    try:
        if not cluster_mod.cluster_exists(shell.run):
            fail(f"kind cluster {CLUSTER_NAME!r} does not exist; run `aiplatform cluster up`")
            return
        shell.run(["kubectl", "--context", KUBE_CONTEXT, "get", "nodes"], capture=False)
        shell.run(["helm", "--kube-context", KUBE_CONTEXT, "list", "-A"], capture=False)
        console.print("\nPlatform UIs (kind):")
        for name, url in (
            ("Argo CD", "http://argocd.127.0.0.1.nip.io"),
            (
                "Grafana",
                "http://grafana.127.0.0.1.nip.io (anonymous viewer; admin/prom-operator)",
            ),
            ("Prometheus", "http://prometheus.127.0.0.1.nip.io"),
            ("Jaeger", "http://jaeger.127.0.0.1.nip.io"),
        ):
            console.print(f"  {name:<11} {url}")
    except AiPlatformError as e:
        fail(e)


addon_app = typer.Typer(
    help="Pause or resume platform add-ons (argocd, observability).", no_args_is_help=True
)
app.add_typer(addon_app, name="addon")

AddonArg = Annotated[str, typer.Argument(help="Add-on name: " + ", ".join(addons_mod.ADDONS))]


@addon_app.command()
def pause(addon: AddonArg) -> None:
    """Scale an add-on's pods to zero, keeping its configuration (frees memory on a laptop)."""
    try:
        steps = [addons_mod.ScaleAddon(shell.run, addon, resume=False)]
    except AiPlatformError as e:
        fail(e)
        return
    exit_for(run_pipeline(steps, {}))


@addon_app.command()
def resume(addon: AddonArg) -> None:
    """Scale a paused add-on back to its original replica counts."""
    try:
        steps = [addons_mod.ScaleAddon(shell.run, addon, resume=True)]
    except AiPlatformError as e:
        fail(e)
        return
    exit_for(run_pipeline(steps, {}))
