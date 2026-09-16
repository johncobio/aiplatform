"""Schema for `aiplatform.yaml`, the developer-facing workload definition."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aiplatform.config.catalog import ModelSpec, get_model
from aiplatform.config.quantity import format_memory, parse_cpu, parse_memory
from aiplatform.errors import ConfigError

_DNS_LABEL = re.compile(r"^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$")

Environment = Literal["dev", "staging"]
Engine = Literal["builtin", "llamacpp-server", "vllm"]


class Autoscaling(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min: int = Field(1, ge=0, le=100)
    max: int = Field(1, ge=1, le=100)
    metric: Literal["queue", "cpu"] = Field(
        "queue",
        description="queue = pending requests per pod (prometheus-adapter); cpu = utilisation %",
    )
    target: float | None = Field(
        None,
        gt=0,
        description="Per-pod target: pending requests (queue, default 2) or CPU % (cpu, 70)",
    )

    @property
    def effective_target(self) -> float:
        if self.target is not None:
            return self.target
        return 2.0 if self.metric == "queue" else 70.0

    @model_validator(mode="after")
    def _min_le_max(self) -> "Autoscaling":
        if self.min > self.max:
            raise ValueError(f"autoscaling.min ({self.min}) cannot exceed max ({self.max})")
        return self


class WorkloadConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="DNS-1123 label, used for containers, images and services")
    model: str = Field(description="Model name from the platform catalog")
    engine: Engine | None = Field(
        None,
        description="Inference engine: builtin (this repo's service), llamacpp-server, vllm. "
        "Default: builtin for CPU/GGUF models, vllm for GPU models",
    )
    cpu: str | int | float = Field(description="CPU request, e.g. 2 or 500m")
    memory: str = Field(description="Memory request, e.g. 2Gi")
    environment: Environment
    port: int = Field(8000, ge=1, le=65535)
    context: str = Field(".", description="Docker build context, relative to the config file")
    autoscaling: Autoscaling = Field(default_factory=Autoscaling)
    env: dict[str, str] = Field(default_factory=dict, description="Extra environment variables")

    @field_validator("name")
    @classmethod
    def _dns_label(cls, v: str) -> str:
        if not _DNS_LABEL.match(v):
            raise ValueError(
                "name must be a DNS-1123 label: lowercase letters, digits and '-', "
                "1-63 chars, starting and ending alphanumeric"
            )
        return v

    @field_validator("cpu")
    @classmethod
    def _cpu(cls, v: str | int | float) -> str | int | float:
        parse_cpu(v)
        return v

    @field_validator("memory")
    @classmethod
    def _memory(cls, v: str) -> str:
        parse_memory(v)
        return v

    @field_validator("model")
    @classmethod
    def _model(cls, v: str) -> str:
        try:
            get_model(v)
        except ConfigError as e:
            raise ValueError(str(e)) from None
        return v

    @model_validator(mode="after")
    def _memory_fits_model(self) -> "WorkloadConfig":
        spec = self.model_spec
        if self.memory_bytes < spec.min_memory_bytes:
            raise ValueError(
                f"model {spec.name!r} requires at least "
                f"{format_memory(spec.min_memory_bytes)} of memory, got {self.memory}"
            )
        return self

    @model_validator(mode="after")
    def _engine_matches_model(self) -> "WorkloadConfig":
        spec = self.model_spec
        engine = self.engine_type
        if engine == "vllm" and spec.backend != "vllm":
            raise ValueError(
                f"engine vllm needs a vllm catalog model; {spec.name!r} is {spec.backend}"
            )
        if engine != "vllm" and spec.backend == "vllm":
            raise ValueError(f"model {spec.name!r} is served by vllm; set engine: vllm")
        return self

    # Derived views -------------------------------------------------------

    @property
    def engine_type(self) -> str:
        """Resolved engine: explicit value, else vllm for vllm models, else builtin."""
        if self.engine:
            return self.engine
        return "vllm" if self.model_spec.backend == "vllm" else "builtin"

    @property
    def health_paths(self) -> tuple[str, str]:
        """(liveness, readiness) HTTP paths for the resolved engine."""
        if self.engine_type == "builtin":
            return ("/healthz", "/readyz")
        return ("/health", "/health")

    @property
    def builds_image(self) -> bool:
        """Only the builtin engine is built from the workload directory."""
        return self.engine_type == "builtin"

    @property
    def cpu_cores(self) -> float:
        return parse_cpu(self.cpu)

    @property
    def memory_bytes(self) -> int:
        return parse_memory(self.memory)

    @property
    def model_spec(self) -> ModelSpec:
        return get_model(self.model)
