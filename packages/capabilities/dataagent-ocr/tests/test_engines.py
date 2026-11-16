from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from dataagent_ocr import engines, load_active_engine
from dataagent_ocr.cli import main
from dataagent_ocr.errors import InstallRefused
from dataagent_ocr.probe import render_probe
from dataagent_ocr.workers import engine_worker

HERE = Path(__file__).parent


def run(capsys, monkeypatch, *argv):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    code = main(list(argv))
    return code, json.loads(capsys.readouterr().out)


def test_recipes_are_valid_specs():
    assert set(engines.RECIPES) == {"paddleocr", "rapidocr", "easyocr", "tesseract"}
    for spec in engines.RECIPES.values():
        assert spec.docs, spec.name


@pytest.mark.parametrize(
    "packages",
    [["paddleocr; os.system('x')"], ["-e git+https://x"], ["--index-url=https://evil"], ["pkg && rm -rf /"]],
)
def test_spec_rejects_non_requirement_strings(packages):
    with pytest.raises(ValueError):
        engines.EngineSpec(name="x", display_name="x", packages=packages, worker="builtin:rapidocr")


def test_plan_digest_and_missing_system(data_root):
    spec = engines.RECIPES["tesseract"]
    plan = engines.plan_install(data_root, spec, uv="/usr/bin/uv", check_system=lambda req: False)
    assert plan.missing_system[0]["name"] == "tesseract"
    assert plan.steps[0][:2] == ["/usr/bin/uv", "venv"]
    again = engines.plan_install(data_root, spec, uv="/usr/bin/uv", check_system=lambda req: False)
    assert again.plan_digest == plan.plan_digest
    with pytest.raises(InstallRefused, match="system requirements missing"):
        engines.install(data_root, spec, confirm=plan.plan_digest, uv="/usr/bin/uv", check_system=lambda req: False)


def test_install_requires_confirmed_digest_and_writes_lock(data_root):
    spec = engines.RECIPES["rapidocr"]
    calls: list[list[str]] = []

    def runner(argv):
        calls.append(argv)
        out = ""
        if argv[1:3] == ["pip", "freeze"]:
            out = "rapidocr-onnxruntime==1.4.4\nonnxruntime==1.20.0\n"
        elif "--selftest" in argv:
            out = '{"engine": "rapidocr", "engine_version": "1.4.4"}'
        elif argv[1:2] == ["-c"]:
            out = "3.11.9"
        return subprocess.CompletedProcess(argv, 0, out, "")

    with pytest.raises(InstallRefused, match="does not match"):
        engines.install(data_root, spec, confirm="sha256:wrong", runner=runner, uv="/usr/bin/uv")
    assert calls == []
    plan = engines.plan_install(data_root, spec, uv="/usr/bin/uv")
    lock = engines.install(data_root, spec, confirm=plan.plan_digest, runner=runner, uv="/usr/bin/uv")
    assert lock["freeze"] == ["onnxruntime==1.20.0", "rapidocr-onnxruntime==1.4.4"]
    assert lock["lock_digest"].startswith("sha256:")
    assert (engines.engine_dir(data_root, "rapidocr") / "worker.py").read_bytes() == engines.worker_source()
    assert calls[0][1] == "venv" and "rapidocr-onnxruntime" in calls[1]
    assert engines.installed_engines(data_root)[0]["engine"] == "rapidocr"


def test_researched_spec_with_adapter(capsys, monkeypatch, data_root, tmp_path):
    spec = {
        "name": "myocr",
        "display_name": "Vendor OCR SDK",
        "packages": ["vendor-ocr-sdk==2.3.1"],
        "worker": "adapter:adapter.py",
        "docs": ["https://vendor.example/docs/install"],
    }
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps(spec))
    adapter = tmp_path / "adapter.py"
    adapter.write_text("print('adapter')\n")
    code, out = run(capsys, monkeypatch, "engine", "spec", "--file", str(spec_file), "--adapter", str(adapter))
    assert code == 0 and out["next"] == "engine plan myocr"
    assert (engines.engine_dir(data_root, "myocr") / "adapter.py").is_file()
    code, out = run(capsys, monkeypatch, "engine", "plan", "myocr")
    assert code == 3 and out["plan"]["plan_digest"].startswith("sha256:")
    assert "vendor-ocr-sdk==2.3.1" in out["plan"]["steps"][1]


def test_paddle_result_parsing_v3_and_v2():
    v3 = [{"res": {"rec_texts": ["发票", "合计 12.50"], "rec_scores": [0.99, 0.87], "rec_boxes": [[1, 2, 30, 12], [1, 20, 60, 30]]}}]
    assert engine_worker.paddle_blocks(v3) == [
        {"text": "发票", "bbox": [1.0, 2.0, 30.0, 12.0], "confidence": 0.99},
        {"text": "合计 12.50", "bbox": [1.0, 20.0, 60.0, 30.0], "confidence": 0.87},
    ]
    v2 = [[[[[0, 0], [10, 0], [10, 5], [0, 5]], ("total", 0.9)]]]
    assert engine_worker.paddle_blocks(v2) == [{"text": "total", "bbox": [0.0, 0.0, 10.0, 5.0], "confidence": 0.9}]


def test_command_worker_end_to_end(capsys, monkeypatch, data_root):
    argv = json.dumps([sys.executable, "-I", str(HERE / "fake_worker.py")])
    code, out = run(
        capsys, monkeypatch, "configure-command", "--profile", "vendor", "--argv-json", argv,
        "--adapter", str(HERE / "fake_worker.py"),
    )
    assert code == 0
    code, out = run(capsys, monkeypatch, "verify", "--profile", "vendor")
    assert code == 0, out
    assert out["verification"]["confidence_source"] == "engine"
    engine = load_active_engine(data_root)
    try:
        blocks = engine.recognize(render_probe().image)
        assert blocks[0].confidence == 0.95 and engine.engine_version.startswith("9.9|vendor@r1")
    finally:
        engine.close()
