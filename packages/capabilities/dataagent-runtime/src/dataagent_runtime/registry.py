"""Operation registry and Catalog consistency gate (06 §4.1, shared).

Each layer package registers its own operations with the ``operation``
decorator and validates them against its catalog snapshot at startup. The
runtime itself ships zero operations.
"""

from __future__ import annotations

import json
import os
import types as _pytypes
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Callable, Type, Union, get_args, get_origin

from pydantic import BaseModel

from dataagent_contracts.core import VersionedRef

from dataagent_runtime.policy.context import is_legacy_context

IMPLEMENTATION_REF = "dataagent-runtime/0.1.0"

DEFAULT_CATALOG_ENV = "DATAAGENT_CATALOG_SNAPSHOT"

# r41 X2: an undeclared or wrongly declared resource field silently disabled
# the access recheck (typo -> attribute missing; ``str``/``dict`` -> no
# VersionedRef produced). These are the only annotation shapes the recheck
# can turn into resource refs, so they are the only shapes a declaration may
# use. ``str``, ``dict``, ``Any`` and opaque models are rejected at
# registration time, never at call time.
# The recheck iterates only list/tuple values; accepting any other sequence
# annotation here would re-open the silent-skip hole this validation closes.
_SEQUENCE_ORIGINS = {list, tuple}


@dataclass(frozen=True)
class OperationSpec:
    operation: str
    capability_id: str
    source_file: str
    input_model: Type[BaseModel]
    output_model: Type[BaseModel]
    handler: Callable[..., Any]
    writes: bool = False
    description: str = ""
    idempotent: bool | None = None
    destructive: bool = False
    # Names of input-model fields that hold resource references read by this
    # operation. The access recheck (08 §4.3) resolves them against the
    # AccessDecision before the handler runs.
    resource_fields: tuple[str, ...] = ()


def _unwrap_annotation(annotation: Any) -> Any:
    """Strip ``Annotated`` wrappers (pydantic keeps the inner type)."""

    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    return annotation


def _is_resource_annotation(annotation: Any) -> bool:
    """Can the recheck turn a value of this annotation into a resource ref?

    Accepted shapes mirror ``invoke._to_versioned_ref``: a ``VersionedRef``,
    an ``AssetRef``/``FileRef``-shaped model (``id`` + ``revision``), a
    wrapper model carrying ``asset`` (``TableRef``, ``DocumentRef``,
    ``ProfileRef`` ...), or a sequence/optional of those. Everything the
    old recheck silently skipped — plain ``str``, ``dict`` containers,
    ``Any``, opaque models — is rejected.
    """

    annotation = _unwrap_annotation(annotation)
    if annotation is VersionedRef:
        return True
    origin = get_origin(annotation)
    if origin in _SEQUENCE_ORIGINS:
        args = [arg for arg in get_args(annotation) if arg is not Ellipsis]
        return bool(args) and all(_is_resource_annotation(arg) for arg in args)
    if origin in (Union, _pytypes.UnionType):
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        return bool(args) and all(_is_resource_annotation(arg) for arg in args)
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        fields = annotation.model_fields
        if "asset" in fields:
            # A wrapper names the asset it reads (TableRef/DocumentRef/...).
            asset_field = fields["asset"]
            if not asset_field.is_required():
                return False
            asset = _unwrap_annotation(asset_field.annotation)
            return _is_asset_ref_annotation(asset)
        # A flat asset carries the identity itself (AssetRef/FileRef); the
        # recheck's ``_to_versioned_ref`` needs all three of id/kind/revision
        # *at call time*, so optional/None-typed identity fields are rejected
        # here rather than silently producing no refs (r41 X2 follow-up).
        id_field = fields.get("id")
        kind_field = fields.get("kind")
        revision_field = fields.get("revision")
        return bool(
            id_field is not None
            and revision_field is not None
            and kind_field is not None
            and _is_required_text_field(id_field)
            and _is_required_text_field(revision_field)
            and _is_text_field(kind_field)
        )
    return False


def _is_text_field(field: Any) -> bool:
    return _unwrap_annotation(field.annotation) is str


def _is_required_text_field(field: Any) -> bool:
    return field.is_required() and _is_text_field(field)


def _is_asset_ref_annotation(annotation: Any) -> bool:
    if annotation is VersionedRef:
        return True
    if not (isinstance(annotation, type) and issubclass(annotation, BaseModel)):
        return False
    fields = annotation.model_fields
    id_field = fields.get("id")
    revision_field = fields.get("revision")
    return bool(
        id_field is not None
        and revision_field is not None
        and _is_required_text_field(id_field)
        and _is_required_text_field(revision_field)
    )


def _resource_annotation_hint(annotation: Any) -> str:
    annotation = _unwrap_annotation(annotation)
    origin = get_origin(annotation)
    if origin is dict:
        return "a dict container is not a resource reference"
    if annotation is str:
        return "a plain str is not a resource reference"
    if annotation is Any:
        return "Any cannot be verified as a resource reference"
    text = getattr(annotation, "__name__", None) or str(annotation)
    return f"{text} does not carry an asset or an id/revision identity"


def validate_resource_fields(
    operation_name: str,
    input_model: Type[BaseModel],
    resource_fields: tuple[str, ...],
    *,
    legacy: bool | None = None,
) -> None:
    """Reject resource-field declarations the access recheck cannot verify.

    Runs at registration (``operation`` / ``register``), so a typo or an
    unusable field type fails the process at startup instead of silently
    skipping the DA12.1 recheck on every call (S0 review X2). Under the
    one-release ``legacy`` switch the old permissive registration is kept,
    so existing packages can roll back without changing their declarations.
    """

    if legacy is None:
        legacy = is_legacy_context()
    if legacy:
        return
    seen: set[str] = set()
    for name in resource_fields:
        if not isinstance(name, str) or not name:
            raise RuntimeError(
                f"{operation_name}: resource_fields must contain non-empty field names"
            )
        if name in seen:
            raise RuntimeError(
                f"{operation_name}: duplicate resource field {name!r} in resource_fields"
            )
        seen.add(name)
        field = input_model.model_fields.get(name)
        if field is None:
            raise RuntimeError(
                f"{operation_name}: resource field {name!r} is not an input field of "
                f"{input_model.__name__}; a misspelled declaration would skip the "
                "access recheck (X2)"
            )
        if not _is_resource_annotation(field.annotation):
            raise RuntimeError(
                f"{operation_name}: resource field {name!r} has type "
                f"{field.annotation!r}; {_resource_annotation_hint(field.annotation)}. "
                "Declare a VersionedRef or an AssetRef/TableRef-shaped model (X2)"
            )


_SPECS: dict[str, OperationSpec] = {}
_LOADED = False


def operation(
    capability_id: str,
    *,
    input_model: Type[BaseModel],
    output_model: Type[BaseModel],
    writes: bool = False,
    description: str = "",
    idempotent: bool | None = None,
    destructive: bool = False,
    resource_fields: tuple[str, ...] = (),
):
    resource_fields = tuple(resource_fields)

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        validate_resource_fields(fn.__name__, input_model, resource_fields)
        module = fn.__module__
        source_file = "src/" + module.replace(".", "/") + ".py"
        spec = OperationSpec(
            operation=fn.__name__,
            capability_id=capability_id,
            source_file=source_file,
            input_model=input_model,
            output_model=output_model,
            handler=fn,
            writes=writes,
            description=description,
            idempotent=idempotent,
            destructive=destructive,
            resource_fields=resource_fields,
        )
        existing = _SPECS.get(spec.operation)
        if existing is not None and existing != spec:
            raise RuntimeError(f"duplicate operation registration: {spec.operation}")
        _SPECS[spec.operation] = spec
        return fn

    return decorator


def register(spec: OperationSpec) -> None:
    validate_resource_fields(spec.operation, spec.input_model, spec.resource_fields)
    existing = _SPECS.get(spec.operation)
    if existing is not None and existing != spec:
        raise RuntimeError(f"duplicate operation registration: {spec.operation}")
    _SPECS[spec.operation] = spec


def load_operations() -> None:
    """No built-ins: each layer package imports its operation modules."""

    global _LOADED
    _LOADED = True


def list_operations() -> list[OperationSpec]:
    load_operations()
    return sorted(_SPECS.values(), key=lambda spec: (spec.capability_id, spec.operation))


def get_spec(name: str) -> OperationSpec | None:
    load_operations()
    return _SPECS.get(name)


def reset_registry() -> None:
    """Test helper: clear registrations before re-importing modules."""

    global _LOADED
    _SPECS.clear()
    _LOADED = False


def load_catalog(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    catalog_path = Path(path or os.environ.get(DEFAULT_CATALOG_ENV))
    return json.loads(catalog_path.read_text(encoding="utf-8"))


def registry_errors(
    catalog: dict[str, Any] | None = None,
    *,
    expected_atoms: int | None = None,
) -> list[str]:
    """Consistency between registered operations and a catalog snapshot.

    ``expected_atoms`` pins the snapshot size (each layer knows its S0 count).
    """

    load_operations()
    if catalog is None:
        catalog = load_catalog()
    errors: list[str] = []
    atoms = catalog.get("atoms", [])
    if expected_atoms is not None and len(atoms) != expected_atoms:
        errors.append(f"catalog snapshot must contain {expected_atoms} atoms, got {len(atoms)}")
    catalog_ops = {a["operation"]: a for a in atoms}
    missing = sorted(set(catalog_ops) - set(_SPECS))
    extra = sorted(set(_SPECS) - set(catalog_ops))
    for name in missing:
        errors.append(f"catalog operation not registered: {name} ({catalog_ops[name]['id']})")
    for name in extra:
        errors.append(f"registered operation not in catalog: {name}")
    for name in sorted(set(catalog_ops) & set(_SPECS)):
        spec = _SPECS[name]
        atom = catalog_ops[name]
        if spec.capability_id != atom["id"]:
            errors.append(f"{name}: capability_id {spec.capability_id} != catalog {atom['id']}")
        if spec.source_file != atom["source_file"]:
            errors.append(f"{name}: source_file {spec.source_file} != catalog {atom['source_file']}")
    return errors


def validate_registry(
    catalog: dict[str, Any] | None = None,
    *,
    expected_atoms: int | None = None,
) -> None:
    errors = registry_errors(catalog, expected_atoms=expected_atoms)
    if errors:
        raise RuntimeError("registry/catalog consistency failed:\n" + "\n".join(errors))
