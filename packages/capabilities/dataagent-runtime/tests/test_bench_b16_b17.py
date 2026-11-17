"""B16/B17 branches of the 09-benchmark CLI entry point.

The data layer does not ship the DA03.2 identity-alignment or DA02.4
schema-mapping operations yet, so the entry carries deterministic baselines.
These tests pin the two output shapes the graders and the oracle adapter use,
the explicit-null behaviour, and the failure path (status/error, exit 1).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dataagent_runtime.interfaces import bench


def _make_bench(tmp_path: Path, task_id: str) -> tuple[Path, Path]:
    root = tmp_path / "bench"
    (root / "harness").mkdir(parents=True)
    (root / "datasets.lock.json").write_text(
        json.dumps({"raw_root": "workspace/benchmark-data"}),
        encoding="utf-8",
    )
    task = root / "tasks" / f"{task_id}-test-task"
    (task / "dataset" / "cases" / "development").mkdir(parents=True)
    (task / "dataset" / "fixtures").mkdir()
    return root, task


def _write_fixture(task: Path, case_id: str, payload: dict) -> Path:
    path = task / "dataset" / "fixtures" / f"{case_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _write_case(
    task: Path,
    *,
    case_id: str,
    task_id: str,
    ref: str,
) -> Path:
    case = {
        "case_id": case_id,
        "task_id": task_id,
        "split_role": "development",
        "inputs": [{"kind": "record_pair" if task_id == "B16" else "table", "ref": ref}],
    }
    path = task / "dataset" / "cases" / "development" / f"{case_id}.json"
    path.write_text(json.dumps(case), encoding="utf-8")
    return path


def _b16_fixture() -> dict:
    return {
        "left": {
            "id": "34102",
            "name": "Canon CB-2LV Battery Charger - 9764A001",
            "description": "Compatible With Canon NB-4L Rechargeable Battery",
        },
        "right_candidates": [
            {
                "id": "90140498",
                "name": "Canon NB-4L Rechargeable Camera Battery - 9763A001",
                "manufacturer": "Canon",
            },
            {
                "id": "90141687",
                "name": "Canon CB-2LV Battery Charger - 9764A001",
                "description": "for NB-4L",
                "manufacturer": "Canon",
            },
        ],
    }


def _b17_fixture() -> dict:
    return {
        "task": "schema_matching_top1",
        "source_field": "total_changes",
        "source_table": {
            "name": "pair/source_table.csv",
            "columns": [
                {"name": "total_changes", "samples": ["1477.0", "1215.0"]},
                {"name": "changes", "samples": ["-19049921.84", "25273000.0"]},
            ],
        },
        "target_table": {
            "name": "pair/target_table.csv",
            "columns": [
                {"name": "total_schedule_changes", "samples": ["1477.0", "1215.0"]},
                {"name": "total_budget_changes", "samples": ["-19049921.84", "25273000.0"]},
                {"name": "pid", "samples": ["541", "516"]},
            ],
        },
    }


def test_b16_output_uses_entity_pair_shape():
    output = bench._b16_output(_b16_fixture())
    assert output == {"pairs": [{"left_id": "34102", "right_id": "90141687"}]}


def test_b16_output_returns_empty_pairs_when_nothing_matches():
    fixture = {
        "left": {"id": "L1", "name": "Acme Widget Alpha"},
        "right_candidates": [{"id": "R1", "name": "Zeta Rocket Engine"}],
    }
    assert bench._b16_output(fixture) == {"pairs": []}


def test_b16_output_requires_a_left_record():
    with pytest.raises(bench.BenchError, match="left record"):
        bench._b16_output({"right_candidates": []})


def test_b16_output_requires_candidates():
    with pytest.raises(bench.BenchError, match="right_candidates"):
        bench._b16_output({"left": {"id": "L1", "name": "x"}})


def test_b17_output_uses_mapping_shape_and_sample_values():
    output = bench._b17_output(_b17_fixture())
    assert output == {
        "mappings": [
            {"source_field": "total_changes", "target_field": "total_schedule_changes"}
        ]
    }


def test_b17_output_explicit_null_when_nothing_matches():
    fixture = _b17_fixture()
    fixture["source_field"] = "zebra_count"
    fixture["source_table"]["columns"].append({"name": "zebra_count", "samples": ["7"]})
    output = bench._b17_output(fixture)
    assert output["mappings"] == [{"source_field": "zebra_count", "target_field": None}]


def test_b17_output_requires_source_field():
    fixture = _b17_fixture()
    del fixture["source_field"]
    with pytest.raises(bench.BenchError, match="source_field"):
        bench._b17_output(fixture)


def test_run_case_b16_writes_ok_result(tmp_path: Path):
    _root, task = _make_bench(tmp_path, "B16")
    _write_fixture(task, "B16-test-0001", _b16_fixture())
    case = _write_case(
        task,
        case_id="B16-test-0001",
        task_id="B16",
        ref="fixtures/B16-test-0001.json",
    )
    out = tmp_path / "out"
    assert bench.run_case(case, out) == 0
    payload = json.loads((out / "result.json").read_text(encoding="utf-8"))
    assert payload["status"] == "ok"
    assert payload["error"] is None
    assert payload["output"]["pairs"][0]["right_id"] == "90141687"


def test_run_case_b17_writes_ok_result(tmp_path: Path):
    _root, task = _make_bench(tmp_path, "B17")
    _write_fixture(task, "B17-test-0001", _b17_fixture())
    case = _write_case(
        task,
        case_id="B17-test-0001",
        task_id="B17",
        ref="fixtures/B17-test-0001.json",
    )
    out = tmp_path / "out"
    assert bench.run_case(case, out) == 0
    payload = json.loads((out / "result.json").read_text(encoding="utf-8"))
    assert payload["status"] == "ok"
    assert payload["task_id"] == "B17"
    assert payload["output"]["mappings"][0]["target_field"] == "total_schedule_changes"


def test_run_case_b16_malformed_fixture_is_an_explicit_failure(tmp_path: Path):
    _root, task = _make_bench(tmp_path, "B16")
    _write_fixture(task, "B16-test-0002", {"left": {"id": "L1", "name": "x"}})
    case = _write_case(
        task,
        case_id="B16-test-0002",
        task_id="B16",
        ref="fixtures/B16-test-0002.json",
    )
    out = tmp_path / "out"
    assert bench.run_case(case, out) == 1
    payload = json.loads((out / "result.json").read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["output"] is None
    assert "right_candidates" in payload["error"]


def test_run_case_b17_missing_source_column_is_an_explicit_failure(tmp_path: Path):
    _root, task = _make_bench(tmp_path, "B17")
    fixture = _b17_fixture()
    fixture["source_field"] = "absent_field"
    _write_fixture(task, "B17-test-0002", fixture)
    case = _write_case(
        task,
        case_id="B17-test-0002",
        task_id="B17",
        ref="fixtures/B17-test-0002.json",
    )
    out = tmp_path / "out"
    assert bench.run_case(case, out) == 1
    payload = json.loads((out / "result.json").read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert "absent_field" in payload["error"]


def test_fixture_reader_requires_the_task_input_kind(tmp_path: Path):
    path = tmp_path / "fixture.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(bench.BenchError, match="record_pair"):
        bench._execute_b16([({"kind": "table"}, path)])
    with pytest.raises(bench.BenchError, match="table"):
        bench._execute_b17([({"kind": "record_pair"}, path)])


def test_fixture_reader_rejects_non_json(tmp_path: Path):
    path = tmp_path / "fixture.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(bench.BenchError, match="not valid JSON"):
        bench._execute_b16([({"kind": "record_pair"}, path)])
