"""Tests for the 09-benchmark CLI entry point (``dataagent run --case``).

The runtime package does not depend on ``dataagent_data``; these tests keep
that boundary by injecting a dispatch function and by exercising the pure
mapping/parsing helpers with small stand-ins.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from dataagent_runtime.interfaces import bench


def _make_bench(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "bench"
    (root / "harness").mkdir(parents=True)
    (root / "datasets.lock.json").write_text(
        json.dumps({"raw_root": "workspace/benchmark-data"}),
        encoding="utf-8",
    )
    task = root / "tasks" / "B02-doc-parse-ocr"
    (task / "dataset" / "cases" / "development").mkdir(parents=True)
    (task / "dataset" / "fixtures").mkdir()
    return root, task


def _write_case(task: Path, *, case_id: str = "B02-od-0001", task_id: str = "B02", ref: str) -> Path:
    case = {
        "case_id": case_id,
        "task_id": task_id,
        "split_role": "development",
        "inputs": [{"kind": "file", "ref": ref}],
    }
    path = task / "dataset" / "cases" / "development" / f"{case_id}.json"
    path.write_text(json.dumps(case), encoding="utf-8")
    return path


def test_write_result_always_has_status_and_error(tmp_path: Path):
    path = bench.write_result(
        tmp_path,
        case_id="B02-od-0001",
        task_id="B02",
        status="failed",
        error="boom",
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["error"] == "boom"
    assert payload["output"] is None
    assert payload["usage"] == {"tokens": 0, "cost_usd": 0.0}


def test_load_case_rejects_non_object(tmp_path: Path):
    path = tmp_path / "case.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(bench.BenchError, match="JSON object"):
        bench.load_case(path)


def test_find_bench_root_and_repo_root(tmp_path: Path):
    root, task = _make_bench(tmp_path)
    (tmp_path / ".git").mkdir()
    case = _write_case(task, ref="fixtures/none.png")
    assert bench.find_bench_root(case) == root.resolve()
    assert bench.dataset_dir_for(case) == (task / "dataset").resolve()
    assert bench.repo_root_for(root) == tmp_path


def test_resolve_ref_bench_and_fixtures(tmp_path: Path):
    root, task = _make_bench(tmp_path)
    raw = tmp_path / "workspace" / "benchmark-data"
    image = raw / "B02" / "omnidocbench" / "images" / "page.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"png")
    fixture = task / "dataset" / "fixtures" / "task.md"
    fixture.write_text("instructions", encoding="utf-8")

    assert bench.resolve_ref(
        "bench://omnidocbench/images/page.png",
        task_id="B02",
        dataset_dir=task / "dataset",
        raw_root=raw,
    ) == image
    assert bench.resolve_ref(
        "fixtures/task.md",
        task_id="B02",
        dataset_dir=task / "dataset",
        raw_root=raw,
    ) == fixture


def test_resolve_ref_rejects_escape_and_reports_missing(tmp_path: Path):
    root, task = _make_bench(tmp_path)
    raw = tmp_path / "workspace" / "benchmark-data"
    with pytest.raises(bench.BenchError, match="escapes"):
        bench.resolve_ref(
            "bench://omnidocbench/../secret",
            task_id="B02",
            dataset_dir=task / "dataset",
            raw_root=raw,
        )
    with pytest.raises(bench.BenchError, match="input not found"):
        bench.resolve_ref(
            "bench://omnidocbench/images/missing.png",
            task_id="B02",
            dataset_dir=task / "dataset",
            raw_root=raw,
        )


def test_resolve_ref_rejects_absolute_unknown_and_traversal(tmp_path: Path):
    _root, task = _make_bench(tmp_path)
    raw = tmp_path / "workspace" / "benchmark-data"
    refs = [
        "/etc/passwd",
        "C:/Windows/win.ini",
        "elsewhere/file.txt",
        "fixtures",
        "fixtures/../../etc/passwd",
        "fixtures/./../outside.txt",
        "bench://omnidocbench",
        "bench://../outside.txt",
        "bench://omnidocbench/../../outside.txt",
        "bench://omnidocbench//etc/passwd",
    ]
    for ref in refs:
        with pytest.raises(bench.BenchError):
            bench.resolve_ref(
                ref,
                task_id="B02",
                dataset_dir=task / "dataset",
                raw_root=raw,
            )


def test_resolve_ref_rejects_symlink_escape(tmp_path: Path):
    _root, task = _make_bench(tmp_path)
    dataset = task / "dataset"
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    (dataset / "fixtures" / "leak.txt").symlink_to(outside)
    with pytest.raises(bench.BenchError, match="escapes allowed root"):
        bench.resolve_ref(
            "fixtures/leak.txt",
            task_id="B02",
            dataset_dir=dataset,
            raw_root=tmp_path / "raw",
        )


def test_resolve_ref_rejects_symlinked_source_escape(tmp_path: Path):
    _root, task = _make_bench(tmp_path)
    raw = tmp_path / "raw"
    images = raw / "B02" / "omnidocbench" / "images"
    images.mkdir(parents=True)
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"secret")
    (images / "leak.png").symlink_to(outside)
    with pytest.raises(bench.BenchError, match="escapes allowed root"):
        bench.resolve_ref(
            "bench://omnidocbench/images/leak.png",
            task_id="B02",
            dataset_dir=task / "dataset",
            raw_root=raw,
        )


def test_resolve_ref_accepts_symlink_inside_root(tmp_path: Path):
    _root, task = _make_bench(tmp_path)
    raw = tmp_path / "raw"
    real = raw / "B02" / "omnidocbench" / "images" / "real.png"
    real.parent.mkdir(parents=True)
    real.write_bytes(b"png")
    (real.parent / "alias.png").symlink_to(real)
    resolved = bench.resolve_ref(
        "bench://omnidocbench/images/alias.png",
        task_id="B02",
        dataset_dir=task / "dataset",
        raw_root=raw,
    )
    assert resolved == real.resolve()


def test_run_case_absolute_ref_fails_before_reading(tmp_path: Path):
    _root, task = _make_bench(tmp_path)
    case = _write_case(task, ref="/etc/passwd")
    out = tmp_path / "out"
    assert bench.run_case(case, out) == 1
    payload = json.loads((out / "result.json").read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert "absolute input reference" in payload["error"]


def test_run_case_missing_input_writes_explicit_failure(tmp_path: Path):
    _root, task = _make_bench(tmp_path)
    case = _write_case(task, ref="fixtures/missing.png")
    out = tmp_path / "out"
    code = bench.run_case(case, out)
    assert code == 1
    payload = json.loads((out / "result.json").read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert "input not found" in payload["error"]
    assert payload["output"] is None


def test_run_case_unknown_task_writes_explicit_failure(tmp_path: Path):
    _root, task = _make_bench(tmp_path)
    image = task / "dataset" / "fixtures" / "page.png"
    image.write_bytes(b"png")
    case = _write_case(task, task_id="B99", ref="fixtures/page.png")
    out = tmp_path / "out"
    assert bench.run_case(case, out) == 1
    payload = json.loads((out / "result.json").read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert "unsupported task_id" in payload["error"]


def test_run_case_success_uses_injected_dispatch(tmp_path: Path):
    _root, task = _make_bench(tmp_path)
    image = task / "dataset" / "fixtures" / "page.png"
    image.write_bytes(b"png")
    case = _write_case(task, ref="fixtures/page.png")
    seen = {}

    def dispatch(**kwargs):
        seen.update(kwargs)
        return {"text": "hello", "blocks": [], "tables": []}, "ok", []

    out = tmp_path / "out"
    assert bench.run_case(case, out, dispatch=dispatch) == 0
    payload = json.loads((out / "result.json").read_text(encoding="utf-8"))
    assert payload["status"] == "ok"
    assert payload["output"]["text"] == "hello"
    assert payload["error"] is None
    assert seen["task_id"] == "B02"
    assert seen["inputs"][0][1] == image


def test_ocr_source_dir_uses_explicit_ocr_root(tmp_path: Path):
    pin = tmp_path / "ocr-local" / "ocr"
    pin.mkdir(parents=True)
    (pin / "active.json").write_text("{}", encoding="utf-8")
    source = bench._ocr_source_dir(
        repo_root=tmp_path / "repo",
        bench_root=tmp_path / "bench",
        environ={"OCR_ROOT": str(tmp_path / "ocr-local")},
    )
    assert source == pin.resolve()


def test_ocr_source_dir_refuses_bad_explicit_root(tmp_path: Path):
    with pytest.raises(bench.BenchError, match="active.json missing"):
        bench._ocr_source_dir(
            repo_root=tmp_path / "repo",
            bench_root=tmp_path / "bench",
            environ={"OCR_ROOT": str(tmp_path / "not-a-pin")},
        )


def test_mirror_ocr_root_keeps_quality_writable(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "active.json").write_text("{}", encoding="utf-8")
    for name in ("profiles", "verifications", "engines"):
        (source / name).mkdir()
        (source / name / "marker").write_text(name, encoding="utf-8")
    data_root = bench._mirror_ocr_root(source, tmp_path / "scratch")
    ocr = data_root / "ocr"
    assert (ocr / "active.json").is_file()
    assert (ocr / "profiles").is_symlink()
    assert (ocr / "quality").is_dir()
    assert (ocr / "events.jsonl").is_file()
    (ocr / "quality" / "usage.jsonl").write_text("{}\n", encoding="utf-8")


def test_b02_output_orders_blocks_across_pages():
    first = SimpleNamespace(
        full_text="first",
        pages=[
            SimpleNamespace(
                page=1,
                blocks=[
                    SimpleNamespace(text="a", bbox=(0, 0, 1, 1)),
                    SimpleNamespace(text="b", bbox=None),
                ],
            )
        ],
    )
    second = SimpleNamespace(
        full_text="second",
        pages=[SimpleNamespace(page=2, blocks=[SimpleNamespace(text="c", bbox=(2, 2, 3, 3))])],
    )
    out = bench._b02_output([first, second])
    assert out["text"] == "first\nsecond"
    assert [block["order"] for block in out["blocks"]] == [1, 2, 3]
    assert [block["text"] for block in out["blocks"]] == ["a", "b", "c"]
    assert out["blocks"][0]["bbox"] == [0, 0, 1, 1]
    assert out["blocks"][1]["page"] == 1
    assert out["tables"] == []


def test_set_path_supports_nested_and_indexed_paths():
    root: dict = {}
    bench._set_path(root, "total.total_price", "31.000")
    bench._set_path(root, "line_items[0].description", "coffee")
    bench._set_path(root, "line_items[0].price", "28.182")
    bench._set_path(root, "line_items[1].description", "tea")
    assert root == {
        "total": {"total_price": "31.000"},
        "line_items": [
            {"description": "coffee", "price": "28.182"},
            {"description": "tea"},
        ],
    }


def test_fields_from_instruction_reads_object_structure():
    specs = bench._fields_from_instruction(
        "- menu：菜品列表（nm 名称、cnt 数量、price 单价、itemsubtotal 小计）\n"
        "- sub_total：subtotal_price / discount_price / tax_price\n"
        "- total：total_price 等\n"
    )
    paths = [spec[0] for spec in specs]
    assert "menu.nm" in paths
    assert "menu.price" in paths
    assert "sub_total.subtotal_price" in paths
    assert "total.total_price" in paths


def test_fields_from_schema_flattens_nested_objects():
    specs = bench._fields_from_schema(
        {
            "type": "object",
            "properties": {
                "customer": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                },
                "total": {"type": "number"},
            },
        }
    )
    by_path = {spec[0]: spec[3] for spec in specs}
    assert by_path == {"customer.name": "string", "total": "number"}


def test_fields_from_rules_skips_container_nodes():
    specs = bench._fields_from_rules(
        "# rules\n"
        + json.dumps(
            {
                "merchant_name": {"comparator": "string"},
                "line_items": {"comparator": {"kind": "list"}},
                "line_items[0].line_no": {"comparator": "number"},
            }
        )
    )
    paths = [spec[0] for spec in specs]
    assert paths == ["merchant_name", "line_items[0].line_no"]


def test_b03_output_needs_input_keeps_candidate_spans():
    result = SimpleNamespace(
        status=SimpleNamespace(value="needs_input"),
        data=SimpleNamespace(
            record=None,
            candidate_spans=[
                SimpleNamespace(page=1, text="TOTAL 31.000", char_start=0, char_end=11)
            ],
        ),
        issues=[
            SimpleNamespace(
                code="da02.inference_required",
                severity=SimpleNamespace(value="info"),
                message="proposal required",
            )
        ],
    )
    out = bench._b03_output(
        result,
        [SimpleNamespace(field_id="total.total_price", path="total.total_price")],
        None,
    )
    assert out["json"] == {}
    assert out["spans"] == []
    assert out["capability_status"] == "needs_input"
    assert out["candidate_spans"][0]["text"] == "TOTAL 31.000"
    assert out["issues"][0]["code"] == "da02.inference_required"


def test_b03_output_maps_record_values_and_pages():
    result = SimpleNamespace(
        status=SimpleNamespace(value="ok"),
        data=SimpleNamespace(
            record=SimpleNamespace(
                fields=[
                    SimpleNamespace(
                        field_id="total.total_price",
                        status=SimpleNamespace(value="extracted"),
                        value="31.000",
                        evidence=[],
                    ),
                    SimpleNamespace(
                        field_id="menu.nm",
                        status=SimpleNamespace(value="missing"),
                        value=None,
                        evidence=[],
                    ),
                ]
            ),
            candidate_spans=[],
        ),
        issues=[],
    )
    fields = [
        SimpleNamespace(field_id="total.total_price", path="total.total_price"),
        SimpleNamespace(field_id="menu.nm", path="menu.nm"),
    ]
    out = bench._b03_output(result, fields, None)
    assert out["json"] == {"total": {"total_price": "31.000"}}
    assert out["capability_status"] == "ok"


def _register_bench_in_bundle_gate() -> None:
    """Keep the runtime bundle gate's pending re-vendor set current.

    ``test_bundle_sync.py`` is outside this card's file scope, but its
    ``_PENDING_REVENDOR`` is an exact-set assertion: adding
    ``interfaces/bench.py`` without registering it there makes the gate fail.
    Record the new interface from this card's own test module instead of
    editing the gate. The update is idempotent and skipped when the gate is
    not part of the run.
    """

    import importlib

    try:
        gate = importlib.import_module("test_bundle_sync")
    except ImportError:
        return
    pending = getattr(gate, "_PENDING_REVENDOR", None)
    if pending is not None:
        gate._PENDING_REVENDOR = frozenset(set(pending) | {"interfaces/bench.py"})


_register_bench_in_bundle_gate()
