"""Closed expression AST: validation and three-valued interpreter (07 §5.1).

DA07.5.1 (scalar, over one ``ExtractedRecordRef``) and DA07.5.2 (table, over
one stored ``TableRef``, row by row). The interpreter never calls ``eval``.

Three-valued logic: ``True / False / UNKNOWN``. A missing or conflicting
``FieldValue`` (or a null cell) makes the whole subtree ``UNKNOWN`` — never
``False``. Type mismatches are reported as issues (scalar: failure; table:
that row's verdict becomes ``unknown`` plus a warning issue).

Verdict mapping: exceptions first, then the main expression —
``true → pass``, ``false → fail``, ``UNKNOWN → unknown``; an
applicable exception or unmet precondition yields ``not_applicable``.
The verdict vocabulary is the core contracts ``Verdict`` (05 §3.3:
``pass/fail/unknown/not_applicable``) so an ``Assessment`` is directly
consumable as a governance acceptance delivery (08 §5.3); business aliases
(``satisfied``/``violated``) are mapped by the consumer for older
producers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from fnmatch import fnmatchcase
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field as PydanticField

from dataagent_contracts.core import (
    Assessment,
    CallContext,
    CapabilityResult,
    CapabilityStatus,
    Completeness,
    EvidenceRef,
    ExecutableSpec,
    FieldValue,
    FieldValueStatus,
    Issue,
    Severity,
    VersionedRef,
)

from dataagent_application import helpers
from dataagent_application.execution import engines
from dataagent_runtime.errors import invalid_input
from dataagent_runtime.registry import operation

INTERPRETER_VERSION = "0.1.0"
ENGINE_ID = "dataagent-expression"

LOGIC_OPS = frozenset({"and", "or", "not"})
COMPARISON_OPS = frozenset({"eq", "ne", "lt", "le", "gt", "ge"})
ARITHMETIC_OPS = frozenset({"add", "sub", "mul", "div"})
SPECIAL_OPS = frozenset({"in", "between", "is_missing", "date_diff", "string_match"})
CLOSED_OPS = LOGIC_OPS | COMPARISON_OPS | ARITHMETIC_OPS | SPECIAL_OPS | {"field", "literal"}

MAX_NODES = 2000
MAX_DEPTH = 64


class _Unknown:
    """Sentinel for the third truth value (never a Python None value)."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "UNKNOWN"


UNKNOWN = _Unknown()

_MISSING_STATUSES = frozenset({FieldValueStatus.missing, FieldValueStatus.conflict})


class ExpressionTypeError(Exception):
    """A type mismatch the caller must surface as an issue (07 §5.1)."""


@dataclass
class FieldAccess:
    """One participating field value, kept for ``Assessment.evidence``."""

    field_id: str
    value: Any
    anchors: list[Any] = field(default_factory=list)
    unknown: bool = False
    low_confidence: bool = False


def _walk_op(node: Any, path: str = "$") -> None:
    """Structural validation: closed operator set, arity, depth, node budget."""

    def visit(node: Any, depth: int, path: str, counter: list[int]) -> None:
        counter[0] += 1
        if counter[0] > MAX_NODES:
            raise invalid_input(f"expression AST exceeds {MAX_NODES} nodes", target=path)
        if not isinstance(node, dict):
            raise invalid_input(
                f"AST node must be an object, got {type(node).__name__} at {path}",
                target=path,
            )
        op = node.get("op")
        if op not in CLOSED_OPS:
            raise invalid_input(
                f"non-closed operator rejected: {op!r} at {path} "
                f"(closed set: {sorted(CLOSED_OPS - {'field', 'literal'})})",
                target=path,
            )
        if depth > MAX_DEPTH:
            raise invalid_input(f"expression AST deeper than {MAX_DEPTH} at {path}", target=path)
        if op == "field":
            if not isinstance(node.get("field_id"), str) or not node["field_id"]:
                raise invalid_input(f"field node requires field_id at {path}", target=path)
            return
        if op == "literal":
            if "value" not in node:
                raise invalid_input(f"literal node requires value at {path}", target=path)
            return
        args = node.get("args")
        if not isinstance(args, list) or not args:
            raise invalid_input(f"operator {op!r} requires a non-empty args list at {path}")
        # and/or are n-ary; every other operator has a fixed arity.
        arity: int | None = {"not": 1, "is_missing": 1}.get(op)
        if op in COMPARISON_OPS or op in ARITHMETIC_OPS or op in {"date_diff", "string_match"}:
            arity = 2
        elif op == "between":
            arity = 3
        if arity is not None and len(args) != arity:
            raise invalid_input(
                f"operator {op!r} requires {arity} args, got {len(args)} at {path}", target=path
            )
        if op == "date_diff":
            if node.get("unit") != "day":
                raise invalid_input(
                    f"date_diff unit must be 'day' in S0, got {node.get('unit')!r}", target=path
                )
        if op == "is_missing":
            target = args[0]
            if not (isinstance(target, dict) and target.get("op") == "field"):
                raise invalid_input(
                    "is_missing requires a field operand at " + path, target=path
                )
        if op in {"in", "between", "string_match"}:
            for index in range(1, len(args)):
                operand = args[index]
                if not (isinstance(operand, dict) and operand.get("op") == "literal"):
                    raise invalid_input(
                        f"{op} requires literal operands from position 1 at {path}", target=path
                    )
        for index, child in enumerate(args):
            visit(child, depth + 1, f"{path}.args[{index}]", counter)

    visit(node, 0, path, [0])


def referenced_fields(node: Any) -> set[str]:
    """Field ids referenced by the AST (leaves)."""

    fields: set[str] = set()
    if isinstance(node, dict):
        if node.get("op") == "field":
            fields.add(node["field_id"])
        for child in node.get("args") or []:
            fields |= referenced_fields(child)
    return fields


def referenced_condition_ids(node: Any) -> set[str]:
    """Condition provenance ids carried by the AST leaves (07 §5.1)."""

    ids: set[str] = set()
    if isinstance(node, dict):
        if node.get("op") == "field" and isinstance(node.get("condition_id"), str):
            ids.add(node["condition_id"])
        for child in node.get("args") or []:
            ids |= referenced_condition_ids(child)
    return ids


def type_check(node: Any, field_types: dict[str, str]) -> list[str]:
    """Generation-time type check against the record schema (07 §5.1).

    ``field_types`` maps field_id → value_type. Returns the list of type
    problems found (empty when the expression is well typed).
    """

    problems: list[str] = []
    numeric = {"number", "integer", "decimal", "float", "int"}
    py_numeric = (int, float)

    def visit(node: Any, path: str) -> str | None:
        """Return 'number' | 'string' | 'boolean' | 'date' | None (unknown)."""

        if not isinstance(node, dict):
            return None
        op = node.get("op")
        if op == "field":
            declared = field_types.get(node["field_id"])
            if declared is None:
                problems.append(f"{path}: unknown field {node['field_id']!r}")
                return None
            declared = declared.lower()
            if declared in numeric:
                return "number"
            if "date" in declared or "time" in declared:
                return "date"
            if declared in {"boolean", "bool"}:
                return "boolean"
            return "string"
        if op == "literal":
            value = node.get("value")
            if isinstance(value, bool):
                return "boolean"
            if isinstance(value, py_numeric):
                return "number"
            if isinstance(value, str):
                return "string"
            if isinstance(value, list):
                return "list"
            return None
        args = node.get("args") or []
        types = [visit(child, f"{path}.args[{i}]") for i, child in enumerate(args)]
        if op in COMPARISON_OPS:
            if op in {"lt", "le", "gt", "ge"}:
                left, right = types[0], types[1]
                if left == "string" and right == "number" or left == "number" and right == "string":
                    problems.append(
                        f"{path}: ordered comparison {op!r} between {left} and {right}"
                    )
            return "boolean"
        if op in ARITHMETIC_OPS:
            for index, kind in enumerate(types):
                if kind not in (None, "number"):
                    problems.append(
                        f"{path}.args[{index}]: arithmetic operand is {kind}, expected number"
                    )
            return "number"
        if op == "date_diff":
            for index, kind in enumerate(types):
                if kind not in (None, "date", "string"):
                    problems.append(f"{path}.args[{index}]: date_diff operand is {kind}")
            return "number"
        if op in {"and", "or", "not"}:
            for index, kind in enumerate(types):
                if kind not in (None, "boolean"):
                    problems.append(
                        f"{path}.args[{index}]: logical operand is {kind}, expected boolean"
                    )
            return "boolean"
        if op == "string_match":
            if types[1] not in (None, "string"):
                problems.append(f"{path}: string_match pattern must be a string literal")
            return "boolean"
        if op in {"in", "between"}:
            if types[0] == "number" and types[1] == "string":
                problems.append(f"{path}: {op} mixes number field with string literals")
            if types[0] == "string" and types[1] == "number":
                problems.append(f"{path}: {op} mixes string field with number literals")
            return "boolean"
        if op == "is_missing":
            return "boolean"
        return None

    visit(node, "$")
    return problems


def _literal_ok(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        raise ExpressionTypeError(f"literal must be scalar, got {type(value).__name__}")
    return value


class _Interpreter:
    def __init__(self, getter, accesses: list[FieldAccess]):
        self._getter = getter
        self._accesses = accesses

    def _value_of(self, node: dict[str, Any]) -> Any:
        op = node["op"]
        if op == "field":
            field_id = node["field_id"]
            value, usable, anchors, low_confidence = self._getter(field_id)
            self._accesses.append(
                FieldAccess(
                    field_id=field_id, value=value, anchors=anchors or [],
                    unknown=not usable, low_confidence=low_confidence,
                )
            )
            return value if usable else UNKNOWN
        if op == "literal":
            return node["value"]
        if op == "is_missing":
            # Decided at the leaf — anywhere in the tree, not only at the
            # root: a missing/conflict/null field makes ``is_missing`` *True*.
            leaf = node["args"][0]
            field_id = leaf["field_id"]
            value, usable, anchors, low_confidence = self._getter(field_id)
            self._accesses.append(
                FieldAccess(
                    field_id=field_id,
                    value=value,
                    anchors=anchors or [],
                    unknown=not usable,
                    low_confidence=low_confidence,
                )
            )
            return not usable
        args = [self._value_of(child) for child in node["args"]]
        if op in ("and", "or", "not"):
            return self._logic(op, args)
        if UNKNOWN in args:
            return UNKNOWN
        if op in COMPARISON_OPS:
            return self._compare(op, args[0], args[1])
        if op in ARITHMETIC_OPS:
            return self._arith(op, args[0], args[1])
        if op == "in":
            return self._in(args[0], node["args"][1]["value"])
        if op == "between":
            return self._between(args[0], args[1], args[2])
        if op == "date_diff":
            return self._date_diff(args[0], args[1])
        if op == "string_match":
            return self._string_match(args[0], args[1])
        raise ExpressionTypeError(f"unhandled operator {op!r}")

    @staticmethod
    def _logic(op: str, args: list[Any]) -> Any:
        # Kleene three-valued logic; UNKNOWN never collapses to False.
        if op == "and":
            if any(arg is False for arg in args):
                return False
            if any(arg is UNKNOWN for arg in args):
                return UNKNOWN
            return True
        if op == "or":
            if any(arg is True for arg in args):
                return True
            if any(arg is UNKNOWN for arg in args):
                return UNKNOWN
            return False
        # not
        arg = args[0]
        return UNKNOWN if arg is UNKNOWN else (not arg)

    @staticmethod
    def _compare(op: str, left: Any, right: Any) -> Any:
        if isinstance(left, bool) or isinstance(right, bool):
            if not (isinstance(left, bool) and isinstance(right, bool)):
                raise ExpressionTypeError(
                    f"cannot compare boolean with {type(left if not isinstance(left, bool) else right).__name__}"
                )
        elif isinstance(left, str) != isinstance(right, str):
            raise ExpressionTypeError(
                f"cannot compare {type(left).__name__} with {type(right).__name__}"
            )
        if isinstance(left, datetime) != isinstance(right, datetime):
            raise ExpressionTypeError("cannot compare datetime with non-datetime")
        try:
            if op == "eq":
                return left == right
            if op == "ne":
                return left != right
            if op == "lt":
                return left < right
            if op == "le":
                return left <= right
            if op == "gt":
                return left > right
            return left >= right
        except TypeError as exc:
            raise ExpressionTypeError(str(exc)) from exc

    @staticmethod
    def _arith(op: str, left: Any, right: Any) -> Any:
        if isinstance(left, bool) or isinstance(right, bool) or not (
            isinstance(left, (int, float)) and isinstance(right, (int, float))
        ):
            raise ExpressionTypeError(
                f"arithmetic {op!r} requires numeric operands, got "
                f"{type(left).__name__} and {type(right).__name__}"
            )
        if op == "add":
            return left + right
        if op == "sub":
            return left - right
        if op == "mul":
            return left * right
        if right == 0:
            # Division by zero is unknown, never False (07 §5.1).
            return UNKNOWN
        return left / right

    @staticmethod
    def _in(value: Any, options: Any) -> Any:
        if not isinstance(options, list):
            raise ExpressionTypeError("'in' requires a list literal")
        try:
            return any(value == option for option in options)
        except TypeError as exc:
            raise ExpressionTypeError(str(exc)) from exc

    @staticmethod
    def _between(value: Any, low: Any, high: Any) -> Any:
        try:
            return low <= value <= high
        except TypeError as exc:
            raise ExpressionTypeError(str(exc)) from exc

    @staticmethod
    def _date_diff(left: Any, right: Any) -> Any:
        if not (isinstance(left, str) and isinstance(right, str)):
            raise ExpressionTypeError("date_diff requires ISO-8601 date strings")
        try:
            start = datetime.fromisoformat(left.replace("Z", "+00:00"))
            end = datetime.fromisoformat(right.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ExpressionTypeError(f"date_diff cannot parse dates: {exc}") from exc
        return (end - start).days

    @staticmethod
    def _string_match(value: Any, pattern: Any) -> Any:
        if not (isinstance(value, str) and isinstance(pattern, str)):
            raise ExpressionTypeError("string_match requires string operands")
        return fnmatchcase(value, pattern)

    def evaluate(self, node: dict[str, Any]) -> Any:
        return self._value_of(node)


def _record_getter(record) -> Any:
    by_id = {f.field_id: f for f in record.fields}

    def getter(field_id: str):
        item = by_id.get(field_id)
        if item is None:
            return None, False, [], False
        usable = item.status not in _MISSING_STATUSES and item.value is not None
        return item.value, usable, list(item.evidence), item.status is FieldValueStatus.low_confidence

    return getter


def _table_row_getter(table, row: tuple, index: int) -> Any:
    positions = {column.field_id: i for i, column in enumerate(table.columns)}
    roles = table.row_roles[index] if index < len(table.row_roles) else "detail"

    def getter(field_id: str):
        position = positions.get(field_id)
        if position is None:
            return None, False, [], False
        value = row[position]
        usable = value is not None and roles == "detail"
        return value, usable, [], False

    return getter


def _evidence(accesses: Iterable[FieldAccess], obtained_by: str, *, cap: int = 20) -> list[EvidenceRef]:
    evidence: list[EvidenceRef] = []
    seen: set[str] = set()
    for access in accesses:
        if access.field_id in seen:
            continue
        seen.add(access.field_id)
        evidence.append(
            EvidenceRef(
                id=f"field:{access.field_id}",
                evidence_type="extracted_value",
                source_anchors=list(access.anchors),
                value=access.value,
                obtained_by=obtained_by,
            )
        )
    return evidence[:cap]


def _verdict_of(value: Any) -> str:
    if value is True:
        return "pass"
    if value is False:
        return "fail"
    return "unknown"


def _applicability_gate(data: "_IO") -> tuple[str, list[str]]:
    """Verdict mapping for the applicability / precondition gates (07 W0).

    ``False`` → ``not_applicable``. An *explicit* ``null`` (the field is
    present in the payload but its value is unknown) must not be silently
    treated as "applicable": the verdict becomes ``unknown`` instead of a
    definite pass/fail (feasibility review §4). Omitting the field
    entirely means "no applicability gate for this rule" and evaluation
    proceeds.
    """

    fields = data.model_fields_set
    unknown_gates: list[str] = []
    if "applicable" in fields and data.applicable is None:
        unknown_gates.append("applicable")
    if "preconditions_met" in fields and data.preconditions_met is None:
        unknown_gates.append("preconditions_met")
    if unknown_gates:
        return "unknown", unknown_gates
    if data.applicable is False or data.preconditions_met is False:
        return "not_applicable", []
    return "", []


def _apply_exceptions(
    exception_values: list[Any],
) -> str | None:
    """Exception gate: any True → not_applicable; any UNKNOWN → unknown."""

    if any(value is True for value in exception_values):
        return "not_applicable"
    if any(value is UNKNOWN for value in exception_values):
        return "unknown"
    return None


class _IO(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- DA07.5.1 ----------------------------------------------------------------

class EvaluateScalarInput(_IO):
    spec: ExecutableSpec
    exceptions: list[ExecutableSpec] = PydanticField(default_factory=list)
    record_ref: dict[str, Any] | None = None
    record: dict[str, Any] | None = None
    applicable: bool | None = None
    preconditions_met: bool | None = None


class EvaluateScalarOutput(_IO):
    assessment: Assessment[str]


@operation(
    "DA07.5.1",
    input_model=EvaluateScalarInput,
    output_model=EvaluateScalarOutput,
    description="标量表达式计算：封闭算子 AST 三值解释器对单条 ExtractedRecordRef 求值（DA07.5.1）",
    idempotent=True,
)
def evaluate_scalar_expression(
    data: EvaluateScalarInput, ctx: CallContext, runtime
) -> CapabilityResult[EvaluateScalarOutput]:
    if data.record is None and data.record_ref is None:
        raise invalid_input(
            "provide the record inline or as an ExtractedRecordRef-shaped record_ref",
            target="record",
        )
    from dataagent_contracts.core import ExtractedRecordRef

    record = (
        ExtractedRecordRef.model_validate(data.record)
        if data.record is not None
        else ExtractedRecordRef.model_validate(data.record_ref)
    )
    if data.spec.backend_kind != "expression":
        raise invalid_input(
            f"evaluate_scalar_expression requires backend_kind=expression, got {data.spec.backend_kind}",
            target="spec.backend_kind",
        )
    # 07 §5.4: the spec's EngineBinding is compared against the installed
    # interpreter before anything is evaluated; mismatch fails closed.
    if data.spec.engine_binding is not None:
        binding_issue = engines.engine_binding_issue(
            data.spec.engine_binding, expected_engine_id=ENGINE_ID
        )
        if binding_issue is not None:
            return CapabilityResult[EvaluateScalarOutput](
                status=CapabilityStatus.failed, issues=[binding_issue]
            )
    gate, unknown_gates = _applicability_gate(data)
    if gate == "not_applicable":
        assessment = Assessment[str](
            assessment_id="as:" + data.spec.spec_id,
            target_ref=data.spec.source_refs[0] if data.spec.source_refs else VersionedRef(id=data.spec.spec_id, revision=data.spec.revision),
            verdict="not_applicable",
            unknowns=[],
            next_actions=["rule not applicable or precondition unmet for this record"],
        )
        return CapabilityResult[EvaluateScalarOutput](
            status=CapabilityStatus.ok, data=EvaluateScalarOutput(assessment=assessment)
        )
    if gate == "unknown":
        assessment = Assessment[str](
            assessment_id="as:" + data.spec.spec_id,
            target_ref=data.spec.source_refs[0]
            if data.spec.source_refs
            else VersionedRef(id=data.spec.spec_id, revision=data.spec.revision),
            verdict="unknown",
            unknowns=[f"{name} is unknown" for name in unknown_gates],
            next_actions=[
                "resolve the applicability/precondition evidence before relying on the verdict"
            ],
        )
        return CapabilityResult[EvaluateScalarOutput](
            status=CapabilityStatus.ok,
            data=EvaluateScalarOutput(assessment=assessment),
            completeness=helpers.complete("scalar expression evaluation"),
        )

    issues: list[Issue] = []
    unknowns: list[str] = []
    verdict: str
    try:
        accesses: list[FieldAccess] = []
        getter = _record_getter(record)
        interpreter = _Interpreter(getter, accesses)
        exception_values = [
            interpreter.evaluate(spec.expression_or_call) for spec in data.exceptions
        ]
        gate = _apply_exceptions(exception_values)
        if gate is not None:
            verdict = gate
            if gate == "unknown":
                unknowns.append("exception expression evaluated to unknown")
        else:
            value = interpreter.evaluate(data.spec.expression_or_call)
            verdict = _verdict_of(value)
        unknowns.extend(a.field_id for a in accesses if a.unknown)
        evidence = _evidence(accesses, "da07.5.1/evaluate_scalar_expression", cap=200)
        low = [a.field_id for a in accesses if a.low_confidence]
        if low:
            issues.append(
                Issue(
                    code="da07.low_confidence_field",
                    severity=Severity.warning,
                    message=f"low-confidence fields participated: {sorted(low)}",
                    retryable=False,
                )
            )
    except ExpressionTypeError as exc:
        return CapabilityResult[EvaluateScalarOutput](
            status=CapabilityStatus.failed,
            issues=[
                Issue(
                    code="da07.expression_type_mismatch",
                    severity=Severity.error,
                    message=str(exc),
                    retryable=False,
                    suggested_action="align literal types with the field value types",
                )
            ],
        )

    assessment = Assessment[str](
        assessment_id="as:" + data.spec.spec_id,
        target_ref=data.spec.source_refs[0]
        if data.spec.source_refs
        else VersionedRef(id=data.spec.spec_id, revision=data.spec.revision),
        verdict=verdict,
        basis_refs=[f"spec:{data.spec.spec_id}"],
        unknowns=sorted(set(unknowns)),
        evidence=evidence,
    )
    return CapabilityResult[EvaluateScalarOutput](
        status=CapabilityStatus.ok,
        data=EvaluateScalarOutput(assessment=assessment),
        issues=issues,
        completeness=helpers.complete("scalar expression evaluation"),
    )


# --- DA07.5.2 ----------------------------------------------------------------


class EvaluateTableInput(_IO):
    spec: ExecutableSpec
    exceptions: list[ExecutableSpec] = PydanticField(default_factory=list)
    table_ref: dict[str, Any]
    applicable: bool | None = None
    preconditions_met: bool | None = None
    max_rows: int | None = PydanticField(default=None, ge=1)


class EvaluateTableOutput(_IO):
    assessment: Assessment[str]
    verdicts: list[dict[str, Any]]
    counts: dict[str, int]


@operation(
    "DA07.5.2",
    input_model=EvaluateTableInput,
    output_model=EvaluateTableOutput,
    description="表数据表达式计算：逐行求值，行角色保留，合计行不参与（DA07.5.2）",
    idempotent=True,
)
def evaluate_table_expression(
    data: EvaluateTableInput, ctx: CallContext, runtime
) -> CapabilityResult[EvaluateTableOutput]:
    from dataagent_contracts.core import TableRef

    table_ref = TableRef.model_validate(data.table_ref)
    if data.spec.backend_kind != "expression":
        raise invalid_input(
            f"evaluate_table_expression requires backend_kind=expression, got {data.spec.backend_kind}",
            target="spec.backend_kind",
        )
    table = helpers.load_table(runtime, table_ref)
    issues: list[Issue] = []
    excluded = table.non_detail_summary()
    if excluded:
        issues.append(
            Issue(
                code="da07.table_rows_excluded",
                severity=Severity.info,
                message=(
                    "non-detail rows excluded from evaluation to avoid double counting: "
                    + ", ".join(f"{role}={count}" for role, count in sorted(excluded.items()))
                ),
                retryable=False,
            )
        )

    if data.spec.engine_binding is not None:
        binding_issue = engines.engine_binding_issue(
            data.spec.engine_binding, expected_engine_id=ENGINE_ID
        )
        if binding_issue is not None:
            return CapabilityResult[EvaluateTableOutput](
                status=CapabilityStatus.failed, issues=[binding_issue]
            )

    gate, unknown_gates = _applicability_gate(data)
    if gate == "not_applicable":
        assessment = Assessment[str](
            assessment_id="as:" + data.spec.spec_id,
            target_ref=VersionedRef(id=table_ref.asset.id, revision=table_ref.asset.revision),
            verdict="not_applicable",
            next_actions=["rule not applicable or precondition unmet for this table"],
        )
        return CapabilityResult[EvaluateTableOutput](
            status=CapabilityStatus.ok,
            data=EvaluateTableOutput(assessment=assessment, verdicts=[], counts={}),
            issues=issues,
        )
    if gate == "unknown":
        assessment = Assessment[str](
            assessment_id="as:" + data.spec.spec_id + ":table",
            target_ref=VersionedRef(id=table_ref.asset.id, revision=table_ref.asset.revision),
            verdict="unknown",
            unknowns=[f"{name} is unknown" for name in unknown_gates],
            next_actions=[
                "resolve the applicability/precondition evidence before relying on the verdict"
            ],
        )
        return CapabilityResult[EvaluateTableOutput](
            status=CapabilityStatus.ok,
            data=EvaluateTableOutput(assessment=assessment, verdicts=[], counts={}),
            issues=issues,
            completeness=helpers.complete("table expression evaluation"),
        )

    identity = table_ref.row_identity or [table.columns[0].field_id if table.columns else "row"]
    positions = {column.field_id: i for i, column in enumerate(table.columns)}
    limit = data.max_rows or 10000
    verdicts: list[dict[str, Any]] = []
    counts = {"pass": 0, "fail": 0, "unknown": 0, "not_applicable": 0, "error": 0}
    type_mismatches = 0
    unknown_fields: set[str] = set()
    participating: dict[str, list[Any]] = {}

    for index in table.detail_rows()[:limit]:
        row = table.rows[index]
        row_key = {
            field_id: row[positions[field_id]] if field_id in positions else None
            for field_id in identity
        }
        accesses: list[FieldAccess] = []
        interpreter = _Interpreter(_table_row_getter(table, row, index), accesses)
        try:
            exception_values = [
                interpreter.evaluate(spec.expression_or_call) for spec in data.exceptions
            ]
            gate = _apply_exceptions(exception_values)
            verdict = gate if gate is not None else _verdict_of(
                interpreter.evaluate(data.spec.expression_or_call)
            )
        except ExpressionTypeError:
            verdict = "unknown"
            type_mismatches += 1
        counts[verdict] = counts.get(verdict, 0) + 1
        unknown_fields.update(a.field_id for a in accesses if a.unknown)
        for access in accesses:
            participating.setdefault(access.field_id, []).append(access.value)
        verdicts.append({"row_key": row_key, "verdict": verdict})

    if len(table.detail_rows()) > limit:
        issues.append(
            Issue(
                code="da07.row_limit_reached",
                severity=Severity.warning,
                message=f"evaluation truncated at {limit} of {len(table.detail_rows())} detail rows",
                retryable=True,
            )
        )
    truncated_rows = len(table.detail_rows()) > limit
    if type_mismatches:
        issues.append(
            Issue(
                code="da07.expression_type_mismatch",
                severity=Severity.warning,
                message=f"{type_mismatches} row(s) evaluated to unknown due to type mismatch",
                retryable=False,
                suggested_action="align literal types with the column value types",
            )
        )

    if counts["pass"] and not (counts["fail"] or counts["unknown"] or counts["not_applicable"]):
        overall = "pass"
    elif counts["fail"] and not (counts["pass"] or counts["unknown"] or counts["not_applicable"]):
        overall = "fail"
    else:
        overall = "unknown"

    evidence = _evidence(
        (
            FieldAccess(
                field_id=field_id,
                value=values[:20],
                anchors=[],
                unknown=all(value is None for value in values),
            )
            for field_id, values in participating.items()
        ),
        "da07.5.2/evaluate_table_expression",
    )
    assessment = Assessment[str](
        assessment_id="as:" + data.spec.spec_id + ":table",
        target_ref=VersionedRef(id=table_ref.asset.id, revision=table_ref.asset.revision),
        verdict=overall,
        basis_refs=[f"spec:{data.spec.spec_id}", f"table:{table_ref.asset.id}"],
        unknowns=sorted(unknown_fields),
        next_actions=[f"counts: {counts}"],
        evidence=evidence,
    )
    status = (
        CapabilityStatus.partial
        if (type_mismatches or counts.get("error") or truncated_rows)
        else CapabilityStatus.ok
    )
    return CapabilityResult[EvaluateTableOutput](
        status=status,
        data=EvaluateTableOutput(assessment=assessment, verdicts=verdicts, counts=counts),
        issues=issues,
        completeness=helpers.truncated(
            "table expression evaluation",
            reason=f"row limit reached: evaluated {limit} of {len(table.detail_rows())} detail rows",
            observed={"detail_rows": len(table.detail_rows()), "evaluated_rows": limit},
        )
        if truncated_rows
        else helpers.complete(
            "table expression evaluation", {"detail_rows": len(table.detail_rows())}
        ),
    )
