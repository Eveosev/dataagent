"""``dataagent run --case``: the 09-benchmark CLI adapter entry point.

Contract (``$BENCH/harness/adapters/dataagent-cli.py:29-33``)::

    dataagent run --case <case.json> --out <run_dir>/artifacts/<case_id> \
                  --config <cfg.json>

The command reads one normalized case, calls the capability that the case
belongs to, and always writes ``<out>/result.json``::

    {"status": "ok" | "failed",
     "output": {...} | null,
     "error": null | "...",
     "usage": {"tokens": 0, "cost_usd": 0.0},
     "case_id": "...", "task_id": "..."}

``status=ok`` means the case ran; ``output`` may still be a partial or
``needs_input`` capability result (for example field extraction without a
model proposal). ``status=failed`` always carries ``error`` and the process
exits 1, so the harness records a missing case instead of a fake empty
success (``harness/README.md`` §2).

B02 calls the OCR capability; B03 calls OCR and then the field-extraction
capability. OCR is always the locally pinned engine under ``$OCR_ROOT`` (or
``$DATAAGENT_OCR_ROOT``); a remote pin is refused because the egress gate
(T15) does not cover the CLI path yet.

B16 (entity alignment) and B17 (schema matching) run on the normalized
record/table fixtures instead of documents. The data layer catalog does not
yet register the DA03.2 identity-alignment or DA02.4 schema-mapping atoms, so
this entry carries the deterministic baselines for those two tasks: B16 ranks
the right candidates against the left record and emits ``expected.pairs``-
shaped entity pairs; B17 ranks target columns for the requested source field
and emits the ``mappings`` shape used by the oracle adapter. Both matchers are
pure, offline, and bounded by the case fixture; a malformed case raises
``BenchError`` so the harness records an explicit failure instead of an empty
success.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import sys
import traceback
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Sequence

TASKS = ("B02", "B03", "B16", "B17")

# Images the data layer's OCR atom can decode with Pillow.
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"})

# Which case input is the document to parse.
DOCUMENT_KINDS = frozenset({"file", "image", "pdf"})


class BenchError(RuntimeError):
    """A case could not be executed; the CLI still writes result.json."""


def _json_default(value: Any) -> Any:
    """Keep result.json parseable when a capability returns a rich value."""

    for method in ("model_dump", "to_plain"):
        dump = getattr(value, method, None)
        if callable(dump):
            try:
                return dump(mode="json")
            except TypeError:
                return dump()
    return str(value)


def write_result(
    out_dir: str | os.PathLike[str],
    *,
    case_id: str | None,
    task_id: str | None,
    status: str,
    output: Any = None,
    error: str | None = None,
    usage: dict[str, Any] | None = None,
    capability_status: str | None = None,
    issues: Sequence[dict[str, Any]] | None = None,
) -> Path:
    """Write ``<out>/result.json`` atomically and return its path."""

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": status,
        "output": output,
        "error": error,
        "usage": usage or {"tokens": 0, "cost_usd": 0.0},
        "case_id": case_id,
        "task_id": task_id,
        "capability_status": capability_status,
        "issues": list(issues or []),
    }
    path = out / "result.json"
    tmp = out / "result.json.tmp"
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path


def load_case(case_path: str | os.PathLike[str]) -> dict[str, Any]:
    """Read a normalized case and validate the fields the adapter relies on."""

    path = Path(case_path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BenchError(f"cannot read case {path}: {exc}") from exc
    try:
        case = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BenchError(f"case is not valid JSON: {path}: {exc}") from exc
    if not isinstance(case, dict):
        raise BenchError(f"case must be a JSON object: {path}")
    if not str(case.get("case_id") or "").strip():
        raise BenchError(f"case has no case_id: {path}")
    return case


def find_bench_root(case_path: str | os.PathLike[str]) -> Path:
    """Return ``$BENCH`` by walking up from ``tasks/<task>/dataset/cases/...``."""

    path = Path(case_path).resolve()
    for parent in path.parents:
        if (parent / "datasets.lock.json").is_file() and (parent / "harness").is_dir():
            return parent
    raise BenchError(f"cannot locate the 09-benchmark root from case path: {path}")


def repo_root_for(bench_root: str | os.PathLike[str]) -> Path:
    """Return the DataAgent checkout that owns ``$BENCH``."""

    root = Path(bench_root).resolve()
    for parent in root.parents:
        if (parent / ".git").exists():
            return parent
    if len(root.parents) > 3:
        return root.parents[3]
    return root


def dataset_dir_for(case_path: str | os.PathLike[str]) -> Path:
    """``.../tasks/<task>/dataset`` for a case file."""

    path = Path(case_path).resolve()
    for parent in path.parents:
        if parent.name == "dataset":
            return parent
    raise BenchError(f"cannot locate the dataset directory from case path: {path}")


def resolve_raw_root(
    bench_root: str | os.PathLike[str],
    repo_root: str | os.PathLike[str],
    environ: dict[str, str] | None = None,
) -> Path:
    """Resolve ``$BENCH/datasets.lock.json``'s ``raw_root`` (or its override).

    ``DATAAGENT_BENCH_RAW_ROOT`` wins when set; it may be absolute or relative
    to the repository root. No machine-specific path is hard-coded.
    """

    env = os.environ if environ is None else environ
    bench = Path(bench_root).resolve()
    repo = Path(repo_root).resolve()
    override = (env.get("DATAAGENT_BENCH_RAW_ROOT") or "").strip()
    if override:
        path = Path(override).expanduser()
        return (path if path.is_absolute() else repo / path).resolve()
    lock_path = bench / "datasets.lock.json"
    raw = ""
    if lock_path.is_file():
        try:
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise BenchError(f"datasets.lock.json is not valid JSON: {exc}") from exc
        raw = str(lock.get("raw_root") or "").strip()
    return (repo / (raw or "workspace/benchmark-data")).resolve()


def _relative_parts(value: str, *, label: str = "input reference") -> tuple[str, ...]:
    """Split a URL-style relative path, rejecting every escape spelling."""

    if not isinstance(value, str) or not value.strip():
        raise BenchError(f"{label} is empty: {value!r}")
    if value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", value):
        raise BenchError(f"{label} must be relative, not absolute: {value}")
    parts = PurePosixPath(value).parts
    if not parts or any(part in {"..", ""} for part in parts):
        raise BenchError(f"{label} escapes its root: {value}")
    if any("\\" in part for part in parts):
        raise BenchError(f"{label} must use '/' separators: {value}")
    return tuple(parts)


def _safe_component(value: str, *, label: str) -> str:
    parts = _relative_parts(value, label=label)
    if len(parts) != 1:
        raise BenchError(f"{label} must be one path segment: {value}")
    return parts[0]


def _contained_file(
    target: Path,
    root: Path,
    ref: str,
    *,
    hint: str = "",
) -> Path:
    """Resolve symlinks, then require the real file to stay under ``root``."""

    try:
        resolved_root = root.resolve(strict=False)
        resolved = target.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise BenchError(f"input not found: {ref} -> {target}: {exc}{hint}") from exc
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise BenchError(
            f"input reference escapes allowed root: {ref} -> {resolved} "
            f"(allowed root: {resolved_root})"
        ) from exc
    if not resolved.is_file():
        raise BenchError(f"input is not a regular file: {ref} -> {resolved}{hint}")
    return resolved


def resolve_ref(
    ref: str,
    *,
    task_id: str,
    dataset_dir: str | os.PathLike[str],
    raw_root: str | os.PathLike[str],
) -> Path:
    """Map a supported case input reference to a contained regular file.

    Only two forms are accepted: ``bench://<source>/<path>`` (under
    ``<raw_root>/<task_id>``) and ``fixtures/<path>`` (under the dataset
    directory). Absolute paths, traversal segments, and symlinks whose real
    target leaves those roots are rejected before any bytes are copied.
    """

    if not isinstance(ref, str) or not ref:
        raise BenchError("input reference must be a non-empty string")
    if ref.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", ref):
        raise BenchError(f"absolute input reference is not allowed: {ref}")

    dataset = Path(dataset_dir)
    raw = Path(raw_root)
    hint = (
        " (raw benchmark data is not staged; set DATAAGENT_BENCH_RAW_ROOT "
        "or run tools/fetch.py for this task)"
    )
    if ref.startswith("bench://"):
        source, separator, rest = ref[len("bench://") :].partition("/")
        if not separator or not source or not rest:
            raise BenchError(f"malformed bench:// reference: {ref}")
        source = _safe_component(source, label="bench:// source")
        task = _safe_component(task_id, label="task_id")
        # Check against the task root, not source: a symlinked source may
        # otherwise point at any host directory (review r2).
        task_root = raw / task
        target = task_root / source / Path(*_relative_parts(rest))
        return _contained_file(target, task_root, ref, hint=hint)
    if ref.startswith("fixtures/"):
        # Check against the dataset, not dataset/fixtures: a symlinked
        # fixtures directory must not escape the dataset either.
        target = dataset / Path(*_relative_parts(ref))
        return _contained_file(target, dataset, ref)
    raise BenchError(
        "unsupported input reference (expected bench://<source>/<path> "
        f"or fixtures/<path>): {ref}"
    )


def resolve_inputs(
    case: dict[str, Any],
    *,
    task_id: str,
    dataset_dir: str | os.PathLike[str],
    raw_root: str | os.PathLike[str],
) -> list[tuple[dict[str, Any], Path]]:
    """Resolve every declared input once, preserving declaration order."""

    resolved: list[tuple[dict[str, Any], Path]] = []
    for item in case.get("inputs") or []:
        if not isinstance(item, dict):
            continue
        ref = str(item.get("ref") or "").strip()
        if not ref:
            continue
        resolved.append(
            (
                item,
                resolve_ref(
                    ref,
                    task_id=task_id,
                    dataset_dir=dataset_dir,
                    raw_root=raw_root,
                ),
            )
        )
    if not resolved:
        raise BenchError(f"case {case.get('case_id')} declares no inputs")
    return resolved


def _status_value(status: Any) -> str:
    return str(getattr(status, "value", status))


def _issue_text(issues: Iterable[Any]) -> str:
    parts = []
    for issue in issues or []:
        code = getattr(issue, "code", "")
        message = getattr(issue, "message", "")
        parts.append(f"{code}: {message}" if code else str(message))
    return "; ".join(part for part in parts if part)


def _invoke(operation: str, payload: dict[str, Any], ctx: Any, runtime: Any) -> Any:
    from dataagent_data.invoke import invoke

    return invoke(operation, payload, ctx, runtime=runtime)


def _require_result(result: Any, operation: str) -> Any:
    status = _status_value(getattr(result, "status", ""))
    if status == "failed":
        raise BenchError(
            f"{operation} failed: {_issue_text(getattr(result, 'issues', [])) or 'unknown error'}"
        )
    if getattr(result, "data", None) is None:
        raise BenchError(f"{operation} returned no data (status={status})")
    return result


def _load_content(runtime: Any, document: Any) -> Any:
    from dataagent_data.preparation.documents import load_document_content

    return load_document_content(runtime, document)


def _make_runtime(workspace: Path, data_root: Path, ocr_engine: Any) -> Any:
    from dataagent_data.runtime import create

    return create(workspace_root=workspace, data_root=data_root, ocr_engine=ocr_engine)


def _make_context(runtime: Any, workspace: Path) -> Any:
    from dataagent_runtime.policy.context import resolve_context

    return resolve_context(runtime=runtime, workspace_root=workspace).context


def _ocr_source_dir(
    *,
    repo_root: Path,
    bench_root: Path,
    environ: dict[str, str] | None = None,
) -> Path | None:
    """The verified OCR directory (the one holding ``active.json``)."""

    env = os.environ if environ is None else environ
    explicit = (env.get("OCR_ROOT") or env.get("DATAAGENT_OCR_ROOT") or "").strip()
    candidates: list[Path] = []
    if explicit:
        directory = Path(explicit).expanduser()
        if directory.name != "ocr":
            directory = directory / "ocr"
        if not (directory / "active.json").is_file():
            raise BenchError(
                "OCR_ROOT is not a verified OCR directory (active.json missing): "
                f"{directory}"
            )
        return directory.resolve()
    candidates.extend(
        [
            Path(os.path.expanduser("~")) / ".dataagent" / "ocr",
            repo_root / ".dataagent" / "ocr",
            bench_root / ".dataagent" / "ocr",
        ]
    )
    for candidate in candidates:
        directory = candidate
        if directory.name != "ocr":
            directory = directory / "ocr"
        if (directory / "active.json").is_file():
            return directory.resolve()
    return None


def _mirror_ocr_root(source: Path, scratch: Path) -> Path:
    """Give the pinned engine a writable quality/event directory.

    The verified OCR directory is an input: copying its pin and symlinking the
    immutable profile/engine trees keeps ``usage.jsonl`` writes out of it while
    the engine still resolves its worker through the pin's own paths.
    """

    scratch.mkdir(parents=True, exist_ok=True)
    data_root = scratch / "ocr-data"
    dest = data_root / "ocr"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    shutil.copy2(source / "active.json", dest / "active.json")
    for name in ("profiles", "verifications", "engines"):
        origin = source / name
        if origin.is_dir():
            os.symlink(origin.resolve(), dest / name, target_is_directory=True)
    (dest / "quality").mkdir()
    (dest / "events.jsonl").touch()
    return data_root


def _load_local_engine(
    *,
    repo_root: Path,
    bench_root: Path,
    scratch: Path,
    environ: dict[str, str] | None = None,
) -> Any:
    source = _ocr_source_dir(repo_root=repo_root, bench_root=bench_root, environ=environ)
    if source is None:
        raise BenchError(
            "no local OCR engine: set OCR_ROOT to a verified OCR directory "
            "(dataagent setup --ocr-root <dir>)"
        )
    try:
        from dataagent_ocr.adapter import load_active_engine
    except Exception as exc:  # noqa: BLE001 - optional component, must be explicit
        raise BenchError(f"OCR component is not installed: {type(exc).__name__}: {exc}") from exc
    data_root = _mirror_ocr_root(source, scratch)
    try:
        engine = load_active_engine(data_root)
    except Exception as exc:  # noqa: BLE001 - pin/profile/engine problems
        raise BenchError(f"local OCR pin under {source} is not usable: {exc}") from exc
    if getattr(engine, "remote", False):
        engine.close()
        raise BenchError(
            f"OCR pin under {source} is remote; the benchmark entry needs the "
            "local engine (the egress gate does not cover the CLI path)"
        )
    return engine


def _stage_documents(
    inputs: Sequence[tuple[dict[str, Any], Path]],
    workspace: Path,
) -> list[tuple[dict[str, Any], Path, str]]:
    """Copy OCR inputs into the runtime workspace (paths must be relative)."""

    staged: list[tuple[dict[str, Any], Path, str]] = []
    for index, (item, path) in enumerate(inputs):
        if str(item.get("kind") or "") not in DOCUMENT_KINDS:
            continue
        suffix = path.suffix.lower()
        if suffix != ".pdf" and suffix not in IMAGE_SUFFIXES:
            raise BenchError(f"unsupported document input: {path.name}")
        rel = f"input-{index}{suffix}"
        shutil.copyfile(path, workspace / rel)
        staged.append((item, path, rel))
    return staged


def _ocr_document(
    *,
    runtime: Any,
    ctx: Any,
    workspace: Path,
    path: Path,
    rel: str,
) -> Any:
    from dataagent_data import helpers

    file_ref = helpers.file_ref(runtime, rel, scope_ref=ctx.scope_ref)
    operation = "ocr_pdf" if path.suffix.lower() == ".pdf" else "ocr_image"
    result = _invoke(operation, {"file_ref": file_ref.model_dump(mode="json")}, ctx, runtime)
    _require_result(result, operation)
    return result.data.document


def _b02_output(contents: Sequence[Any]) -> dict[str, Any]:
    """Map OCR document content to the harness output shape.

    ``text_ned`` reads ``text``; ``reading_order_accuracy`` reads ``blocks``
    (``order`` + ``text``); ``table_teds`` reads ``tables``. OCR does not infer
    table structure, so ``tables`` stays empty instead of being invented.
    """

    blocks: list[dict[str, Any]] = []
    texts: list[str] = []
    order = 0
    for content in contents:
        text = getattr(content, "full_text", "") or ""
        if text:
            texts.append(text)
        for page in getattr(content, "pages", []) or []:
            for block in getattr(page, "blocks", []) or []:
                order += 1
                item: dict[str, Any] = {
                    "order": order,
                    "text": getattr(block, "text", ""),
                    "page": getattr(page, "page", 1),
                }
                bbox = getattr(block, "bbox", None)
                if bbox:
                    item["bbox"] = list(bbox)
                blocks.append(item)
    return {"text": "\n".join(texts), "blocks": blocks, "tables": []}


def _schema_type(node: Any) -> str:
    if not isinstance(node, dict):
        return "string"
    value = node.get("type")
    if isinstance(value, str) and value != "null":
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item != "null":
                return item
    for key in ("anyOf", "oneOf", "allOf"):
        items = node.get(key)
        if isinstance(items, list):
            for item in items:
                picked = _schema_type(item)
                if picked != "null":
                    return picked
    return "string"


def _resolve_schema_ref(node: Any, root: dict[str, Any]) -> Any:
    if not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return node
    current: Any = root
    for token in ref[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            return node
        current = current[token]
    return current


def _fields_from_schema(schema: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """Flatten a JSON Schema into ``(field_id, name, path, value_type)``."""

    out: list[tuple[str, str, str, str]] = []
    seen: set[str] = set()

    def add(path: str, value_type: str) -> None:
        if len(out) >= 200 or path in seen:
            return
        seen.add(path)
        out.append((path, path.rsplit(".", 1)[-1], path, value_type))

    def walk(node: Any, prefix: str) -> None:
        node = _resolve_schema_ref(node, schema)
        if not isinstance(node, dict):
            return
        properties = node.get("properties")
        if isinstance(properties, dict):
            for name, child in properties.items():
                child = _resolve_schema_ref(child, schema)
                path = f"{prefix}.{name}" if prefix else str(name)
                if isinstance(child, dict) and isinstance(child.get("properties"), dict):
                    walk(child, path)
                else:
                    add(path, _schema_type(child))
            return
        if prefix:
            add(prefix, _schema_type(node))

    walk(schema, "")
    return out


def _fields_from_rules(text: str) -> list[tuple[str, str, str, str]]:
    """Extract value paths from an ExtractBench-style field-rules fixture."""

    start = text.find("{")
    if start < 0:
        return []
    try:
        rules = json.loads(text[start:])
    except json.JSONDecodeError:
        return []
    if not isinstance(rules, dict):
        return []
    out: list[tuple[str, str, str, str]] = []
    seen: set[str] = set()
    for key, spec in rules.items():
        if not isinstance(key, str) or not key or key in seen:
            continue
        value_type = "string"
        if isinstance(spec, dict):
            comparator = spec.get("comparator")
            if isinstance(comparator, dict):
                # A container node (e.g. ``line_items``), not a value path.
                continue
            if comparator in {"number", "amount", "money", "percent"}:
                value_type = "number"
            elif comparator is True:
                value_type = "boolean"
        seen.add(key)
        out.append((key, key.rsplit(".", 1)[-1], key, value_type))
        if len(out) >= 200:
            break
    return out


_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _fields_from_instruction(text: str) -> list[tuple[str, str, str, str]]:
    """Read the ``- <object>：<field names>`` structure of an instruction."""

    out: list[tuple[str, str, str, str]] = []
    seen: set[str] = set()
    for line in text.splitlines():
        match = re.match(r"\s*[-*]\s*([A-Za-z_][A-Za-z0-9_]*)\s*[：:]\s*(.*)", line)
        if not match:
            continue
        parent, rest = match.group(1), match.group(2)
        names: list[str] = []
        for group in re.findall(r"[（(]([^）)]*)[）)]", rest):
            names.extend(_IDENTIFIER.findall(group))
        if not names:
            names = _IDENTIFIER.findall(rest)
        names = [
            name
            for name in dict.fromkeys(names)
            if name.lower() not in {"and", "or", "the", "etc"}
        ]
        if not names:
            names = [parent]
        for name in names:
            if len(out) >= 200:
                break
            path = parent if name == parent else f"{parent}.{name}"
            if path in seen:
                continue
            seen.add(path)
            out.append((path, name, path, "string"))
    return out


def _fields_for_case(
    inputs: Sequence[tuple[dict[str, Any], Path]],
) -> list[Any]:
    """Build the extraction field list from schema/rules/instruction inputs."""

    from dataagent_contracts.core import FieldSpec

    specs: list[tuple[str, str, str, str]] = []
    for wanted in ("rules", "schema", "instruction"):
        for item, path in inputs:
            if str(item.get("kind") or "") != wanted:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as exc:
                raise BenchError(f"cannot read {wanted} input {path}: {exc}") from exc
            if wanted == "schema":
                try:
                    schema = json.loads(text)
                except json.JSONDecodeError:
                    continue
                specs.extend(_fields_from_schema(schema) if isinstance(schema, dict) else [])
            elif wanted == "rules":
                specs.extend(_fields_from_rules(text))
            else:
                specs.extend(_fields_from_instruction(text))
            if specs:
                break
        if specs:
            break
    if not specs:
        # Keep the capability call honest: ask for one generic value rather
        # than inventing a field table. With no proposal it returns
        # needs_input and the output records why there are no values.
        specs = [("content", "content", "content", "string")]
    fields = []
    seen: set[str] = set()
    for field_id, name, path, value_type in specs:
        if field_id in seen:
            continue
        seen.add(field_id)
        fields.append(
            FieldSpec(
                field_id=field_id,
                name=name or field_id,
                path=path or field_id,
                value_type=value_type or "string",
                nullable=True,
            )
        )
    return fields


def _path_parts(path: str) -> list[str | int]:
    parts: list[str | int] = []
    for chunk in str(path).split("."):
        if not chunk:
            continue
        match = re.fullmatch(r"([^\[]+)((?:\[\d+\])*)", chunk)
        if not match:
            parts.append(chunk)
            continue
        parts.append(match.group(1))
        for index in re.findall(r"\[(\d+)\]", match.group(2)):
            parts.append(int(index))
    return parts


def _set_path(root: dict[str, Any], path: str, value: Any) -> None:
    """Set a dotted/indexed path such as ``line_items[0].description``."""

    parts = _path_parts(path)
    if not parts or not isinstance(parts[0], str):
        return
    current: Any = root
    for index, part in enumerate(parts[:-1]):
        following = parts[index + 1]
        if isinstance(part, int):
            if not isinstance(current, list):
                return
            while len(current) <= part:
                current.append(None)
            if current[part] is None:
                current[part] = [] if isinstance(following, int) else {}
            current = current[part]
        else:
            if not isinstance(current, dict):
                return
            if current.get(part) is None:
                current[part] = [] if isinstance(following, int) else {}
            current = current[part]
    last = parts[-1]
    if isinstance(last, int):
        if not isinstance(current, list):
            return
        while len(current) <= last:
            current.append(None)
        current[last] = value
    elif isinstance(current, dict):
        current[last] = value


def _field_value(field_value: Any) -> Any:
    status = _status_value(getattr(field_value, "status", ""))
    if status in {"extracted", "low_confidence"}:
        return getattr(field_value, "value", None)
    return None


def _evidence(field_value: Any, content: Any) -> tuple[int | None, str | None]:
    evidence = list(getattr(field_value, "evidence", []) or [])
    if not evidence:
        return None, None
    anchor = evidence[0]
    page = getattr(getattr(anchor, "selector", None), "page", None)
    try:
        from dataagent_data.anchors import AnchorResolver

        resolved = AnchorResolver(content).resolve(anchor)
    except Exception:  # noqa: BLE001 - evidence is best effort, never a failure
        return page, None
    return page, resolved.text


def _b03_output(result: Any, fields: Sequence[Any], content: Any) -> dict[str, Any]:
    """Map the extraction capability result to the harness output shape.

    ``value_f1``/``record_completeness`` read ``json``; ``evidence_span_f1``
    reads ``spans``; ``evidence_page_f1`` reads ``pages``. When there is no
    model proposal the capability returns ``needs_input``: the output carries
    the candidate spans and the issue, but no invented field values.
    """

    out: dict[str, Any] = {
        "json": {},
        "spans": [],
        "pages": {},
        "fields": [
            {"field_id": field.field_id, "path": field.path} for field in fields
        ],
        "capability_status": _status_value(getattr(result, "status", "")),
        "issues": [
            {
                "code": getattr(issue, "code", ""),
                "severity": _status_value(getattr(issue, "severity", "")),
                "message": getattr(issue, "message", ""),
            }
            for issue in getattr(result, "issues", []) or []
        ],
    }
    data = getattr(result, "data", None)
    candidates = list(getattr(data, "candidate_spans", []) or []) if data is not None else []
    if candidates:
        out["candidate_spans"] = [
            {
                "page": span.page,
                "text": span.text,
                "char_start": span.char_start,
                "char_end": span.char_end,
            }
            for span in candidates
        ]
    record = getattr(data, "record", None) if data is not None else None
    if record is None:
        return out
    paths = {field.field_id: field.path for field in fields}
    values: dict[str, Any] = {}
    for field_value in getattr(record, "fields", []) or []:
        value = _field_value(field_value)
        if value is None:
            continue
        path = paths.get(getattr(field_value, "field_id", ""), getattr(field_value, "field_id", ""))
        if not path:
            continue
        _set_path(values, path, value)
        page, text = _evidence(field_value, content)
        if page is not None:
            out["pages"][path] = page
        if text:
            out["spans"].append({"field": path, "text": text, "page": page or 1})
    out["json"] = values
    return out


# B16/B17 baselines. The data layer's 32-atom catalog does not register the
# DA03.2 identity-alignment / DA02.4 schema-mapping atoms yet, so the benchmark
# entry carries deterministic, fixture-local matchers. Both are lexical
# baselines (not inference); thresholds are calibrated on the development
# split and keep the output honest: below the threshold the answer is an empty
# pair list / explicit null, never a guess.
_B16_MATCH_THRESHOLD = 0.40
_B17_MATCH_THRESHOLD = 0.35

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "by",
        "for",
        "from",
        "in",
        "is",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "with",
    }
)

_TOKEN_SYNONYMS = {
    "addr": "address",
    "amt": "amount",
    "cat": "category",
    "cd": "code",
    "chg": "change",
    "changes": "change",
    "desc": "description",
    "dt": "date",
    "info": "information",
    "mo": "month",
    "nm": "name",
    "no": "number",
    "num": "number",
    "pct": "percent",
    "qty": "quantity",
    "stat": "status",
    "val": "value",
    "wk": "week",
    "yr": "year",
}


def _normalize_text(value: Any) -> str:
    """NFKC, camel-case split, casefold, and non-alphanumeric to space."""

    text = unicodedata.normalize("NFKC", str(value or ""))
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _stem_token(token: str) -> str:
    """A small suffix stemmer: enough for charger/charging and controller(s)."""

    for suffix in ("ing", "ers", "er", "ies", "es", "s"):
        if len(token) > 4 and token.endswith(suffix):
            if suffix == "ies":
                return token[: -len(suffix)] + "y"
            return token[: -len(suffix)]
    return token


def _text_tokens(value: Any) -> set[str]:
    tokens = {
        _stem_token(token)
        for token in re.findall(r"[a-z0-9]+", _normalize_text(value))
        if token not in _STOPWORDS
    }
    return tokens


def _field_tokens(value: Any) -> list[str]:
    """Token list for schema matching; keeps order for greedy soft matching."""

    return [
        _TOKEN_SYNONYMS.get(token, token)
        for token in re.findall(r"[a-z0-9]+", _normalize_text(value))
        if token not in _STOPWORDS
    ]


def _char_ngrams(value: Any, size: int = 3) -> set[str]:
    text = _normalize_text(value).replace(" ", "")
    return {text[index : index + size] for index in range(max(0, len(text) - size + 1))}


def _set_dice(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return 2 * len(left & right) / (len(left) + len(right))


def _set_jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _set_containment(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def _title_of(record: dict[str, Any]) -> str:
    return str(record.get("name") or record.get("title") or "")


def _record_text(record: dict[str, Any], fields: Sequence[str]) -> str:
    return " ".join(str(record[field]) for field in fields if record.get(field))


def _candidate_token_idf(candidates: Sequence[dict[str, Any]]) -> dict[str, float]:
    """IDF over the candidate titles so rare model/brand words dominate."""

    counts: dict[str, int] = {}
    for candidate in candidates:
        for token in _text_tokens(_title_of(candidate)):
            counts[token] = counts.get(token, 0) + 1
    total = len(candidates)
    return {
        token: math.log((total + 1) / (frequency + 0.5)) + 1.0
        for token, frequency in counts.items()
    }


def _entity_similarity(
    left: dict[str, Any],
    right: dict[str, Any],
    idf: dict[str, float],
) -> float:
    """Score one left/right record pair for the B16 entity-alignment baseline."""

    left_title = _title_of(left)
    right_title = _title_of(right)
    left_tokens = _text_tokens(left_title)
    right_tokens = _text_tokens(right_title)

    title_jaccard = _set_jaccard(left_tokens, right_tokens)
    title_containment = _set_containment(left_tokens, right_tokens)
    title_ngrams = _set_dice(_char_ngrams(left_title), _char_ngrams(right_title))
    weighted_intersection = sum(
        idf.get(token, 1.0) for token in left_tokens & right_tokens
    )
    weighted_right = sum(idf.get(token, 1.0) for token in right_tokens) or 1.0
    weighted_union = sum(idf.get(token, 1.0) for token in left_tokens | right_tokens) or 1.0
    weighted_cover = weighted_intersection / weighted_right
    weighted_jaccard = weighted_intersection / weighted_union
    title = (
        0.20 * title_jaccard
        + 0.22 * title_containment
        + 0.18 * title_ngrams
        + 0.20 * weighted_cover
        + 0.20 * weighted_jaccard
    )

    left_body = _text_tokens(
        _record_text(left, ("name", "title", "description", "authors", "venue"))
    )
    right_body = _text_tokens(
        _record_text(right, ("name", "title", "description", "authors", "venue"))
    )
    body = _set_jaccard(left_body, right_body)

    left_manufacturer = _text_tokens(left.get("manufacturer") or "")
    right_manufacturer = _text_tokens(right.get("manufacturer") or "")
    if left_manufacturer and right_manufacturer:
        brand = (
            1.0
            if left_manufacturer == right_manufacturer
            else _set_jaccard(left_manufacturer, right_manufacturer)
        )
    elif right_manufacturer and right_manufacturer & left_tokens:
        brand = 1.0
    else:
        brand = 0.0

    left_models = {
        token for token in left_tokens if any(char.isdigit() for char in token) and len(token) >= 4
    }
    right_models = {
        token
        for token in right_tokens
        if any(char.isdigit() for char in token) and len(token) >= 4
    }
    model = _set_containment(left_models, right_models)

    year = (
        1.0
        if left.get("year")
        and right.get("year")
        and str(left.get("year")) == str(right.get("year"))
        else 0.0
    )
    price = (
        1.0
        if left.get("price")
        and right.get("price")
        and _normalize_text(left.get("price")) == _normalize_text(right.get("price"))
        else 0.0
    )

    return (
        0.42 * title
        + 0.14 * body
        + 0.18 * brand
        + 0.12 * model
        + 0.10 * year
        + 0.04 * price
    )


def _align_entities(fixture: dict[str, Any]) -> list[dict[str, str]]:
    """B16 baseline: pick the best right candidate for the left record."""

    left = fixture.get("left")
    if not isinstance(left, dict):
        raise BenchError("B16 fixture has no left record")
    left_id = str(left.get("id") or "").strip()
    if not left_id:
        raise BenchError("B16 fixture left record has no id")

    raw_candidates = fixture.get("right_candidates")
    if not isinstance(raw_candidates, list):
        raise BenchError("B16 fixture has no right_candidates list")
    candidates = [
        candidate
        for candidate in raw_candidates
        if isinstance(candidate, dict) and str(candidate.get("id") or "").strip()
    ]
    if not candidates:
        return []

    idf = _candidate_token_idf(candidates)
    ranked = sorted(
        (
            (_entity_similarity(left, candidate, idf), str(candidate["id"]).strip())
            for candidate in candidates
        ),
        key=lambda item: (-item[0], item[1]),
    )
    best_score, best_right_id = ranked[0]
    if best_score < _B16_MATCH_THRESHOLD:
        return []
    return [{"left_id": left_id, "right_id": best_right_id}]


def _b16_output(fixture: dict[str, Any]) -> dict[str, Any]:
    """The oracle adapter's B16 shape: ``{"pairs": [{"left_id", "right_id"}]}``."""

    return {"pairs": _align_entities(fixture)}


def _consonants(token: str) -> str:
    return "".join(char for char in token if char not in "aeiouy")


def _tokens_equivalent(left: str, right: str) -> bool:
    """Exact, prefix, or consonant-skeleton match (BRGH_CD vs borough)."""

    if left == right:
        return True
    if len(left) >= 3 and len(right) >= 3:
        if left.startswith(right) or right.startswith(left):
            return True
        left_consonants = _consonants(left)
        right_consonants = _consonants(right)
        if len(left_consonants) >= 2 and left_consonants == right_consonants:
            return True
    return False


def _soft_overlap(left: Sequence[str], right: Sequence[str]) -> int:
    """Greedy one-to-one token matches; used for abbreviation-aware scoring."""

    used = [False] * len(right)
    matched = 0
    for token in left:
        for index, other in enumerate(right):
            if used[index]:
                continue
            if _tokens_equivalent(token, other):
                used[index] = True
                matched += 1
                break
    return matched


def _column_samples(column: dict[str, Any]) -> set[str]:
    samples = set()
    for value in column.get("samples") or []:
        normalized = _normalize_text(value)
        if normalized:
            samples.add(normalized)
    return samples


def _schema_similarity(
    source_field: str,
    source_column: dict[str, Any],
    target_column: dict[str, Any],
) -> float:
    """Score one source-field/target-column pair for the B17 baseline."""

    target_name = str(target_column.get("name") or "")
    source_tokens = _field_tokens(source_field)
    target_tokens = _field_tokens(target_name)
    matched = _soft_overlap(source_tokens, target_tokens)
    union = len(source_tokens) + len(target_tokens) - matched
    token_jaccard = matched / union if union else 0.0
    token_containment = (
        matched / min(len(source_tokens), len(target_tokens))
        if source_tokens and target_tokens
        else 0.0
    )
    ngram_dice = _set_dice(_char_ngrams(source_field), _char_ngrams(target_name))
    sample_dice = _set_dice(_column_samples(source_column), _column_samples(target_column))
    exact = 1.0 if _normalize_text(source_field) == _normalize_text(target_name) else 0.0

    return (
        0.28 * exact
        + 0.18 * token_jaccard
        + 0.20 * token_containment
        + 0.14 * ngram_dice
        + 0.20 * sample_dice
    )


def _find_column(table: dict[str, Any], name: str) -> dict[str, Any] | None:
    columns = table.get("columns")
    if not isinstance(columns, list):
        return None
    for column in columns:
        if isinstance(column, dict) and str(column.get("name") or "") == name:
            return column
    wanted = _normalize_text(name)
    for column in columns:
        if isinstance(column, dict) and _normalize_text(column.get("name")) == wanted:
            return column
    return None


def _map_schema_field(fixture: dict[str, Any]) -> str | None:
    """B17 baseline: the top-1 target column, or ``None`` when nothing matches."""

    source_field = str(fixture.get("source_field") or "").strip()
    if not source_field:
        raise BenchError("B17 fixture has no source_field")
    source_table = fixture.get("source_table")
    target_table = fixture.get("target_table")
    if not isinstance(source_table, dict) or not isinstance(target_table, dict):
        raise BenchError("B17 fixture has no source_table/target_table")
    source_column = _find_column(source_table, source_field)
    if source_column is None:
        raise BenchError(f"B17 fixture source table has no column {source_field!r}")
    raw_columns = target_table.get("columns")
    if not isinstance(raw_columns, list) or not raw_columns:
        raise BenchError("B17 fixture target table has no columns")

    ranked = sorted(
        (
            (
                _schema_similarity(source_field, source_column, column),
                str(column.get("name") or ""),
            )
            for column in raw_columns
            if isinstance(column, dict) and str(column.get("name") or "").strip()
        ),
        key=lambda item: (-item[0], item[1]),
    )
    if not ranked or ranked[0][0] < _B17_MATCH_THRESHOLD:
        return None
    return ranked[0][1]


def _b17_output(fixture: dict[str, Any]) -> dict[str, Any]:
    """The oracle adapter's B17 shape, with an explicit ``null`` for no match."""

    source_field = str(fixture.get("source_field") or "").strip()
    return {
        "mappings": [
            {
                "source_field": source_field,
                "target_field": _map_schema_field(fixture),
            }
        ]
    }


def _read_fixture_input(
    inputs: Sequence[tuple[dict[str, Any], Path]],
    kinds: frozenset[str],
    *,
    task_id: str,
) -> dict[str, Any]:
    """Read the first resolved input whose declared kind belongs to ``kinds``."""

    for item, path in inputs:
        if str(item.get("kind") or "") not in kinds:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise BenchError(f"cannot read {task_id} fixture {path}: {exc}") from exc
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise BenchError(f"{task_id} fixture is not valid JSON: {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise BenchError(f"{task_id} fixture must be a JSON object: {path}")
        return payload
    raise BenchError(f"{task_id} case has no {sorted(kinds)[0]} input")


def _execute_b16(
    inputs: Sequence[tuple[dict[str, Any], Path]],
) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
    fixture = _read_fixture_input(inputs, frozenset({"record_pair"}), task_id="B16")
    return _b16_output(fixture), "ok", []


def _execute_b17(
    inputs: Sequence[tuple[dict[str, Any], Path]],
) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
    fixture = _read_fixture_input(inputs, frozenset({"table"}), task_id="B17")
    return _b17_output(fixture), "ok", []


def _execute_task(
    *,
    task_id: str,
    case: dict[str, Any],
    inputs: list[tuple[dict[str, Any], Path]],
    bench_root: Path,
    repo_root: Path,
    scratch: Path,
) -> tuple[dict[str, Any], str | None, list[dict[str, Any]]]:
    """Run the task's capability chain; return (output, status, issues)."""

    if task_id == "B16":
        return _execute_b16(inputs)
    if task_id == "B17":
        return _execute_b17(inputs)

    workspace = scratch / "workspace"
    data_root = scratch / "data"
    workspace.mkdir(parents=True, exist_ok=True)
    data_root.mkdir(parents=True, exist_ok=True)
    staged = _stage_documents(inputs, workspace)
    if not staged:
        raise BenchError(f"{task_id} case has no file/image input to parse")

    engine = _load_local_engine(
        repo_root=repo_root, bench_root=bench_root, scratch=scratch
    )
    runtime = None
    try:
        runtime = _make_runtime(workspace, data_root, engine)
        ctx = _make_context(runtime, workspace)
        if task_id == "B02":
            contents = []
            for _item, path, rel in staged:
                document = _ocr_document(
                    runtime=runtime, ctx=ctx, workspace=workspace, path=path, rel=rel
                )
                contents.append(_load_content(runtime, document))
            return _b02_output(contents), "ok", []
        document = _ocr_document(
            runtime=runtime,
            ctx=ctx,
            workspace=workspace,
            path=staged[0][1],
            rel=staged[0][2],
        )
        content = _load_content(runtime, document)
        fields = _fields_for_case(inputs)
        result = _invoke(
            "extract_fields_to_schema",
            {
                "document_ref": document.model_dump(mode="json"),
                "fields": [field.model_dump(mode="json") for field in fields],
            },
            ctx,
            runtime,
        )
        _require_result(result, "extract_fields_to_schema")
        output = _b03_output(result, fields, content)
        issues = output.get("issues") or []
        return output, _status_value(result.status), issues
    finally:
        if runtime is not None:
            close = getattr(runtime, "close", None)
            if callable(close):
                close()
        engine.close()


def _execute_task_dispatch(
    **kwargs: Any,
) -> tuple[dict[str, Any], str | None, list[dict[str, Any]]]:
    return _execute_task(**kwargs)


def run_case(
    case_path: str | os.PathLike[str],
    out_dir: str | os.PathLike[str],
    config_path: str | os.PathLike[str] | None = None,
    *,
    dispatch: Callable[..., tuple[dict[str, Any], str | None, list[dict[str, Any]]]] | None = None,
) -> int:
    """Execute one case, always write result.json, and return the exit code."""

    out = Path(out_dir)
    case_id: str | None = None
    task_id: str | None = None
    capability_status: str | None = None
    issues: list[dict[str, Any]] = []
    try:
        out.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"dataagent run: cannot create output directory {out}: {exc}", file=sys.stderr)
        return 2

    scratch = out / ".bench"
    try:
        if scratch.exists():
            shutil.rmtree(scratch)
        case = load_case(case_path)
        case_id = str(case.get("case_id"))
        task_id = str(case.get("task_id") or "").strip() or None
        if task_id not in TASKS:
            raise BenchError(
                f"unsupported task_id: {task_id or '<missing>'} "
                f"(expected {' or '.join(TASKS)})"
            )
        bench_root = find_bench_root(case_path)
        repo_root = repo_root_for(bench_root)
        dataset_dir = dataset_dir_for(case_path)
        raw_root = resolve_raw_root(bench_root, repo_root)
        inputs = resolve_inputs(
            case, task_id=task_id, dataset_dir=dataset_dir, raw_root=raw_root
        )
        output, capability_status, issues = (dispatch or _execute_task_dispatch)(
            task_id=task_id,
            case=case,
            inputs=inputs,
            bench_root=bench_root,
            repo_root=repo_root,
            scratch=scratch,
        )
        write_result(
            out,
            case_id=case_id,
            task_id=task_id,
            status="ok",
            output=output,
            error=None,
            capability_status=capability_status,
            issues=issues,
        )
        return 0
    except BenchError as exc:
        error = str(exc)
        print(f"dataagent run: {case_id or case_path}: {error}", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 - the harness needs an explicit failure
        error = f"{type(exc).__name__}: {exc}"
        if os.environ.get("DATAAGENT_BENCH_DEBUG"):
            traceback.print_exc()
        print(f"dataagent run: {case_id or case_path}: {error}", file=sys.stderr)

    write_result(
        out,
        case_id=case_id,
        task_id=task_id,
        status="failed",
        output=None,
        error=error,
        capability_status=capability_status,
        issues=issues,
    )
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dataagent run",
        description="Run one normalized 09-benchmark case and write <out>/result.json.",
    )
    parser.add_argument("--case", required=True, help="normalized case JSON")
    parser.add_argument("--out", required=True, help="output directory for result.json")
    parser.add_argument("--config", help="adapter config JSON")
    args = parser.parse_args(argv)
    return run_case(args.case, args.out, args.config)


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI
    raise SystemExit(main())
