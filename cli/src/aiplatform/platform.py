"""Platform-wide configuration from deploy/platform.yaml."""

from functools import lru_cache

import yaml
from pydantic import BaseModel, ConfigDict, Field

from aiplatform import paths
from aiplatform.errors import ConfigError


class GitOpsSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repo: str
    branch: str = "main"
    workloads_dir: str = "deploy/workloads"


class ArgoCDSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    namespace: str = "argocd"
    applicationset: str = "aiplatform-workloads"
    host: str = "argocd.127.0.0.1.nip.io"


class PlatformConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    registry: str = Field(description="Image registry prefix, e.g. ghcr.io/org/project")
    gitops: GitOpsSettings
    argocd: ArgoCDSettings = Field(default_factory=ArgoCDSettings)


@lru_cache(maxsize=1)
def load_platform() -> PlatformConfig:
    path = paths.repo_root() / "deploy" / "platform.yaml"
    if not path.is_file():
        raise ConfigError(f"platform config not found: {path}")
    try:
        return PlatformConfig.model_validate(yaml.safe_load(path.read_text()) or {})
    except ValueError as e:
        raise ConfigError(f"{path}: {e}") from None
