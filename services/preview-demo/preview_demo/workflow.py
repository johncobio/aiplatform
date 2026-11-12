"""Typed intent and bounded, single-slot simulation state."""

import re
import secrets
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

EXAMPLE = "Deploy version 2 for 30 minutes."
REQUEST = re.compile(r"deploy version ([12]) for (15|30) minutes\.?", re.IGNORECASE | re.ASCII)
TERMINAL = {"expired", "removed"}
APPROVAL_WINDOW = 5 * 60
STAGES = (
    (0, "planning", "Operator approved. Simulated plan started."),
    (2, "starting", "Simulated plan accepted. Starting the preview."),
    (4, "verifying", "Simulating the preview health check."),
    (6, "ready", "Local sample form is ready to test."),
)


class DemoError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Spec:
    version: Literal[1, 2]
    minutes: Literal[15, 30]


def parse_request(request: str) -> Spec:
    match = REQUEST.fullmatch(request.strip())
    if match is None:
        raise DemoError(
            422,
            f"Use version 1 or 2 and a lifetime of 15 or 30 minutes. Example: {EXAMPLE}",
        )
    return Spec(cast("Literal[1, 2]", int(match[1])), cast("Literal[15, 30]", int(match[2])))


@dataclass
class Deployment:
    guest: str
    spec: Spec
    requested: float
    id: str = field(default_factory=lambda: secrets.token_hex(8))
    phase: str = "awaiting_approval"
    started: float | None = None
    next_stage: int = 0
    events: list[dict[str, str]] = field(default_factory=list)


class Rehearsal:
    """Only call from the server's one event loop; updates never await I/O."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.clock = clock
        self.epoch = clock()
        self.wall = datetime.now(UTC)
        self.invites: dict[str, float] = {}
        self.guests: dict[str, float] = {}
        self.job: Deployment | None = None

    def issue_invite(self) -> str:
        now = self.clock()
        self.invites = {key: end for key, end in self.invites.items() if now < end}
        if len(self.invites) >= 24:
            raise DemoError(409, "Too many unused invitations. Reuse an unused link or wait.")
        token = secrets.token_urlsafe(32)
        self.invites[token] = now + 15 * 60
        return token

    def join(self, token: str) -> str:
        now = self.clock()
        if now >= self.invites.pop(token, 0):
            raise DemoError(403, "This invitation expired or was used. Ask for a new link.")
        self.guests = {key: end for key, end in self.guests.items() if now < end}
        session = secrets.token_urlsafe(32)
        self.guests[session] = now + 60 * 60
        return session

    def is_guest(self, token: str) -> bool:
        return self.clock() < self.guests.get(token, 0)

    def submit(self, guest: str, request: str, *, interpreted: Spec | None = None) -> dict:
        spec = interpreted if interpreted is not None else parse_request(request)
        self.advance()
        if self.job and self.job.phase not in TERMINAL:
            raise DemoError(409, "The rehearsal slot is in use. Ask the operator to clear it.")
        now = self.clock()
        required = APPROVAL_WINDOW + STAGES[-1][0] + spec.minutes * 60
        if self.guests.get(guest, 0) - now < required:
            raise DemoError(
                409, "Your session is too short for this preview. Ask for a fresh invite."
            )
        self.job = Deployment(guest, spec, now)
        self.record("awaiting_approval", "Request validated. Waiting for operator approval.", now)
        return self.snapshot()

    def approve(self, job_id: str) -> dict:
        job = self.find(job_id)
        if job.phase != "awaiting_approval":
            raise DemoError(409, "This request is no longer waiting for approval.")
        job.started = self.clock()
        self.advance()
        return self.snapshot()

    def destroy(self, job_id: str) -> dict:
        job = self.find(job_id)
        if job.phase not in TERMINAL:
            self.record("removed", "Operator removed the local preview or request.", self.clock())
        return self.snapshot()

    def status(self, guest: str | None) -> dict | None:
        self.advance()
        if self.job and (guest is None or self.job.guest == guest):
            return self.snapshot()
        return None

    def can_try(self, guest: str, version: int) -> bool:
        job = self.status(guest)
        return bool(
            job and job["phase"] == "ready" and (version == 1 or job["spec"]["version"] == version)
        )

    def find(self, job_id: str) -> Deployment:
        self.advance()
        if self.job is None or self.job.id != job_id:
            raise DemoError(404, "That request is no longer in the rehearsal slot.")
        return self.job

    def advance(self) -> None:
        job = self.job
        if not job or job.phase in TERMINAL:
            return
        now = self.clock()
        if job.started is None:
            end = job.requested + APPROVAL_WINDOW
            if now >= end:
                self.record("expired", "Request expired while waiting for approval.", end)
            return
        while job.next_stage < len(STAGES):
            offset, phase, message = STAGES[job.next_stage]
            at = job.started + offset
            if at > now:
                break
            self.record(phase, message, at)
            job.next_stage += 1
        end = job.started + STAGES[-1][0] + job.spec.minutes * 60
        if now >= end:
            self.record("expired", "Preview lifetime ended. The sample is closed.", end)

    def record(self, phase: str, message: str, at: float) -> None:
        assert self.job is not None
        self.job.phase = phase
        stamp = (self.wall + timedelta(seconds=at - self.epoch)).isoformat(timespec="seconds")
        self.job.events.append({"phase": phase, "message": message, "at": stamp})

    def snapshot(self) -> dict:
        assert self.job is not None
        return {
            "id": self.job.id,
            "spec": asdict(self.job.spec),
            "phase": self.job.phase,
            "events": list(self.job.events),
        }
