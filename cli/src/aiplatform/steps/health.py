"""Readiness gate shared by all targets."""

import time
from collections.abc import Callable

from aiplatform import http
from aiplatform.steps.pipeline import Context, Step


class HealthCheckStep(Step):
    name = "Health checks passed"

    def __init__(self, wait_for_http: Callable[..., float] = http.wait_for_http) -> None:
        super().__init__()
        self._wait = wait_for_http

    def run(self, ctx: Context) -> str | None:
        endpoint = ctx["endpoint"]
        timeout = float(ctx.get("timeout", 600))
        live, ready = ctx["config"].health_paths
        t0 = time.monotonic()
        self._wait(f"{endpoint}{live}", timeout=min(60.0, timeout), label="liveness")
        self._wait(f"{endpoint}{ready}", timeout=timeout, label="readiness")
        waited = time.monotonic() - t0
        ctx["ready_seconds"] = waited
        return f"ready after {waited:.1f}s"
