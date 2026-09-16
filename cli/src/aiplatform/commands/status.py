"""`aiplatform status`: show the current release and its health."""

from rich.table import Table

from aiplatform.commands.common import (
    DirOption,
    TargetOption,
    build_context,
    console,
    fail,
    resolve_target,
)
from aiplatform.errors import AiPlatformError


def status(directory: DirOption = None, target: TargetOption = "local") -> None:
    """Show whether the workload is running and ready."""
    try:
        ctx = build_context(directory)
        tgt = resolve_target(target)
        st = tgt.status(ctx)
    except AiPlatformError as e:
        fail(e)
        return
    cfg = ctx["config"]
    state = ctx["state"].load(cfg.environment, cfg.name)

    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_row("workload", f"{cfg.name} ({cfg.environment}, target {tgt.name})")
    table.add_row("running", "[green]yes[/green]" if st.running else "[red]no[/red]")
    table.add_row("ready", "[green]yes[/green]" if st.ready else "[yellow]no[/yellow]")
    if st.image:
        table.add_row("image", st.image)
    if st.started_at:
        table.add_row("started", st.started_at)
    if st.endpoint:
        table.add_row("endpoint", st.endpoint)
    if st.detail:
        table.add_row("detail", st.detail)
    if state.current:
        table.add_row(
            "release",
            f"{state.current.tag} (deployed {state.current.deployed_at:%Y-%m-%d %H:%M:%S %Z})",
        )
    if len(state.releases) > 1:
        table.add_row("history", ", ".join(r.tag for r in state.releases[-5:]))
    console.print(table)
