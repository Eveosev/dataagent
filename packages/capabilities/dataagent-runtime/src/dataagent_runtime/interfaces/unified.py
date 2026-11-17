"""Unified CLI kernel (12-unified-cli-research §5.3): argv in, summary out.

Shared by the three layer packages. This module owns the argv grammar
(``list``, ``run <op>`` with ``--input-file`` / ``--set`` / ``--set-json`` /
``--file`` / ``--ref`` / ``--proposal-file`` / ``--authorize`` /
``--detail``), the summary/output conventions (stdout ≤ 32 KiB, full result
under ``<data_root>/results/``), the exit-code contract (0/1/2/3) and the
model-visibility (egress) check on the way out. The layer provides hooks:
registry/invoke wiring, a runtime factory and — where the layer has file
inputs — a FileRef builder.

Identity (12 §5.4): the executing subject and purpose come from the host
first (``_meta`` when the entry point has it, then
``DATAAGENT_HOST_SUBJECT_REF`` / ``DATAAGENT_HOST_PURPOSE`` via the layer
runtime), then the local-owner fallback; call arguments can never set or
override them. A ``context`` key inside ``--input-file`` is a usage error,
not a context.

The legacy stdin mode (``python -m <pkg>.interfaces.cli <op>`` with a JSON
body on stdin) is retained unchanged for the existing black-box acceptance
flows; it is only taken when the operation name appears alone.
"""

from __future__ import annotations

import json
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from types import UnionType
from typing import Any, Callable, Union, get_args, get_origin

from pydantic import ValidationError

from dataagent_contracts.core import CapabilityStatus

# W0 seam spec §5: the content keys of an inference_request are the only
# model-visible content channel; structure keys are never stripped. The
# canonical tuple lives in ``dataagent_runtime.enforcement`` (the egress
# gate) and is re-exported here for the layer CLI kernels.
from dataagent_runtime.enforcement import EGRESS_CONTENT_KEYS  # noqa: F401
from dataagent_runtime.policy.context import (
    ContextResolutionError,
    ResolvedContext,
    resolve_context,
    with_authorization,
)

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2
EXIT_ENV = 3

SUMMARY_LIMIT = 32 * 1024

_FLAGS = (
    "--input-file",
    "--set",
    "--set-json",
    "--file",
    "--ref",
    "--proposal-file",
    "--authorize",
    "--detail",
)


class UsageError(Exception):
    """argv/schema error: exit 2 (12 §5.3)."""


@dataclass
class Parsed:
    input_file: str | None = None
    sets: list[tuple[str, str]] = field(default_factory=list)
    set_jsons: list[tuple[str, str]] = field(default_factory=list)
    file: str | None = None
    refs: list[tuple[str, str]] = field(default_factory=list)
    proposal_file: str | None = None
    authorize: bool = False
    detail: str = "summary"


@dataclass
class LayerHooks:
    layer: str  # "data" | "app" | "gov"
    list_operations: Callable[[], list[Any]]
    invoke: Callable[[str, dict[str, Any] | None, Any], Any]
    validate: Callable[[], None]
    runtime_factory: Callable[[], Any]
    # Layer-specific FileRef builder (data layer: real digest of the bytes).
    make_file_ref: Callable[[Any, str], dict[str, Any]] | None = None
    program: str = "dataagent"
    usage: str = ""


def _stderr(message: str) -> None:
    print(message, file=sys.stderr)


def _parse_pair(parsed: Parsed, token: str, value: str) -> None:
    """Store one ``<flag> <value>`` pair (validated per flag)."""

    if token == "--input-file":
        parsed.input_file = value
    elif token == "--set":
        name, sep, raw = value.partition("=")
        if not sep or not name:
            raise UsageError(f"--set expects k=v, got {value!r}")
        parsed.sets.append((name, raw))
    elif token == "--set-json":
        name, sep, raw = value.partition("=")
        if not sep or not name:
            raise UsageError(f"--set-json expects k=<json>, got {value!r}")
        parsed.set_jsons.append((name, raw))
    elif token == "--file":
        parsed.file = value
    elif token == "--ref":
        name, sep, handle = value.partition("=")
        if not sep or not name or "@" not in handle:
            raise UsageError(f"--ref expects <field>=<id@revision>, got {value!r}")
        parsed.refs.append((name, handle))
    elif token == "--proposal-file":
        parsed.proposal_file = value
    elif token == "--detail":
        if value not in {"summary", "full"}:
            raise UsageError("--detail expects summary or full")
        parsed.detail = value


def _parse_params(params: list[str]) -> Parsed:
    parsed = Parsed()
    index = 0
    while index < len(params):
        token = params[index]
        if token in {"-h", "--help"}:
            raise UsageError("--help belongs before the flag list; see `<op> --help`")
        if token not in _FLAGS:
            raise UsageError(f"unknown or misplaced argument: {token!r}")
        if token == "--authorize":
            parsed.authorize = True
            index += 1
            continue
        if index + 1 >= len(params):
            raise UsageError(f"{token} requires a value")
        _parse_pair(parsed, token, params[index + 1])
        index += 2
    if not (
        parsed.input_file
        or parsed.sets
        or parsed.set_jsons
        or parsed.file
        or parsed.refs
        or parsed.proposal_file
    ):
        raise UsageError(
            "no input given: use --input-file, --set/--set-json, --file, "
            "--ref or --proposal-file"
        )
    return parsed


_SCALAR_KINDS = frozenset({"string", "integer", "number", "boolean"})

# Keys that constrain the shape of a value. A property with none of them
# (pydantic's rendering of ``Any``, with or without ``title``/``default``)
# accepts any JSON, so a raw string is a valid ``--set`` value.
_STRUCTURAL_KEYS = (
    "$ref",
    "type",
    "enum",
    "anyOf",
    "allOf",
    "oneOf",
    "items",
    "prefixItems",
    "properties",
    "additionalProperties",
)


def _resolve_kind(prop: Any, defs: dict[str, Any], *, _depth: int = 0) -> str | None:
    """Scalar JSON type behind a property, following ``$ref``/``anyOf``.

    The inputSchema does not always spell a scalar as a literal ``type``:
    optional scalars arrive as ``anyOf`` unions with ``null``, string-form
    models (VersionedRef) and enums as ``$ref``, and unconstrained fields
    as ``{}`` (r4-review D10). Returns the scalar kind, or None when the
    field is not scalar-settable (arrays, objects, file/ref models).
    """

    if _depth > 8 or not isinstance(prop, dict):
        return None
    if "$ref" in prop:
        name = str(prop["$ref"]).rsplit("/", 1)[-1]
        return _resolve_kind(defs.get(name), defs, _depth=_depth + 1)
    kind = prop.get("type")
    if isinstance(kind, str) and kind in _SCALAR_KINDS:
        return kind
    if "enum" in prop:
        values = prop["enum"]
        if isinstance(values, list) and values and all(isinstance(v, str) for v in values):
            return "string"
        return None
    if "anyOf" in prop:
        kinds = {
            resolved
            for variant in prop["anyOf"]
            if (resolved := _resolve_kind(variant, defs, _depth=_depth + 1)) is not None
        }
        return kinds.pop() if len(kinds) == 1 else None
    if not any(key in prop for key in _STRUCTURAL_KEYS):
        # Unconstrained (``Any``): a raw string is a valid value.
        return "string"
    return None


def _coerce(
    name: str,
    raw: str,
    properties: dict[str, dict[str, Any]],
    defs: dict[str, Any],
) -> Any:
    """`--set` scalar conversion against the inputSchema (12 §5.3)."""

    prop = properties.get(name)
    if prop is None:
        raise UsageError(f"--set {name}: not a field of the input schema")
    kind = _resolve_kind(prop, defs)
    if kind == "integer":
        try:
            return int(raw)
        except ValueError as exc:
            raise UsageError(f"--set {name}={raw!r}: not an integer") from exc
    if kind == "number":
        try:
            return float(raw)
        except ValueError as exc:
            raise UsageError(f"--set {name}={raw!r}: not a number") from exc
    if kind == "boolean":
        if raw.lower() in {"true", "1", "yes"}:
            return True
        if raw.lower() in {"false", "0", "no"}:
            return False
        raise UsageError(f"--set {name}={raw!r}: not a boolean")
    if kind == "string":
        return raw
    raise UsageError(f"--set {name}: field is not a scalar; use --set-json {name}=<json>")


def _load_json_file(path: str, *, what: str) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UsageError(f"{what}: file not found: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise UsageError(f"{what}: cannot read {path}: {exc}") from exc


def _models_in(annotation: Any) -> list[type]:
    """BaseModel subclasses in an annotation (unwraps Optional/Union)."""

    from pydantic import BaseModel

    origin = get_origin(annotation)
    if origin is Union or origin is UnionType:
        models: list[type] = []
        for arg in get_args(annotation):
            models.extend(_models_in(arg))
        return models
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    return []


def _ref_fields(spec: Any) -> dict[str, type]:
    """Input fields typed as a model (TableRef, DocumentRef, VersionedRef...)."""

    fields = {}
    for name, field in getattr(spec.input_model, "model_fields", {}).items():
        models = _models_in(field.annotation)
        if models:
            fields[name] = models[0]
    return fields


def _file_field(spec: Any, raw: str, properties: dict[str, dict[str, Any]]) -> tuple[str, str]:
    """`--file [field=]path` → (field, path); one file input defaults."""

    name, sep, path = raw.partition("=")
    if sep and name in properties:
        return name, path
    if sep:
        raise UsageError(f"--file {raw!r}: {name!r} is not a field of the input schema")
    candidates = sorted(_ref_fields(spec))
    file_like = [c for c in candidates if "file" in c or "File" in c]
    if len(file_like) == 1:
        return file_like[0], raw
    if not file_like:
        raise UsageError("--file: this operation has no file input field")
    raise UsageError(
        f"--file: multiple file input fields ({', '.join(file_like)}); use --file <field>=<path>"
    )


def _proposal_field(spec: Any, properties: dict[str, dict[str, Any]]) -> str:
    if "proposal" in properties:
        return "proposal"
    name = _proposal_field_or_none(spec)
    if name is not None:
        return name
    raise UsageError("--proposal-file: this operation has no proposal input field")


def _resolve_handle(runtime: Any, handle: str, field_type: type | None = None) -> Any:
    """Resolve ``id@revision`` against previously written CLI results.

    Handles reference objects produced by earlier calls (tables, documents,
    rules — 12 §5.3); the full object is recovered from the result records
    under ``<data_root>/results/``, newest first. A handle names the versioned
    identity inside an object (a ``TableRef``'s asset, a plain
    ``VersionedRef``); when the target field declares a model type, the
    candidate chain (match, then its containers) is validated against it so
    the field receives the whole wrapper object, not the inner asset. A field
    whose model takes the string form (``VersionedRef``) can be filled from
    any handle, rich or plain: the handle string itself is the identity
    (r5-review D12).
    """

    results_dir = Path(runtime.data_root) / "results"
    if not results_dir.is_dir():
        raise UsageError(f"--ref: no result records under {results_dir}; handle {handle!r} unknown")
    for path in sorted(results_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        if path.name.endswith(".inference_request.json") or path.name.endswith(".input.json"):
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            # Never fatal (an unreadable record just cannot hold the
            # handle), but visible: a silently skipped record hides a
            # broken results directory.
            _stderr(f"--ref: skipping unreadable result record {path.name}: {exc}")
            continue
        chain = _find_chain(record.get("result", record), handle)
        if chain is not None:
            return _pick_chain_candidate(chain, field_type, handle)
    raise UsageError(f"--ref: handle {handle!r} not found in any result record")


def _validated_candidate(candidate: Any, field_type: type) -> Any:
    """The candidate validated against ``field_type``, or ``None``.

    Chain nodes that do not fit the declared field type are expected
    (the chain contains inner assets and their wrappers); validation is a
    filter, and the miss is returned, not raised. Works for the dict and
    the string form alike — ``VersionedRef`` validates from both.
    """

    try:
        field_type.model_validate(candidate)
    except ValidationError:
        return None
    return candidate


def _pick_chain_candidate(chain: list[Any], field_type: type | None, handle: str) -> Any:
    """The value a ``--ref`` field receives for ``handle``.

    Preference order when the field declares a model type (r5-review D12):

    1. the first chain object (match, then its containers) that validates —
       a ``TableRef`` field takes the whole wrapper object;
    2. the handle string itself — identity fields (``VersionedRef``) accept
       ``"<id>@<revision>"`` no matter how rich the stored object is;
    3. neither fits → usage error, never a silently incompatible value.
    """

    if field_type is not None:
        for candidate in chain:
            if not isinstance(candidate, dict):
                continue
            validated = _validated_candidate(candidate, field_type)
            if validated is not None:
                return validated
        validated = _validated_candidate(handle, field_type)
        if validated is not None:
            return validated
        raise UsageError(
            f"--ref: handle {handle!r} does not fit field type "
            f"{getattr(field_type, '__name__', field_type)!r}"
        )
    for candidate in chain:
        if isinstance(candidate, dict):
            return candidate
    raise UsageError("--ref: handle matched a non-object node")


def _find_chain(node: Any, handle: str) -> list[Any] | None:
    """``[matched node, parent, grandparent, ...]`` for the first match."""

    if isinstance(node, dict):
        ref_id, revision = node.get("id"), node.get("revision")
        if isinstance(ref_id, str) and isinstance(revision, str) and f"{ref_id}@{revision}" == handle:
            return [node]
        for value in node.values():
            chain = _find_chain(value, handle)
            if chain is not None:
                chain.append(node)
                return chain
    elif isinstance(node, list):
        for value in node:
            chain = _find_chain(value, handle)
            if chain is not None:
                chain.append(node)
                return chain
    return None


def _collect_handles(node: Any, out: list[str]) -> None:
    if isinstance(node, dict):
        ref_id, revision = node.get("id"), node.get("revision")
        if isinstance(ref_id, str) and isinstance(revision, str):
            out.append(f"{ref_id}@{revision}")
            return
        for value in node.values():
            _collect_handles(value, out)
    elif isinstance(node, list):
        for value in node:
            _collect_handles(value, out)


def _build_context(runtime: Any, parsed: Parsed) -> ResolvedContext:
    # R1: one resolver for every entry point. Subject/purpose come from the
    # host _meta (not available in argv) -> host configuration/environment
    # -> local-owner. The old argv-only context path is reached with
    # DATAAGENT_CONTEXT_RESOLVER=legacy.
    try:
        resolved = resolve_context(runtime=runtime)
    except ContextResolutionError as exc:
        raise _ContextError(str(exc)) from exc
    if parsed.authorize:
        decision = runtime.decisions.latest_allow(
            resolved.context.subject_ref, resolved.context.purpose
        )
        if decision is None:
            raise _AuthorizeError(
                "no allow AccessDecision for "
                f"subject={resolved.context.subject_ref!r} "
                f"purpose={resolved.context.purpose!r}; mint one first "
                "(dataagent gov run check_access_scope) or apply a policy"
            )
        resolved = with_authorization(resolved, decision.decision_id)
    return resolved


class _AuthorizeError(Exception):
    """`--authorize` found no usable decision: environment/policy missing (3)."""


class _ContextError(Exception):
    """The trusted context channels are malformed: environment error (3)."""


def _egress_scrub(summary: dict[str, Any], mode: str) -> dict[str, Any]:
    """Model-visibility check on the way out (12 §5.4, W0 seam spec §5).

    The layer operations already gate ``inference_request`` content; this is
    the CLI-side defence in depth for the same channel: under ``enforce``,
    an inference request that cites no ``egress_decision_ref`` never prints
    its content keys on stdout.
    """

    if mode != "enforce":
        return summary
    for issue in summary.get("issues") or []:
        request = issue.get("inference_request")
        if not isinstance(request, dict):
            continue
        if request.get("egress_decision_ref"):
            continue
        issue["inference_request"] = {
            key: value for key, value in request.items() if key not in EGRESS_CONTENT_KEYS
        }
    return summary


def _op_help(spec: Any, hooks: LayerHooks) -> str:
    """Flat parameter table from the inputSchema — never ``$defs``."""

    schema = spec.input_model.model_json_schema()
    lines = [
        f"usage: dataagent {hooks.layer} run {spec.operation} [flags]",
        "",
        f"{spec.capability_id} {spec.operation}",
        spec.description or "",
        "",
        "input fields:",
    ]
    for name, prop in schema.get("properties", {}).items():
        kind = _resolve_kind(prop, schema.get("$defs", {}))
        if kind is None:
            kind = prop.get("$ref", "object").rsplit("/", 1)[-1]
        required = "required" if name in schema.get("required", []) else "optional"
        description = (prop.get("description") or "").splitlines()
        first = description[0] if description else ""
        lines.append(f"  --set {name}=<{kind}>  [{required}]  {first}")
    lines += [
        "",
        "flags:",
        "  --input-file <path>        full input object (JSON)",
        "  --set k=v                  single scalar field, typed by the schema",
        "  --set-json k=<json>        single field as JSON (objects, arrays, refs)",
        "  --file [field=]<path>      build a FileRef from the file's bytes",
        "  --ref <field>=<id@rev>     fill a reference field from an earlier result",
        "  --proposal-file <path>     two-phase second-stage proposal (JSON)",
        "  --authorize                fill authorization_ref from the latest allow decision",
        "  --detail summary|full      print the full result instead of the summary",
        "",
        "context comes from the host environment (DATAAGENT_HOST_SUBJECT_REF,",
        "DATAAGENT_HOST_PURPOSE), then the local-owner fallback; it cannot be",
        "passed as an argument. DATAAGENT_CONTEXT_RESOLVER=legacy restores the",
        "old precedence for one release.",
    ]
    return "\n".join(lines)


def _list_lines(hooks: LayerHooks) -> int:
    for spec in hooks.list_operations():
        recheck = "yes" if spec.resource_fields else "no"
        two_phase = "yes" if _is_two_phase(spec) else "no"
        print(f"{spec.operation}\t{spec.capability_id}\trecheck={recheck}\ttwo_phase={two_phase}")
    return EXIT_OK


def _is_two_phase(spec: Any) -> bool:
    properties = spec.input_model.model_json_schema().get("properties", {})
    if "proposal" in properties:
        return True
    return bool(_proposal_field_or_none(spec))


def _proposal_field_or_none(spec: Any) -> str | None:
    for name, field in getattr(spec.input_model, "model_fields", {}).items():
        for model in _models_in(field.annotation):
            if getattr(model, "__name__", "").endswith("Proposal"):
                return name
    return None


def _legacy_list_json(hooks: LayerHooks) -> int:
    from dataagent_runtime.interfaces.cli import operations_json

    print(operations_json(hooks.list_operations))
    return EXIT_OK


def _build_payload(
    spec: Any,
    parsed: Parsed,
    hooks: LayerHooks,
    runtime: Any,
    schema: dict[str, Any],
) -> dict[str, Any]:
    """The operation input assembled from the parsed flags (12 §5.3)."""

    properties = schema.get("properties", {})
    defs = schema.get("$defs", {})
    payload: dict[str, Any] = {}
    if parsed.input_file is not None:
        body = _load_json_file(parsed.input_file, what="--input-file")
        if not isinstance(body, dict):
            raise UsageError("--input-file: JSON must be an object")
        if "context" in body:
            raise UsageError("--input-file: 'context' cannot be supplied by arguments (12 §5.4)")
        payload.update(body)
    for name, raw in parsed.sets:
        payload[name] = _coerce(name, raw, properties, defs)
    for name, raw in parsed.set_jsons:
        if name not in properties:
            raise UsageError(f"--set-json {name}: not a field of the input schema")
        payload[name] = json.loads(raw)
    if parsed.file is not None:
        if hooks.make_file_ref is None:
            raise UsageError("--file: this layer has no file inputs")
        name, path = _file_field(spec, parsed.file, properties)
        try:
            payload[name] = hooks.make_file_ref(runtime, path)
        except OSError as exc:
            raise UsageError(f"--file: cannot read {path}: {exc}") from exc
    for name, handle in parsed.refs:
        if name not in properties:
            raise UsageError(f"--ref {name}: not a field of the input schema")
        payload[name] = _resolve_handle(runtime, handle, _ref_fields(spec).get(name))
    if parsed.proposal_file is not None:
        name = _proposal_field(spec, properties)
        proposal = _load_json_file(parsed.proposal_file, what="--proposal-file")
        if not isinstance(proposal, dict):
            raise UsageError("--proposal-file: JSON must be an object")
        payload[name] = proposal
    return payload


def _run(op: str, params: list[str], hooks: LayerHooks) -> int:
    specs = {spec.operation: spec for spec in hooks.list_operations()}
    if "-h" in params or "--help" in params:
        spec = specs.get(op)
        if spec is None:
            _stderr(f"unknown operation: {op}")
            return EXIT_USAGE
        print(_op_help(spec, hooks))
        return EXIT_OK
    spec = specs.get(op)
    if spec is None:
        _stderr(f"unknown operation: {op}")
        return EXIT_USAGE
    try:
        parsed = _parse_params(params)
    except UsageError as exc:
        _stderr(f"usage error: {exc}")
        return EXIT_USAGE

    runtime = hooks.runtime_factory()
    try:
        payload = _build_payload(spec, parsed, hooks, runtime, spec.input_model.model_json_schema())
    except UsageError as exc:
        _stderr(f"usage error: {exc}")
        return EXIT_USAGE
    except json.JSONDecodeError as exc:
        _stderr(f"usage error: invalid JSON: {exc}")
        return EXIT_USAGE

    # Schema errors are usage errors (exit 2, 12 §5.3), not capability failures.
    try:
        spec.input_model.model_validate(payload)
    except ValidationError as exc:
        _stderr(f"schema error: {exc}")
        return EXIT_USAGE

    try:
        context = _build_context(runtime, parsed)
    except _AuthorizeError as exc:
        _stderr(str(exc))
        return EXIT_ENV
    except _ContextError as exc:
        _stderr(f"context error: {exc}")
        return EXIT_ENV

    result = hooks.invoke(op, payload, context)
    return _emit(result, parsed, hooks, op, runtime, payload)


def _clip_value(value: Any) -> Any:
    """Recursively clip an oversized value (long strings, long lists)."""

    if isinstance(value, str) and len(value) > 200:
        return f"{value[:200]}…[clipped {len(value) - 200} chars; see result_path]"
    if isinstance(value, list) and len(value) > 3:
        head = [_clip_value(item) for item in value[:3]]
        return head + [{"clipped": f"+{len(value) - 3} entries; see result_path"}]
    if isinstance(value, dict):
        return {key: _clip_value(item) for key, item in value.items()}
    return value


def _clip_issue(issue: Any) -> Any:
    """Clip one issue's ``inference_request`` content down to summary size."""

    if isinstance(issue, dict) and isinstance(issue.get("inference_request"), dict):
        return {**issue, "inference_request": _clip_value(issue["inference_request"])}
    return issue


def _fit_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """A summary that fits ``SUMMARY_LIMIT`` (12 §5.3, r1-review D5).

    Steps, taken only while the encoded summary is still oversized: drop
    the ``data`` payload, cap the issue list, clip each remaining issue's
    ``inference_request`` content, clip oversized handles and finally shed
    them. Nothing durable is lost — the untouched record stays in
    ``result_path`` (and, for ``needs_input``, in the
    ``.inference_request.json`` file). The returned summary always fits:
    a single handle can alone exceed the limit (r5-review D5), so the
    encoded size is re-checked after every step, down to a minimal
    record identity. The cap is on the whole stdout line, so the trailing
    newline ``print`` appends counts against the budget (r6-review D5:
    an exactly 32,768-byte JSON used to print as 32,769 bytes of stdout).
    """

    def fits(candidate: dict[str, Any]) -> bool:
        # +1 for the "\n" print() writes after the JSON (stdout cap).
        encoded = len(json.dumps(candidate, ensure_ascii=False).encode("utf-8"))
        return encoded + 1 <= SUMMARY_LIMIT

    if fits(summary):
        return summary
    encoded = json.dumps(summary, ensure_ascii=False)
    shrunk = {
        **summary,
        "data": {
            "truncated": True,
            "reason": "summary exceeds 32 KiB",
            "bytes": len(encoded.encode("utf-8")),
        },
    }
    if fits(shrunk):
        return shrunk
    shrunk["issues"] = [_clip_issue(issue) for issue in (summary.get("issues") or [])[:20]]
    if fits(shrunk):
        return shrunk
    shrunk["issues"] = [
        {
            "code": "summary_clipped",
            "severity": "warning",
            "message": "summary clipped to 32 KiB; the full record is in result_path",
            "retryable": False,
        }
    ]
    handles = [
        handle if len(handle) <= 200 else _clip_value(handle) for handle in shrunk.get("handles") or []
    ]
    while handles and not fits({**shrunk, "handles": handles}):
        handles = handles[:-1]
    shrunk["handles"] = handles
    if fits(shrunk):
        return shrunk
    # Pathological residue (e.g. a runaway result_path): the identity of the
    # record still fits — everything else is in result_path.
    return {
        "status": shrunk.get("status"),
        "invocation_id": shrunk.get("invocation_id"),
        "issues": shrunk["issues"],
        "result_path": str(shrunk.get("result_path"))[:1024],
    }


def _emit(
    result: Any,
    parsed: Parsed,
    hooks: LayerHooks,
    op: str,
    runtime: Any,
    payload: dict[str, Any],
) -> int:
    data = result.model_dump(mode="json")
    execution = data.get("execution_ref") or {}
    invocation_id = execution.get("invocation_id") or f"inv:{uuid.uuid4().hex[:12]}"
    results_dir = Path(runtime.data_root) / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    result_path = results_dir / f"{invocation_id}.json"
    input_path = results_dir / f"{invocation_id}.input.json"
    result_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    input_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    mode = getattr(getattr(runtime, "enforcement", None), "mode", "warn")
    if parsed.detail == "full":
        # r1-review D7: ``--detail full`` is a stdout channel like the
        # summary — the model-visibility check strips inference_request
        # content keys on every stdout path, not only the summary.
        print(json.dumps(_egress_scrub(data, mode), ensure_ascii=False))
        return EXIT_FAILED if result.status is CapabilityStatus.failed else EXIT_OK

    handles: list[str] = []
    _collect_handles(data.get("data"), handles)
    _collect_handles(data.get("provenance"), handles)
    summary: dict[str, Any] = {
        "status": data.get("status"),
        "invocation_id": invocation_id,
        "issues": data.get("issues") or [],
        "handles": sorted(set(handles)),
        "result_path": str(result_path),
    }
    if data.get("data") is not None:
        summary["data"] = data["data"]

    summary = _egress_scrub(summary, mode)

    if result.status is CapabilityStatus.needs_input:
        requests = [
            issue.get("inference_request")
            for issue in data.get("issues") or []
            if isinstance(issue.get("inference_request"), dict)
        ]
        if requests:
            request_path = results_dir / f"{invocation_id}.inference_request.json"
            request_path.write_text(
                json.dumps(requests[0], ensure_ascii=False, indent=2), encoding="utf-8"
            )
        summary["next_command"] = (
            f"dataagent {hooks.layer} run {op} "
            f"--input-file {input_path} --proposal-file <proposal.json>"
        )

    print(json.dumps(_fit_summary(summary), ensure_ascii=False))
    return EXIT_FAILED if result.status is CapabilityStatus.failed else EXIT_OK


def _legacy(hooks: LayerHooks, argv: list[str]) -> int:
    from dataagent_runtime.interfaces.cli import USAGE, main as legacy_main

    return legacy_main(
        argv,
        list_operations=hooks.list_operations,
        invoke=hooks.invoke,
        usage=hooks.usage or USAGE,
        program=hooks.program,
    )


def main(argv: list[str] | None = None, *, hooks: LayerHooks) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        hooks.validate()
    except Exception as exc:  # noqa: BLE001 - environment missing (12 §5.3: exit 3)
        _stderr(f"{hooks.program}: environment check failed: {exc}")
        return EXIT_ENV
    if not argv or argv[0] in {"-h", "--help"}:
        _stderr(
            f"usage: dataagent {hooks.layer} list\n"
            f"       dataagent {hooks.layer} run <op> [flags]\n"
            f"       dataagent {hooks.layer} <op> --help\n"
            f"       dataagent {hooks.layer} <op>            (legacy: JSON on stdin)"
        )
        return EXIT_USAGE
    head = argv[0]
    if head == "--list":
        return _legacy_list_json(hooks)
    if head == "list":
        return _list_lines(hooks)
    if head == "run":
        if len(argv) < 2:
            _stderr("usage error: run requires an operation name")
            return EXIT_USAGE
        return _run(argv[1], argv[2:], hooks)
    known = {spec.operation for spec in hooks.list_operations()}
    if head in known:
        if len(argv) == 1:
            return _legacy(hooks, argv)
        return _run(head, argv[1:], hooks)
    _stderr(f"unknown command or operation: {head}")
    return EXIT_USAGE
