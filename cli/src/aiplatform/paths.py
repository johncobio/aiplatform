"""Locate repository assets (Helm chart, kind config) from the installed CLI.

The CLI lives in the monorepo, so assets are resolved relative to the package.
`AIPLATFORM_REPO` overrides the root for installs outside the repo.
"""

import os
from pathlib import Path

from aiplatform.errors import ConfigError

_MARKER = Path("deploy") / "helm" / "llm-workload"


def repo_root() -> Path:
    override = os.environ.get("AIPLATFORM_REPO")
    candidates = [Path(override)] if override else []
    candidates += list(Path(__file__).resolve().parents)
    for base in candidates:
        if (base / _MARKER).is_dir():
            return base
    raise ConfigError(
        "cannot locate the aiplatform repository (deploy/helm/llm-workload); "
        "set AIPLATFORM_REPO to the repo root"
    )


def chart_path() -> Path:
    return repo_root() / _MARKER


def env_values_path(environment: str) -> Path:
    return repo_root() / "deploy" / "environments" / environment / "values.yaml"


def kind_config_path() -> Path:
    return repo_root() / "deploy" / "kind" / "cluster.yaml"


def kind_addon_values(name: str) -> Path:
    return repo_root() / "deploy" / "kind" / f"{name}.values.yaml"
