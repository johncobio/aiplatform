"""Loopback API and static browser screens for the rehearsal."""

import asyncio
import re
import secrets
import time
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, StringConstraints
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .workflow import DemoError, Rehearsal, Spec

WEB = Path(__file__).with_name("web")
# Basic classroom syntax check; this does not establish mailbox deliverability.
EMAIL = re.compile(
    r"[a-z0-9_+%-]+(?:\.[a-z0-9_+%-]+)*@"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}",
    re.IGNORECASE | re.ASCII,
)
Auth = Annotated[str, Header()]
BoundedText = Annotated[str, StringConstraints(max_length=254)]


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class JoinBody(Body):
    invite: BoundedText


class PreviewBody(Body):
    request: BoundedText


class SampleBody(Body):
    email: BoundedText


def create_app(
    owner_token: str,
    *,
    clock: Callable[[], float] = time.monotonic,
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "testserver"),
    interpreter: Callable[[str], Spec] | None = None,
) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(allowed_hosts))
    demo = Rehearsal(clock)
    inference_lock = asyncio.Lock()

    @app.middleware("http")
    async def page_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        return response

    @app.exception_handler(DemoError)
    async def demo_error(_request: Request, error: DemoError):
        return JSONResponse({"detail": str(error)}, status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(_request: Request, _error: RequestValidationError):
        return JSONResponse(
            {"detail": "Invalid input. Check the field and keep it under 255 characters."},
            status_code=422,
        )

    def role(authorization: str, required: str | None = None) -> tuple[str, str]:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.isascii():
            raise DemoError(401, "Open your operator or guest invite link to continue.")
        if secrets.compare_digest(token, owner_token):
            actual = "owner"
        elif demo.is_guest(token):
            actual = "guest"
        else:
            raise DemoError(401, "Your session ended. Open a fresh link.")
        if required and actual != required:
            raise DemoError(403, f"This action requires the {required} role.")
        return actual, token

    @app.get("/")
    @app.get("/operator")
    @app.get("/preview")
    async def index():
        return FileResponse(WEB / "index.html", media_type="text/html")

    @app.get("/assets/{name}")
    async def asset(name: Literal["app.js", "app.css"]):
        media = "text/javascript" if name == "app.js" else "text/css"
        return FileResponse(WEB / name, media_type=media)

    @app.get("/api/status")
    async def status(authorization: Auth = ""):
        actual, token = role(authorization)
        return {
            "mode": "simulation",
            "intent": "local model" if interpreter else "example parser",
            "role": actual,
            "deployment": demo.status(token if actual == "guest" else None),
        }

    @app.post("/api/invites", status_code=201)
    async def invite(authorization: Auth = ""):
        role(authorization, "owner")
        return {"invite": demo.issue_invite()}

    @app.post("/api/join")
    async def join(body: JoinBody):
        return {"session": demo.join(body.invite)}

    @app.post("/api/requests", status_code=201)
    async def submit(body: PreviewBody, authorization: Auth = ""):
        _, token = role(authorization, "guest")
        if interpreter is None:
            return demo.submit(token, body.request)
        if inference_lock.locked():
            raise DemoError(409, "The local model is busy. Try again in a moment.")
        async with inference_lock:
            interpreted = await run_in_threadpool(interpreter, body.request)
        return demo.submit(token, body.request, interpreted=interpreted)

    @app.post("/api/requests/{job_id}/approve")
    async def approve(job_id: str, authorization: Auth = ""):
        role(authorization, "owner")
        return demo.approve(job_id)

    @app.post("/api/requests/{job_id}/destroy")
    async def destroy(job_id: str, authorization: Auth = ""):
        role(authorization, "owner")
        return demo.destroy(job_id)

    @app.post("/api/sample/{version}")
    async def sample(version: Literal["1", "2"], body: SampleBody, authorization: Auth = ""):
        _, token = role(authorization, "guest")
        if not demo.can_try(token, int(version)):
            raise DemoError(409, "This preview is not ready or has been closed.")
        email = body.email.strip()
        accepted = bool(email) if version == "1" else EMAIL.fullmatch(email) is not None
        return {"accepted": accepted}

    return app
