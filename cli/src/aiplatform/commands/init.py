"""`aiplatform init`: write a starter aiplatform.yaml."""

from pathlib import Path
from typing import Annotated

import typer

from aiplatform.commands.common import DirOption, console, fail
from aiplatform.config.loader import CONFIG_FILENAME

TEMPLATE = """\
# aiplatform workload definition. Run `aiplatform validate` to check it.
name: {name}
model: qwen2.5-0.5b-instruct   # see `aiplatform models`
# engine: builtin               # builtin | llamacpp-server | vllm (default follows the model)
cpu: 2
memory: 2Gi
environment: dev
port: 8000
context: .                     # Docker build context (must contain a Dockerfile)
autoscaling:
  min: 1
  max: 3
  metric: queue                # queue = pending requests per pod | cpu = utilisation %
  target: 2
env: {{}}
"""


def init(
    directory: DirOption = None,
    name: Annotated[str, typer.Option(help="Workload name (DNS-1123 label)")] = "",
) -> None:
    """Create a starter aiplatform.yaml in the target directory."""
    workload_dir = (directory or Path.cwd()).resolve()
    workload_dir.mkdir(parents=True, exist_ok=True)
    path = workload_dir / CONFIG_FILENAME
    if path.exists():
        fail(f"{path} already exists; edit it or remove it first")
    name = name or workload_dir.name.lower().replace("_", "-").replace(" ", "-")
    path.write_text(TEMPLATE.format(name=name))
    console.print(f"[green]✓[/green] wrote {path}")
    console.print("Next: edit the file, then run [bold]aiplatform validate[/bold].")
