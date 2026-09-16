"""FastAPI application factory and HTTP routes."""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from llm_service import __version__, metrics
from llm_service.backends import Backend, build_backend
from llm_service.engine import InferenceEngine, NotReadyError
from llm_service.logging import configure_logging
from llm_service.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    Choice,
    Message,
    ModelCard,
    ModelList,
    Usage,
)
from llm_service.settings import Settings
from llm_service.tracing import configure_tracing, current_trace_id, instrument_app

log = logging.getLogger("llm_service")
access_log = logging.getLogger("llm_service.access")


def create_app(
    settings: Settings | None = None, backend: Backend | None = None, tracing: bool = True
) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level, settings.log_format)
    if tracing:
        configure_tracing()
    engine = InferenceEngine(backend or build_backend(settings), settings.max_concurrency)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        log.info(
            "starting llm-service %s backend=%s model=%s",
            __version__,
            settings.backend,
            settings.model_name,
        )
        engine.start_loading()
        yield
        log.info("shutting down")

    app = FastAPI(title="llm-service", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    instrument_app(app)

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        t0 = time.monotonic()
        response: Response = await call_next(request)
        duration_ms = round((time.monotonic() - t0) * 1000, 1)
        response.headers["x-request-id"] = request_id
        if request.url.path not in ("/healthz", "/readyz", "/metrics"):
            access_log.info(
                "%s %s -> %s",
                request.method,
                request.url.path,
                response.status_code,
                extra={
                    "request_id": request_id,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                    "trace_id": current_trace_id(),
                },
            )
        return response

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz():
        body = {"status": engine.state.value, "model": engine.backend.model_name}
        if engine.ready:
            body["load_seconds"] = round(engine.load_seconds or 0, 2)
            return body
        if engine.error:
            body["error"] = engine.error
        return JSONResponse(body, status_code=503)

    @app.get("/metrics")
    async def prometheus_metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/v1/models", response_model=ModelList)
    async def list_models():
        return ModelList(data=[ModelCard(id=engine.backend.model_name)])

    @app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
    async def chat_completions(req: ChatCompletionRequest):
        if req.stream:
            raise HTTPException(400, "streaming is not supported yet")
        max_tokens = req.max_tokens or settings.default_max_tokens
        if max_tokens > settings.max_tokens_limit:
            metrics.REQUESTS.labels(status="rejected").inc()
            raise HTTPException(400, f"max_tokens exceeds limit of {settings.max_tokens_limit}")

        t0 = time.monotonic()
        try:
            gen = await engine.generate(req.messages, max_tokens, req.temperature)
        except NotReadyError as e:
            metrics.REQUESTS.labels(status="rejected").inc()
            raise HTTPException(503, f"model not ready: {e}") from None
        except Exception:
            metrics.REQUESTS.labels(status="error").inc()
            metrics.REQUEST_DURATION.observe(time.monotonic() - t0)
            log.exception("generation failed")
            raise HTTPException(500, "generation failed") from None
        metrics.REQUESTS.labels(status="ok").inc()
        metrics.REQUEST_DURATION.observe(time.monotonic() - t0)

        return ChatCompletionResponse(
            model=engine.backend.model_name,
            choices=[
                Choice(
                    message=Message(role="assistant", content=gen.text),
                    finish_reason=gen.finish_reason,
                )
            ],
            usage=Usage(
                prompt_tokens=gen.prompt_tokens,
                completion_tokens=gen.completion_tokens,
                total_tokens=gen.prompt_tokens + gen.completion_tokens,
            ),
        )

    return app
