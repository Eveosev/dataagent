"""Shared test setup for the workbench suites.

The layer-client tests exercise the sibling ``dataagent-data`` checkout through
its own virtual environment. A fresh worktree (and a ``test_all.sh`` invocation
that lists workbench before data) has no ``dataagent-data/.venv`` yet, so sync
it once from the frozen lock; the real probe path still uses that separate
interpreter rather than importing the data layer into this process.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest


@pytest.fixture(scope="session", autouse=True)
def data_layer_environment():
    package = Path(__file__).resolve().parents[2] / "dataagent-data"
    python = package / ".venv/bin/python"
    if not python.is_file():
        result = subprocess.run(
            ["uv", "sync", "--frozen"], cwd=package, capture_output=True, text=True,
            env=dict(os.environ),
        )
        assert result.returncode == 0, result.stderr[-2000:]
    assert python.is_file(), "data layer environment was not created"
