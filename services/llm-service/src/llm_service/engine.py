"""Inference engine: wraps a backend with lifecycle, admission control and metrics.

- Loads the model in a background thread so `/healthz` answers immediately
  and `/readyz` flips to 200 when weights are in memory.
- Serializes generations with a semaphore (llama.cpp is not thread-safe per
  model) and counts waiters as *queue depth*, the autoscaling signal.
"""

import asyncio
import logging
import threading
import time
from enum import StrEnum

from starlette.concurrency import run_in_threadpool

from llm_service import metrics
from llm_service.backends.base import Backend, Generation
from llm_service.schemas import Message

log = logging.getLogger(__name__)


class EngineState(StrEnum):
    LOADING = "loading"
    READY = "ready"
    FAILED = "failed"


class NotReadyError(RuntimeError):
    pass


class InferenceEngine:
    def __init__(self, backend: Backend, max_concurrency: int = 1) -> None:
        self.backend = backend
        self.state = EngineState.LOADING
        self.error: str | None = None
        self.load_seconds: float | None = None
        self._max_concurrency = max_concurrency
        self._slots: asyncio.Semaphore | None = None
        self._thread: threading.Thread | None = None

    # Lifecycle -----------------------------------------------------------

    def start_loading(self) -> None:
        self._slots = asyncio.Semaphore(self._max_concurrency)
        self._thread = threading.Thread(target=self._load, name="model-loader", daemon=True)
        self._thread.start()

    def _load(self) -> None:
        t0 = time.monotonic()
        try:
            self.backend.load()
        except Exception as e:  # noqa: BLE001 - surface any load failure via /readyz
            self.state = EngineState.FAILED
            self.error = f"{type(e).__name__}: {e}"
            metrics.MODEL_READY.set(0)
            log.exception("model load failed")
            return
        self.load_seconds = time.monotonic() - t0
        self.state = EngineState.READY
        metrics.MODEL_LOAD_SECONDS.set(self.load_seconds)
        metrics.MODEL_READY.set(1)
        metrics.MODEL_INFO.info(
            {"model": self.backend.model_name, "backend": type(self.backend).__name__}
        )
        log.info("model %s ready in %.2fs", self.backend.model_name, self.load_seconds)

    def wait_until_settled(self, timeout: float) -> None:
        """Test helper: block until loading finished (ready or failed)."""
        if self._thread:
            self._thread.join(timeout)

    @property
    def ready(self) -> bool:
        return self.state is EngineState.READY

    # Inference -----------------------------------------------------------

    async def generate(
        self, messages: list[Message], max_tokens: int, temperature: float
    ) -> Generation:
        if not self.ready or self._slots is None:
            raise NotReadyError(self.error or "model is still loading")

        queued_at = time.monotonic()
        metrics.QUEUE_DEPTH.inc()
        acquired = False
        try:
            async with self._slots:
                acquired = True
                waited = time.monotonic() - queued_at
                metrics.QUEUE_DEPTH.dec()
                metrics.QUEUE_WAIT.observe(waited)
                metrics.INFLIGHT.inc()
                t0 = time.monotonic()
                try:
                    gen = await run_in_threadpool(
                        self.backend.generate, messages, max_tokens, temperature
                    )
                finally:
                    metrics.INFLIGHT.dec()
                gen_seconds = time.monotonic() - t0
        except BaseException:
            if not acquired:  # cancelled while queued: undo the queue count
                metrics.QUEUE_DEPTH.dec()
            raise

        metrics.PROMPT_TOKENS.inc(gen.prompt_tokens)
        metrics.COMPLETION_TOKENS.inc(gen.completion_tokens)
        if gen_seconds > 0 and gen.completion_tokens:
            metrics.TOKENS_PER_SECOND.observe(gen.completion_tokens / gen_seconds)
        log.debug(
            "generated %d tokens in %.2fs (queue wait %.3fs)",
            gen.completion_tokens,
            gen_seconds,
            waited,
        )
        return gen
