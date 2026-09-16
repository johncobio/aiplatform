"""Local deployment history, one JSON file per (environment, workload).

Enough state for `status` and `rollback` without a database. In later phases
the source of truth moves to Git (Argo CD); this store remains for the local
target.
"""

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field


class Release(BaseModel):
    tag: str
    image: str
    target: str
    endpoint: str = ""
    deployed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WorkloadState(BaseModel):
    current: Release | None = None
    releases: list[Release] = Field(default_factory=list)

    def previous(self) -> Release | None:
        """The most recent release before `current`, if any."""
        if self.current is None:
            return self.releases[-1] if self.releases else None
        older = [r for r in self.releases if r.tag != self.current.tag]
        return older[-1] if older else None


class StateStore:
    def __init__(self, root: Path, keep: int = 10) -> None:
        self.root = root
        self.keep = keep

    def _path(self, environment: str, name: str) -> Path:
        return self.root / environment / f"{name}.json"

    def load(self, environment: str, name: str) -> WorkloadState:
        path = self._path(environment, name)
        if not path.is_file():
            return WorkloadState()
        return WorkloadState.model_validate_json(path.read_text())

    def save(self, environment: str, name: str, state: WorkloadState) -> None:
        path = self._path(environment, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(state.model_dump_json(indent=2))
        tmp.replace(path)

    def record(self, environment: str, name: str, release: Release) -> WorkloadState:
        state = self.load(environment, name)
        state.releases = [r for r in state.releases if r.tag != release.tag] + [release]
        state.releases = state.releases[-self.keep :]
        state.current = release
        self.save(environment, name, state)
        return state

    def clear_current(self, environment: str, name: str) -> None:
        state = self.load(environment, name)
        state.current = None
        self.save(environment, name, state)
