"""`aiplatform models`: list the model catalog."""

from rich.table import Table

from aiplatform.commands.common import console
from aiplatform.config.catalog import CATALOG
from aiplatform.config.quantity import format_memory


def models() -> None:
    """List models the platform can serve and their minimum resources."""
    table = Table(title="Model catalog")
    table.add_column("name")
    table.add_column("params", justify="right")
    table.add_column("backend")
    table.add_column("min memory", justify="right")
    table.add_column("gpu")
    for spec in CATALOG.values():
        table.add_row(
            spec.name,
            f"{spec.parameters_b:g}B",
            spec.backend,
            format_memory(spec.min_memory_bytes),
            "required" if spec.requires_gpu else "no",
        )
    console.print(table)
