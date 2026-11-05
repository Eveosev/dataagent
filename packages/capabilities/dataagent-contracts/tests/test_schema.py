from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "schema" / "generated"


def test_schema_check_is_ci_gate():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_schema.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_schema_index_is_consistent():
    index = json.loads((GENERATED / "index.json").read_text())
    assert index["core_type_count"] == 37
    assert index["concrete_type_count"] == 35
    files = {p.name for p in GENERATED.glob("*.json")} - {"index.json"}
    assert files == set(index["files"])


def test_generation_is_idempotent_in_a_temp_dir(tmp_path):
    script = ROOT / "scripts" / "generate_schema.py"
    first = tmp_path / "first"
    second = tmp_path / "second"
    subprocess.run(
        [sys.executable, str(script), "--out", str(first)], check=True, capture_output=True
    )
    subprocess.run(
        [sys.executable, str(script), "--out", str(second)], check=True, capture_output=True
    )
    assert {p.name: p.read_bytes() for p in first.glob("*.json")} == {
        p.name: p.read_bytes() for p in second.glob("*.json")
    }
    assert {p.name: p.read_bytes() for p in first.glob("*.json")} == {
        p.name: p.read_bytes() for p in GENERATED.glob("*.json")
    }
