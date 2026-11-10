"""Persisted workbench job state; continuations always name actual records."""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class JobRecord:
    id: str
    session_id: str
    state: Literal['queued', 'running', 'needs_input', 'completed', 'failed']
    checkpoint: str = ''
    result_ref: str | None = None
