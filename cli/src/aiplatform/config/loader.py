"""Locate and load `aiplatform.yaml`."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from aiplatform.config.schema import WorkloadConfig
from aiplatform.errors import ConfigError

CONFIG_FILENAME = "aiplatform.yaml"


def find_config(start: Path | None = None) -> Path:
    """Return the config path in `start` (default cwd) or raise."""
    directory = (start or Path.cwd()).resolve()
    candidate = directory / CONFIG_FILENAME
    if not candidate.is_file():
        raise ConfigError(f"{CONFIG_FILENAME} not found in {directory}; run `aiplatform init`")
    return candidate


def load_config(path: Path) -> WorkloadConfig:
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise ConfigError(f"{path}: invalid YAML: {e}") from None
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: top level must be a mapping of fields")
    try:
        return WorkloadConfig.model_validate(raw)
    except ValidationError as e:
        raise ConfigError(_format_validation_error(path, e)) from None


def _format_validation_error(path: Path, err: ValidationError) -> str:
    lines = [f"{path}: {err.error_count()} validation error(s)"]
    for item in err.errors():
        loc = ".".join(str(p) for p in item["loc"]) or "<root>"
        msg = item["msg"].removeprefix("Value error, ")
        lines.append(f"  - {loc}: {msg}")
    return "\n".join(lines)
