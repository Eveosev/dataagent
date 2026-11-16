"""Dependency-based OCR engines: specs, install plans, isolated environments.

An :class:`EngineSpec` says how to build an engine environment: Python
version, requirement strings, optional package index, system programs that
must already exist, and which worker serves it (a built-in adapter of
``workers/engine_worker.py`` or an adapter script written for the engine).

Built-in recipes cover PaddleOCR, RapidOCR, EasyOCR and Tesseract. For any
other engine the agent researches the official documentation and saves a
spec (``engine spec``); the same plan → confirm → install → verify flow then
applies. Requirements in a recipe may be unpinned; the versions actually
installed are frozen into ``engine.lock.json`` and bound into the profile
digest through ``lock_digest``.

The component only runs ``uv`` inside ``<data_root>/ocr/engines/<name>/``.
System programs (``tesseract``, CUDA drivers, ...) are checked, never
installed: missing ones come back as ``needs_input`` with install hints for
the user to approve.
"""

from __future__ import annotations

import json
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dataagent_ocr.errors import ConfigError, EngineMissing, InstallRefused
from dataagent_ocr.profiles import ProfileStore, canonical, now_iso, sha256_hex

_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
_REQ = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-\[\],]*(\s*(==|>=|<=|~=|!=|<|>)\s*[A-Za-z0-9.*+!\-]+(\s*,\s*(==|>=|<=|~=|!=|<|>)\s*[A-Za-z0-9.*+!\-]+)*)?$")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SystemRequirement(_Model):
    name: str
    check: list[str] = Field(min_length=1)
    install_hints: dict[str, str] = Field(default_factory=dict)


class EngineSpec(_Model):
    name: str
    display_name: str
    python: str = "3.11"
    packages: list[str] = Field(min_length=1)
    index_url: str | None = None
    extra_index_urls: list[str] = Field(default_factory=list)
    system_requirements: list[SystemRequirement] = Field(default_factory=list)
    worker: str = Field(description="builtin:<engine> or adapter:<file name in the engine directory>")
    default_lang: str | None = None
    docs: list[str] = Field(default_factory=list, description="official sources the spec is based on")
    license: str | None = None
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        if not _NAME.match(value):
            raise ValueError("engine name must match [a-z0-9][a-z0-9_-]{0,31}")
        return value

    @field_validator("packages")
    @classmethod
    def _packages(cls, value: list[str]) -> list[str]:
        for req in value:
            if not _REQ.match(req.strip()) or req.strip().startswith("-"):
                raise ValueError(f"requirement {req!r} is not a plain requirement specifier")
        return [req.strip() for req in value]

    @field_validator("python")
    @classmethod
    def _python(cls, value: str) -> str:
        if not re.match(r"^3\.\d{1,2}$", value):
            raise ValueError("python must be a minor version such as 3.11")
        return value

    @field_validator("worker")
    @classmethod
    def _worker(cls, value: str) -> str:
        kind, _, name = value.partition(":")
        if kind == "builtin" and name in BUILTIN_WORKERS:
            return value
        if kind == "adapter" and re.match(r"^[A-Za-z0-9_-]+\.py$", name):
            return value
        raise ValueError(f"worker must be builtin:{{{','.join(sorted(BUILTIN_WORKERS))}}} or adapter:<file>.py")

    def digest(self) -> str:
        return "sha256:" + sha256_hex(canonical(self.model_dump(mode="json")))


BUILTIN_WORKERS = {"paddleocr", "rapidocr", "easyocr", "tesseract"}

RECIPES: dict[str, EngineSpec] = {
    "paddleocr": EngineSpec(
        name="paddleocr",
        display_name="PaddleOCR (PP-OCR pipeline, CPU)",
        python="3.11",
        packages=["paddlepaddle", "paddleocr"],
        worker="builtin:paddleocr",
        default_lang="ch",
        docs=[
            "https://github.com/PaddlePaddle/PaddleOCR",
            "https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html",
        ],
        license="Apache-2.0",
        notes=(
            "First run downloads detection/recognition models into the user cache. "
            "GPU builds need paddlepaddle-gpu from Paddle's own index; write a custom spec for that."
        ),
    ),
    "rapidocr": EngineSpec(
        name="rapidocr",
        display_name="RapidOCR (PP-OCR models on ONNX Runtime)",
        python="3.11",
        packages=["rapidocr-onnxruntime"],
        worker="builtin:rapidocr",
        docs=["https://github.com/RapidAI/RapidOCR"],
        license="Apache-2.0",
    ),
    "easyocr": EngineSpec(
        name="easyocr",
        display_name="EasyOCR (PyTorch, CPU)",
        python="3.11",
        packages=["easyocr"],
        worker="builtin:easyocr",
        default_lang="ch_sim+en",
        docs=["https://github.com/JaidedAI/EasyOCR"],
        license="Apache-2.0",
        notes="Installs PyTorch (large download). Language codes are joined with '+'.",
    ),
    "tesseract": EngineSpec(
        name="tesseract",
        display_name="Tesseract via pytesseract",
        python="3.11",
        packages=["pytesseract", "pillow"],
        worker="builtin:tesseract",
        default_lang="chi_sim+eng",
        system_requirements=[
            SystemRequirement(
                name="tesseract",
                check=["tesseract", "--version"],
                install_hints={
                    "darwin": "brew install tesseract tesseract-lang",
                    "linux": "sudo apt-get install -y tesseract-ocr tesseract-ocr-chi-sim",
                },
            )
        ],
        docs=["https://github.com/tesseract-ocr/tesseract", "https://github.com/madmaze/pytesseract"],
        license="Apache-2.0",
    ),
}


def engine_dir(data_root: Path, name: str) -> Path:
    return Path(data_root) / "ocr" / "engines" / name


def worker_source() -> bytes:
    return resources.files("dataagent_ocr.workers").joinpath("engine_worker.py").read_bytes()


def load_spec(data_root: Path, name: str) -> EngineSpec:
    custom = engine_dir(data_root, name) / "spec.json"
    if custom.is_file():
        return EngineSpec.model_validate_json(custom.read_text(encoding="utf-8"))
    if name in RECIPES:
        return RECIPES[name]
    raise ConfigError(
        f"no spec for OCR engine {name!r}",
        action="research the engine's official install docs and save a spec with `engine spec`",
    )


def save_spec(data_root: Path, spec: EngineSpec, adapter: bytes | None = None) -> Path:
    directory = engine_dir(data_root, spec.name)
    directory.mkdir(parents=True, exist_ok=True)
    kind, _, file_name = spec.worker.partition(":")
    if kind == "adapter":
        if adapter is None and not (directory / file_name).is_file():
            raise ConfigError(f"spec {spec.name} needs adapter file {file_name}")
        if adapter is not None:
            (directory / file_name).write_bytes(adapter)
    path = directory / "spec.json"
    path.write_text(spec.model_dump_json(indent=2), encoding="utf-8")
    ProfileStore(data_root).event("engine_spec_saved", engine=spec.name, spec_digest=spec.digest(), docs=spec.docs)
    return path


@dataclass
class InstallPlan:
    engine: str
    spec_digest: str
    env_dir: str
    steps: list[list[str]]
    system_requirements: list[dict]
    missing_system: list[dict]
    plan_digest: str

    def to_dict(self) -> dict:
        return {
            "engine": self.engine,
            "spec_digest": self.spec_digest,
            "env_dir": self.env_dir,
            "steps": self.steps,
            "system_requirements": self.system_requirements,
            "missing_system": self.missing_system,
            "plan_digest": self.plan_digest,
        }


def _python_in(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def _check_system(req: SystemRequirement) -> bool:
    if shutil.which(req.check[0]) is None:
        return False
    try:
        return subprocess.run(req.check, capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def plan_install(data_root: Path, spec: EngineSpec, *, uv: str | None = None, check_system: Callable[[SystemRequirement], bool] = _check_system) -> InstallPlan:
    uv = uv or shutil.which("uv")
    if not uv:
        raise EngineMissing("uv is not on PATH", action="install uv (https://docs.astral.sh/uv/)")
    directory = engine_dir(data_root, spec.name)
    venv = directory / ".venv"
    python = str(_python_in(venv))
    install = [uv, "pip", "install", "--python", python]
    if spec.index_url:
        install += ["--index-url", spec.index_url]
    for url in spec.extra_index_urls:
        install += ["--extra-index-url", url]
    install += spec.packages
    steps = [
        [uv, "venv", "--python", spec.python, str(venv)],
        install,
    ]
    system = [req.model_dump() for req in spec.system_requirements]
    missing = []
    host = "darwin" if sys.platform == "darwin" else ("linux" if sys.platform.startswith("linux") else sys.platform)
    for req in spec.system_requirements:
        if not check_system(req):
            missing.append({"name": req.name, "check": req.check, "install_hint": req.install_hints.get(host)})
    body = {
        "engine": spec.name,
        "spec_digest": spec.digest(),
        "steps": steps,
        "platform": [sys.platform, platform.machine()],
    }
    return InstallPlan(
        engine=spec.name,
        spec_digest=spec.digest(),
        env_dir=str(directory),
        steps=steps,
        system_requirements=system,
        missing_system=missing,
        plan_digest="sha256:" + sha256_hex(canonical(body)),
    )


Runner = Callable[[list[str]], subprocess.CompletedProcess]


def _run(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, timeout=3600)


def install(data_root: Path, spec: EngineSpec, *, confirm: str, runner: Runner = _run, uv: str | None = None, check_system: Callable[[SystemRequirement], bool] = _check_system) -> dict:
    """Execute a confirmed plan and write ``engine.lock.json``."""

    plan = plan_install(data_root, spec, uv=uv, check_system=check_system)
    if confirm != plan.plan_digest:
        raise InstallRefused(
            "install confirmation does not match the current plan",
            action=f"show the plan to the user and confirm with --confirm {plan.plan_digest}",
        )
    if plan.missing_system:
        names = ", ".join(item["name"] for item in plan.missing_system)
        raise InstallRefused(
            f"system requirements missing: {names}",
            action="ask the user to install them (see missing_system install_hint), then plan again",
        )
    directory = Path(plan.env_dir)
    directory.mkdir(parents=True, exist_ok=True)
    store = ProfileStore(data_root)
    store.event("engine_install_started", engine=spec.name, plan_digest=plan.plan_digest)
    for step in plan.steps:
        proc = runner(step)
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "")[-800:]
            store.event("engine_install_failed", engine=spec.name, step=step[1:3])
            raise InstallRefused(f"step {' '.join(step[1:3])} failed: {tail}", action="read the error, fix the spec, plan again")
    uv_bin = plan.steps[0][0]
    python = str(_python_in(directory / ".venv"))
    freeze = runner([uv_bin, "pip", "freeze", "--python", python])
    if freeze.returncode != 0:
        raise InstallRefused("could not freeze the engine environment")
    version = runner([python, "-c", "import sys;print('%d.%d.%d'%sys.version_info[:3])"])
    kind, _, name = spec.worker.partition(":")
    if kind == "builtin":
        worker_bytes = worker_source()
        (directory / "worker.py").write_bytes(worker_bytes)
    else:
        worker_bytes = (directory / name).read_bytes()
    worker_digest = "sha256:" + sha256_hex(worker_bytes)
    selftest = runner(worker_argv(data_root, spec, lang=spec.default_lang) + ["--selftest"])
    if selftest.returncode != 0:
        tail = (selftest.stderr or selftest.stdout or "")[-800:]
        raise InstallRefused(f"engine self-test failed: {tail}", action="check the engine docs; adjust packages or adapter")
    lock = {
        "engine": spec.name,
        "spec": spec.model_dump(mode="json"),
        "spec_digest": spec.digest(),
        "plan_digest": plan.plan_digest,
        "python": (version.stdout or "").strip(),
        "platform": [sys.platform, platform.machine()],
        "freeze": sorted(line for line in (freeze.stdout or "").splitlines() if line.strip()),
        "worker": spec.worker,
        "worker_digest": worker_digest,
        "selftest": (selftest.stdout or "").strip()[-400:],
        "installed_at": now_iso(),
    }
    lock_body = {k: v for k, v in lock.items() if k not in {"installed_at", "selftest"}}
    lock["lock_digest"] = "sha256:" + sha256_hex(canonical(lock_body))
    (directory / "engine.lock.json").write_text(json.dumps(lock, indent=2, ensure_ascii=False), encoding="utf-8")
    store.event("engine_installed", engine=spec.name, lock_digest=lock["lock_digest"], python=lock["python"])
    return lock


def read_lock(data_root: Path, name: str) -> dict:
    path = engine_dir(data_root, name) / "engine.lock.json"
    if not path.is_file():
        raise EngineMissing(f"OCR engine {name!r} is not installed", action=f"engine plan {name} / engine install {name}")
    return json.loads(path.read_text(encoding="utf-8"))


def worker_argv(data_root: Path, spec: EngineSpec, *, lang: str | None) -> list[str]:
    directory = engine_dir(data_root, spec.name)
    python = str(_python_in(directory / ".venv"))
    kind, _, name = spec.worker.partition(":")
    if kind == "builtin":
        argv = [python, "-I", str(directory / "worker.py"), "--engine", name]
    else:
        argv = [python, "-I", str(directory / name)]
    if lang:
        argv += ["--lang", lang]
    return argv


def current_worker_digest(data_root: Path, spec: EngineSpec) -> str:
    kind, _, name = spec.worker.partition(":")
    path = engine_dir(data_root, spec.name) / ("worker.py" if kind == "builtin" else name)
    if not path.is_file():
        raise EngineMissing(f"worker for {spec.name} is missing", action=f"engine install {spec.name}")
    return "sha256:" + sha256_hex(path.read_bytes())


def installed_engines(data_root: Path) -> list[dict]:
    base = Path(data_root) / "ocr" / "engines"
    out = []
    if base.is_dir():
        for directory in sorted(base.iterdir()):
            lock = directory / "engine.lock.json"
            if lock.is_file():
                data = json.loads(lock.read_text(encoding="utf-8"))
                out.append({"engine": data["engine"], "lock_digest": data["lock_digest"], "python": data.get("python"), "installed_at": data.get("installed_at")})
    return out
