"""Rich console reporter that renders the ✓ / ✗ checklist."""

from rich.console import Console

from aiplatform.steps.pipeline import StepStatus


class ConsoleReporter:
    def __init__(self, console: Console | None = None, show_timing: bool = False) -> None:
        self.console = console or Console()
        self.show_timing = show_timing

    def step_started(self, name: str) -> None:
        return None  # steps are short-lived; only the final ✓/✗ line is printed

    def step_finished(
        self, name: str, status: StepStatus, detail: str | None, seconds: float
    ) -> None:
        timing = f" [dim]({seconds:.1f}s)[/dim]" if self.show_timing else ""
        if status is StepStatus.OK:
            extra = f" [dim]{detail}[/dim]" if detail else ""
            self.console.print(f"[green]✓[/green] {name}{extra}{timing}")
        else:
            self.console.print(f"[red]✗[/red] {name}{timing}")
            if detail:
                self.console.print(f"  [red]{detail}[/red]", highlight=False)
