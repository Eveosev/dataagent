"""Boundary tests for the sources acceptance sentinel scanner."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from scripts.acceptance import sources  # noqa: E402


def test_sentinel_crossing_chunk_boundary_is_found(tmp_path):
    path = tmp_path / "boundary.bin"
    path.write_bytes(b"x" * (1024 * 1024 - 1) + sources.SENTINEL.encode())
    assert sources._read_contains(path, [sources.SENTINEL.encode()]) is True


def test_unreadable_file_fails_scan(tmp_path):
    path = tmp_path / "unreadable.bin"
    path.write_bytes(b"x")

    def deny(self, *args, **kwargs):
        raise PermissionError("denied")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(Path, "open", deny)
        with pytest.raises(RuntimeError, match="could not read"):
            sources._read_contains(path, [sources.SENTINEL.encode()])


def test_scan_fails_when_a_project_file_cannot_be_read(tmp_path):
    (tmp_path / "unreadable.bin").write_bytes(b"x")

    def deny(self, *args, **kwargs):
        raise PermissionError("denied")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(Path, "open", deny)
        with pytest.raises(RuntimeError, match="could not read"):
            sources._scan_for_credentials(tmp_path, tmp_path / "output", {}, extra_roots=())
