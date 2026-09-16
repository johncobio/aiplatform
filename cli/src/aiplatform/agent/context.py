"""Gather the repository context the model needs: small, relevant, bounded."""

from pathlib import Path

from aiplatform.config.catalog import CATALOG
from aiplatform.config.quantity import format_memory

MAX_FILE_CHARS = 6000
MAX_TOTAL_CHARS = 60000

CONTEXT_GLOBS = [
    "deploy/platform.yaml",
    "policy/data/limits.yaml",
    "policy/prices.yaml",
    "services/*/aiplatform.yaml",
    "deploy/workloads/*/*.values.yaml",
    "deploy/environments/*/values.yaml",
    "deploy/helm/llm-workload/values.yaml",
    "infra/terraform/environments/dev/variables.tf",
    "infra/terraform/environments/dev/main.tf",
]


def catalog_summary() -> str:
    lines = ["| model | backend | min memory | gpu |", "|---|---|---|---|"]
    for spec in CATALOG.values():
        lines.append(
            f"| {spec.name} | {spec.backend} | {format_memory(spec.min_memory_bytes)} | "
            f"{'yes' if spec.requires_gpu else 'no'} |"
        )
    return "\n".join(lines)


def build_context(repo: Path) -> str:
    parts = ["## Model catalog", catalog_summary()]
    adrs = sorted((repo / "docs" / "adr").glob("0*.md"))
    if adrs:
        titles = [a.read_text().splitlines()[0].lstrip("# ").strip() for a in adrs]
        parts += ["## Architecture decisions", "\n".join(f"- {t}" for t in titles)]
    total = sum(len(p) for p in parts)
    for pattern in CONTEXT_GLOBS:
        for path in sorted(repo.glob(pattern)):
            text = path.read_text()
            if len(text) > MAX_FILE_CHARS:
                text = text[:MAX_FILE_CHARS] + "\n# ... truncated ...\n"
            block = f"## {path.relative_to(repo)}\n```\n{text}\n```"
            if total + len(block) > MAX_TOTAL_CHARS:
                parts.append(f"## {path.relative_to(repo)}\n(omitted: context budget reached)")
                continue
            parts.append(block)
            total += len(block)
    return "\n\n".join(parts)
