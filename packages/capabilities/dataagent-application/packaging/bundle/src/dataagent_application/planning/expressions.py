"""Two-phase planning: expression generation (DA06.3.5) and single-table SQL
generation (DA06.3.1).

First call (no ``proposal``) returns ``needs_input`` with an
``inference_request`` describing the closed AST schema / the SQL shape, the
rule conditions and the table schema; the request is gated on an
``EgressDecision`` first (07 §4.1). The second call is validated
deterministically: closed operator set, field/condition coverage, type
check, and consistency with ``rule.combination`` (expressions); single
SELECT, bound tables only, function blacklist, and — when a bound
``RequirementSpec`` is supplied — caliber binding of measure, aggregation
and fixed filters (SQL, via sqlglot). Caliber binding is scope-aware: only
the SELECT that produces the result (and the CTE chain it reads) carries
filters, time windows and aggregates, the bound table may be read only
once (no self-joins), the read sources' column lineage is followed (a
renamed/computed ``amount * 2 AS amount`` is not the bound measure), and
HAVING / LIMIT / ROLLUP-family grouping never carries the caliber.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field as PydanticField
from sqlglot import exp, parse as sqlglot_parse

from dataagent_contracts.core import (
    CallContext,
    CapabilityResult,
    CapabilityStatus,
    EngineBinding,
    ExecutableSpec,
    Issue,
    RuleDefinition,
    SemanticDraft,
    Severity,
    VersionedRef,
)

from dataagent_application import helpers
from dataagent_application.contracts import RequirementSpec
from dataagent_application.execution.expressions import (
    CLOSED_OPS,
    INTERPRETER_VERSION,
    ENGINE_ID as EXPRESSION_ENGINE_ID,
    referenced_condition_ids,
    referenced_fields,
    type_check,
    _walk_op,
)
from dataagent_runtime.enforcement import egress_check
from dataagent_runtime.errors import invalid_input
from dataagent_runtime.registry import operation

SQL_DIALECT = "duckdb"
SQL_ENGINE_ID = "duckdb"

# A revision of this shape names content by address; only such a rule_ref
# revision can bind the inline rule to the bytes an EgressDecision covers
# (r38 F1).
_RULE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")

# Structural field metadata the model needs to compile an expression:
# ``field_id`` and ``value_type`` only. Anything beyond these keys (samples,
# descriptions, raw payloads) is caller content that no decision has covered,
# so it never reaches the model (r38 F1) — and since r40 F1a the projection
# is rebuilt by ``_model_visible_fields`` from the bound rule's referenced
# fields with a closed value-type vocabulary.

# The closed vocabulary of field value types (r40 F1a). ``value_type`` is
# pure caller free text — the EgressDecision covers the rule content, not
# the field metadata — so it may only travel as a member of this closed set;
# anything else is refused without echoing it. It matches the type
# vocabulary the execution layer's type checker and SQL column mapping
# understand (``execution/sql.py`` ``_COLUMN_TYPES`` and the data layer's
# parsed schema types).
_FIELD_VALUE_TYPES = frozenset(
    {
        "unknown",
        "string",
        "number",
        "integer",
        "float",
        "decimal",
        "boolean",
        "date",
        "datetime",
        "time",
        "timestamp",
        "json",
    }
)


def _model_visible_fields(
    fields: list[dict[str, Any]], rule: RuleDefinition
) -> list[dict[str, Any]]:
    """Rebuild the model-visible field metadata from bound content (r40 F1a).

    The projection carries only what the *rule* references — the rule's
    ``referenced_fields`` are part of the (byte-bound) rule content, so a
    field id can never smuggle caller free text past the decision — and a
    ``value_type`` from the closed vocabulary. Fields the rule does not
    reference are dropped: the AST can only leaf at rule-referenced fields
    anyway. A ``value_type`` outside the vocabulary is refused without
    echoing it: it is caller content no EgressDecision has covered.
    """

    referenced = set()
    for condition in rule.conditions:
        referenced.update(condition.referenced_fields)
    projected: list[dict[str, Any]] = []
    for field in fields:
        raw_type = field.get("value_type")
        value_type = str(raw_type).strip().lower() if raw_type is not None else "unknown"
        if value_type not in _FIELD_VALUE_TYPES:
            raise invalid_input(
                "fields[].value_type must be one of the closed vocabulary "
                + ", ".join(sorted(_FIELD_VALUE_TYPES))
                + "; unverified caller content is not sent to the model",
                target="fields[].value_type",
            )
        if field.get("field_id") in referenced:
            projected.append({"field_id": field["field_id"], "value_type": value_type})
    return projected


def _anchor_view(anchor: Any) -> dict[str, Any]:
    if isinstance(anchor, dict):
        return anchor
    return anchor.model_dump(mode="json")


def _condition_view(condition: Any) -> dict[str, Any]:
    if isinstance(condition, dict):
        return {
            "condition_id": condition.get("condition_id"),
            "text": condition.get("text"),
            "referenced_fields": list(condition.get("referenced_fields") or []),
            "anchors": [_anchor_view(a) for a in condition.get("anchors") or []],
        }
    return {
        "condition_id": condition.condition_id,
        "text": condition.text,
        "referenced_fields": list(condition.referenced_fields),
        "anchors": [_anchor_view(a) for a in condition.anchors or []],
    }


def _rule_view(rule: Any) -> dict[str, Any]:
    """The rule content that reaches the model, canonically.

    Used to verify an inline rule against the stored content a
    ``rule_ref``'s revision addresses (r38 F1): everything in this view
    travels to the model in the inference request, so it must be exactly
    the content the EgressDecision covered.
    """

    if isinstance(rule, dict):
        conditions = rule.get("conditions") or []
        exceptions = rule.get("exceptions") or []
        return {
            "statement": rule.get("statement"),
            "combination": rule.get("combination"),
            "conditions": [_condition_view(c) for c in conditions],
            "exceptions": [
                (e.get("text") if isinstance(e, dict) else e) for e in exceptions
            ],
        }
    return {
        "statement": rule.statement,
        "combination": rule.combination,
        "conditions": [_condition_view(c) for c in rule.conditions],
        "exceptions": [e.text for e in rule.exceptions],
    }


def _verify_covered_rule(runtime, rule: RuleDefinition, rule_ref: dict | None) -> None:
    """Refuse an inline rule that is not the content the decision covers.

    When the caller cites a ``rule_ref``, its revision must be the content
    address of the stored rule and the inline rule must match those bytes
    on everything the model will see; any inline rewrite — or a ref that
    does not resolve — is refused *without echoing the content* (r38 F1).
    """

    if rule_ref is None:
        return
    revision = str(rule_ref.get("revision") or "")
    if not _RULE_DIGEST.match(revision):
        raise invalid_input(
            "rule_ref.revision must be the content address (sha256:<hex>) of the "
            "stored rule the EgressDecision covers",
            target="rule_ref.revision",
        )
    try:
        stored = runtime.content.get_json(revision)
    except FileNotFoundError:
        raise invalid_input(
            f"rule_ref {rule_ref.get('id')!r}@{revision} does not resolve to stored "
            "content; the rule content cannot be bound to the decision",
            target="rule_ref.revision",
        ) from None
    if _rule_view(rule) != _rule_view(stored):
        raise invalid_input(
            "the inline rule does not match the content bound to rule_ref; "
            "refusing to send unverified rule content to the model",
            target="rule",
        )

# 07 §5.2: functions that touch the filesystem, load extensions or escape the
# single-SELECT contract are rejected.
FUNCTION_BLACKLIST = frozenset(
    {
        "read_csv", "read_json", "read_parquet", "read_text", "read_blob",
        "read_xlsx", "read_iceberg", "read_delta", "glob", "gzip", "zstd",
        "attach", "install", "load", "copy", "export_database", "set",
        "pragma", "call", "checkpoint", "force_checkpoint",
        "shell", "system", "getenv", "read_file", "write_file",
    }
)


class _IO(BaseModel):
    model_config = ConfigDict(extra="forbid")


def sql_digest(sql: str) -> str:
    return "sha256:" + hashlib.sha256(sql.encode("utf-8")).hexdigest()


def validate_single_select_sql(sql: str, allowed_tables: set[str]) -> list[str]:
    """Deterministic SQL validation with sqlglot (07 §5.2).

    Rules: exactly one ``SELECT`` (CTEs allowed); every referenced table must
    be one of the bound inputs; blacklisted functions rejected; no commands
    (COPY/ATTACH/INSTALL/SET/...).
    """

    errors: list[str] = []
    try:
        statements = sqlglot_parse(sql, dialect=SQL_DIALECT)
    except Exception as exc:  # noqa: BLE001 - parse errors are input errors
        return [f"SQL does not parse as {SQL_DIALECT}: {type(exc).__name__}: {exc}"]
    if len(statements) != 1:
        return [f"exactly one statement is allowed, got {len(statements)}"]
    statement = statements[0]
    if not isinstance(statement, exp.Select):
        return [f"only a single SELECT is allowed, got {type(statement).__name__}"]
    # CTE names are query-local: they shadow nothing external.
    cte_names = {cte.alias_or_name.lower() for cte in statement.find_all(exp.CTE)}
    allowed_tables |= cte_names
    for node in statement.walk():
        node_value = node[0] if isinstance(node, tuple) else node
        if isinstance(node_value, (exp.Command,)):
            errors.append(f"SQL command is not allowed: {node_value.sql()[:60]}")
        if isinstance(node_value, (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create, exp.Attach, exp.Copy, exp.Pragma, exp.TruncateTable)):
            errors.append(f"statement type is not allowed: {type(node_value).__name__}")
        if isinstance(node_value, exp.Table):
            name = node_value.name.lower()
            if name not in allowed_tables:
                errors.append(
                    f"table {name!r} is not bound; bound tables: {sorted(allowed_tables)}"
                )
        if isinstance(node_value, (exp.Anonymous, exp.Func)):
            func_name = ""
            if isinstance(node_value, exp.Anonymous):
                func_name = str(node_value.this or "").lower()
            else:
                func_name = str(node_value.key).lower()
                # sqlglot names builtins like "read_csv" as their key
                for candidate in (func_name, str(getattr(node_value, "sql_name", lambda: "")()).lower()):
                    if candidate in FUNCTION_BLACKLIST:
                        func_name = candidate
                        break
            if func_name in FUNCTION_BLACKLIST:
                errors.append(f"function {func_name!r} is blacklisted")
    # String-scan fallback for anything sqlglot normalizes away (fail closed).
    lowered = " ".join(sql.lower().split())
    for banned in ("read_csv", "read_parquet", "read_json", "attach ", "install ", "copy ", "pragma "):
        if banned in lowered:
            errors.append(f"blacklisted SQL construct: {banned.strip()!r}")
    return errors


def _sql_table_name(table_ref: Any) -> str:
    """SQL-visible name for a bound TableRef (asset ids contain ':')."""

    hex_part = table_ref.asset.id.split(":", 1)[-1] if ":" in table_ref.asset.id else table_ref.asset.id
    return "t_" + "".join(ch for ch in hex_part if ch.isalnum())[:16]


# --- rule.combination consistency (07 §5.1 / feasibility review §5) -----------
#
# DA06.3.5 must not accept an AST that computes a different boolean function
# of the rule's conditions than ``rule.combination`` expresses (e.g. ``and``
# flipped to ``or``). Both are normalized to boolean formulas over the
# condition ids and compared by truth-table equivalence.

_COMBINATION_MAX_ATOMS = 16


def _tokenize_combination(text: str) -> list[str] | None:
    tokens: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if char in "(),":
            tokens.append(char)
            index += 1
            continue
        end = index
        while end < len(text) and (text[end].isalnum() or text[end] in "_-.:"):
            end += 1
        if end == index:
            return None
        tokens.append(text[index:end])
        index = end
    return tokens


def _parse_combination(
    tokens: list[str], condition_ids: set[str], position: list[int]
) -> tuple | None:
    """Recursive descent: expr := term ('or' term)* ; term := factor ('and' factor)*."""

    def parse_expr() -> tuple | None:
        left = parse_term()
        if left is None:
            return None
        parts = [left]
        while position[0] < len(tokens) and tokens[position[0]] == "or":
            position[0] += 1
            right = parse_term()
            if right is None:
                return None
            parts.append(right)
        return parts[0] if len(parts) == 1 else ("or", parts)

    def parse_term() -> tuple | None:
        left = parse_factor()
        if left is None:
            return None
        parts = [left]
        while position[0] < len(tokens) and tokens[position[0]] == "and":
            position[0] += 1
            right = parse_factor()
            if right is None:
                return None
            parts.append(right)
        return parts[0] if len(parts) == 1 else ("and", parts)

    def parse_factor() -> tuple | None:
        if position[0] >= len(tokens):
            return None
        token = tokens[position[0]]
        if token == "not":
            position[0] += 1
            inner = parse_factor()
            return None if inner is None else ("not", inner)
        if token in ("all", "any"):
            position[0] += 1
            if position[0] >= len(tokens) or tokens[position[0]] != "(":
                return None
            position[0] += 1
            connective = "and" if token == "all" else "or"
            parts = []
            while True:
                part = parse_expr()
                if part is None:
                    return None
                parts.append(part)
                if position[0] < len(tokens) and tokens[position[0]] == ",":
                    position[0] += 1
                    continue
                break
            if position[0] >= len(tokens) or tokens[position[0]] != ")":
                return None
            position[0] += 1
            return parts[0] if len(parts) == 1 else (connective, parts)
        if token == "(":
            position[0] += 1
            inner = parse_expr()
            if inner is None:
                return None
            if position[0] >= len(tokens) or tokens[position[0]] != ")":
                return None
            position[0] += 1
            return inner
        if token in condition_ids or token in ("true", "false"):
            position[0] += 1
            return ("atom", token)
        return None

    formula = parse_expr()
    if formula is None or position[0] != len(tokens):
        return None
    return formula


def _ast_skeleton(node: Any, counter: list[int]) -> tuple | None:
    """Boolean skeleton of a closed AST: leaves become condition atoms."""

    if not isinstance(node, dict):
        return None
    op = node.get("op")
    if op in ("and", "or", "not"):
        parts = []
        for child in node.get("args") or []:
            part = _ast_skeleton(child, counter)
            if part is None:
                return None
            parts.append(part)
        if not parts:
            return None
        if op == "not":
            return ("not", parts[0])
        return parts[0] if len(parts) == 1 else (op, parts)
    ids = referenced_condition_ids(node)
    if len(ids) == 1:
        return ("atom", next(iter(ids)))
    if not ids:
        counter[0] += 1
        return ("atom", f"?free{counter[0]}")
    # A comparison mixing several conditions cannot be mapped one-to-one.
    return None


def _substitute(formula: tuple, mapping: dict[str, tuple]) -> tuple:
    kind, value = formula[0], formula[1]
    if kind == "atom":
        return mapping.get(value, formula)
    if kind == "not":
        return ("not", _substitute(value, mapping))
    return (kind, [_substitute(part, mapping) for part in value])


def _formula_atoms(formula: tuple, atoms: set[str]) -> None:
    kind, value = formula[0], formula[1]
    if kind == "atom":
        atoms.add(value)
    elif kind == "not":
        _formula_atoms(value, atoms)
    else:
        for part in value:
            _formula_atoms(part, atoms)


def _eval_formula(formula: tuple, env: dict[str, bool]) -> bool:
    kind, value = formula[0], formula[1]
    if kind == "atom":
        return env[value]
    if kind == "not":
        return not _eval_formula(value, env)
    values = (_eval_formula(part, env) for part in value)
    return all(values) if kind == "and" else any(values)


def combination_mismatch(
    expression: Any, rule: RuleDefinition, unsupported: list[str]
) -> str | None:
    """``None`` when the AST matches ``rule.combination``; else the reason."""

    condition_ids = {c.condition_id for c in rule.conditions}
    if not (rule.combination or "").strip():
        # No declared combination: nothing to check the structure against
        # (the per-condition coverage checks above still ran).
        return None
    tokens = _tokenize_combination(rule.combination or "")
    if tokens is None:
        return (
            f"rule.combination {rule.combination!r} cannot be parsed as a boolean "
            "expression over the condition ids; the AST cannot be checked against it"
        )
    combination = _parse_combination(tokens, condition_ids, [0])
    if combination is None:
        return (
            f"rule.combination {rule.combination!r} does not parse over condition ids "
            f"{sorted(condition_ids)}"
        )
    skeleton = _ast_skeleton(expression, [0])
    if skeleton is None:
        return "expression mixes several conditions inside one comparison; it cannot match rule.combination one-to-one"
    # Conditions declared unsupported are excluded from the spec: the
    # combination is checked over the compiled part only, with the
    # unsupported conditions assumed satisfiable.
    true_atom = "?true"
    mapping = {cid: ("atom", true_atom) for cid in unsupported}
    combination = _substitute(combination, mapping)
    atoms: set[str] = set()
    _formula_atoms(combination, atoms)
    _formula_atoms(skeleton, atoms)
    if len(atoms) > _COMBINATION_MAX_ATOMS:
        return None  # too many conditions for a truth table; syntax checks still ran
    variables = sorted(atoms)
    for mask in range(1 << len(variables)):
        env = {name: bool(mask >> i & 1) for i, name in enumerate(variables)}
        env[true_atom] = True
        if _eval_formula(combination, env) != _eval_formula(skeleton, env):
            return (
                "the proposed expression does not compute the boolean function of the "
                f"conditions that rule.combination {rule.combination!r} expresses "
                "(e.g. an and/or/not structure mismatch)"
            )
    return None


# --- DA06.3.5 ----------------------------------------------------------------


class GenerateFunctionExpressionsInput(_IO):
    rule: RuleDefinition
    rule_ref: dict[str, Any] | None = None
    fields: list[dict[str, Any]] = PydanticField(default_factory=list)
    proposal: dict[str, Any] | None = None
    egress_decision_ref: str | None = None
    destination: dict[str, str] | None = None


class GenerateFunctionExpressionsOutput(_IO):
    spec: ExecutableSpec
    exception_specs: list[ExecutableSpec] = []


@operation(
    "DA06.3.5",
    input_model=GenerateFunctionExpressionsInput,
    output_model=GenerateFunctionExpressionsOutput,
    description="函数调用与表达式生成（两段式）：规则条件编译为封闭算子 AST，保留条件来源，结构须与 rule.combination 一致（DA06.3.5）",
)
def generate_function_expressions(
    data: GenerateFunctionExpressionsInput, ctx: CallContext, runtime
) -> CapabilityResult[GenerateFunctionExpressionsOutput]:
    field_types = {f["field_id"]: f.get("value_type", "unknown") for f in data.fields}
    known_fields = set(field_types)
    if data.proposal is None:
        # r38 F1: bind the inline rule to the stored content the cited
        # rule_ref addresses — an inline rewrite never reaches the model.
        _verify_covered_rule(runtime, data.rule, data.rule_ref)
        conditions = [
            {
                "condition_id": c.condition_id,
                "text": c.text,
                "referenced_fields": c.referenced_fields,
                "anchors": [
                    a if isinstance(a, dict) else a.model_dump(mode="json") for a in c.anchors
                ],
            }
            for c in data.rule.conditions
        ]
        request = {
            "kind": "expression_ast",
            "statement": data.rule.statement,
            "combination": data.rule.combination,
            "conditions": conditions,
            "exceptions": [e.text for e in data.rule.exceptions],
            # Only structural field metadata travels to the model, rebuilt
            # from the (byte-bound) rule's referenced fields with a closed
            # value-type vocabulary: samples, unreferenced fields and any
            # other caller payload are content no EgressDecision has
            # covered (r38 F1, r40 F1a).
            "fields": _model_visible_fields(data.fields, data.rule),
            "closed_operators": sorted(CLOSED_OPS - {"field", "literal"}),
            "ast_shape": {
                "node": "{'op': <operator>, 'args': [<node>...]}",
                "field_leaf": "{'op': 'field', 'field_id': ..., 'condition_id': <condition_id>}",
                "literal_leaf": "{'op': 'literal', 'value': <scalar>}",
                "operators": {
                    "logic": ["and", "or", "not"],
                    "comparison": ["eq", "ne", "lt", "le", "gt", "ge"],
                    "arithmetic": ["add", "sub", "mul", "div"],
                    "special": ["in", "between", "is_missing", "date_diff", "string_match"],
                },
            },
            "constraints": [
                "every leaf field_id must be one of fields[].field_id",
                "every rule condition_id must be referenced by at least one leaf",
                "every leaf condition_id must be a rule condition_id",
                "the and/or/not structure must compute the same boolean function of the "
                "conditions as rule.combination",
            ],
            "instruction": (
                "Compile the rule conditions (and exceptions, if any) into the closed AST "
                "shape; keep condition_id provenance on the leaves. Conditions that the "
                "operator set cannot express must be left out and reported in unsupported_conditions."
            ),
        }
        content_refs = (
            [VersionedRef(id=data.rule_ref["id"], revision=data.rule_ref["revision"])]
            if data.rule_ref
            else [
                VersionedRef(
                    id="rule:" + hashlib.sha256(data.rule.statement.encode("utf-8")).hexdigest()[:16],
                    revision="r1",
                )
            ]
        )
        request, gate_issues, allowed = helpers.gate_inference_request(
            runtime,
            request,
            data.egress_decision_ref,
            content_refs=content_refs,
            check=egress_check,
            destination=data.destination,
        )
        if allowed:
            issues = [
                Issue(
                    code="da06.inference_required",
                    severity=Severity.info,
                    message="agent-provided expression AST is required",
                    retryable=False,
                    suggested_action="replay with a proposal {expression, exceptions?, unsupported_conditions?}",
                    inference_request=request,
                )
            ] + gate_issues
        else:
            issues = [
                issue.model_copy(update={"inference_request": request})
                for issue in gate_issues
            ] or [
                Issue(
                    code="da12.egress_required",
                    severity=Severity.error,
                    message="egress decision denied carrying the rule content to the model",
                    retryable=False,
                    inference_request=request,
                )
            ]
        return CapabilityResult[GenerateFunctionExpressionsOutput](
            status=CapabilityStatus.needs_input,
            data=None,
            issues=issues,
            completeness=helpers.complete("expression generation"),
        )

    proposal = data.proposal
    unsupported = list(proposal.get("unsupported_conditions") or [])
    expression = proposal.get("expression")
    if not isinstance(expression, dict):
        raise invalid_input("proposal.expression must be an AST object", target="proposal.expression")
    rule = data.rule
    condition_ids = {c.condition_id for c in rule.conditions}
    if not rule.conditions and not expression:
        raise invalid_input("rule has no conditions; nothing to compile")

    _walk_op(expression)
    used_fields = referenced_fields(expression)
    unknown_fields = used_fields - known_fields if known_fields else set()
    if unknown_fields:
        raise invalid_input(
            f"expression references fields outside the bound schema: {sorted(unknown_fields)}",
            target="proposal.expression",
        )
    used_conditions = referenced_condition_ids(expression)
    bogus_conditions = used_conditions - condition_ids
    if bogus_conditions:
        raise invalid_input(
            f"expression references unknown condition ids: {sorted(bogus_conditions)}",
            target="proposal.expression",
        )
    missing_conditions = condition_ids - used_conditions - set(unsupported)
    if missing_conditions:
        raise invalid_input(
            "conditions not covered by the expression and not declared unsupported: "
            f"{sorted(missing_conditions)}",
            target="proposal.expression",
        )
    if unsupported and not set(unsupported) <= condition_ids:
        raise invalid_input(
            f"unsupported_conditions must reference rule conditions: {sorted(set(unsupported))}",
            target="proposal.unsupported_conditions",
        )
    type_problems = type_check(expression, field_types) if field_types else []
    if type_problems:
        raise invalid_input(
            "expression type check failed: " + "; ".join(type_problems), target="proposal.expression"
        )
    # The and/or/not structure must compute the same boolean function of
    # the conditions as rule.combination (B3: no silent inversion).
    mismatch = combination_mismatch(expression, rule, unsupported)
    if mismatch is not None:
        return CapabilityResult[GenerateFunctionExpressionsOutput](
            status=CapabilityStatus.failed,
            data=None,
            issues=[
                Issue(
                    code="da06.combination_mismatch",
                    severity=Severity.error,
                    message=mismatch,
                    retryable=False,
                    suggested_action="re-propose an AST whose and/or/not structure matches rule.combination",
                )
            ],
        )

    exception_specs: list[ExecutableSpec] = []
    for index, exception_ast in enumerate(proposal.get("exceptions") or []):
        if not isinstance(exception_ast, dict):
            raise invalid_input(f"exception #{index} must be an AST object")
        _walk_op(exception_ast)
        exception_fields = referenced_fields(exception_ast)
        bad_fields = exception_fields - known_fields if known_fields else set()
        if bad_fields:
            raise invalid_input(
                f"exception #{index} references unknown fields: {sorted(bad_fields)}"
            )
        problems = type_check(exception_ast, field_types) if field_types else []
        if problems:
            raise invalid_input(
                f"exception #{index} type check failed: " + "; ".join(problems)
            )
        exception_specs.append(
            ExecutableSpec(
                spec_id=f"{rule.statement[:24].replace(' ', '_') or 'rule'}:exc{index}",
                revision="r1",
                backend_kind="expression",
                expression_or_call=exception_ast,
                source_refs=[VersionedRef(id=data.rule_ref["id"], revision=data.rule_ref["revision"])]
                if data.rule_ref
                else [],
            )
        )

    source_refs = (
        [VersionedRef(id=data.rule_ref["id"], revision=data.rule_ref["revision"])]
        if data.rule_ref
        else []
    )
    spec = ExecutableSpec(
        spec_id=f"expr:{hashlib.sha256((rule.statement + repr(sorted(used_fields))).encode('utf-8')).hexdigest()[:16]}",
        revision="r1",
        backend_kind="expression",
        expression_or_call=expression,
        source_refs=source_refs,
        engine_binding=EngineBinding(
            engine_id=EXPRESSION_ENGINE_ID, engine_version=INTERPRETER_VERSION
        ),
    )
    issues = []
    if unsupported:
        issues.append(
            Issue(
                code="da06.conditions_unsupported",
                severity=Severity.warning,
                message=(
                    "conditions the closed operator set cannot express are excluded from the "
                    f"spec and must be judged manually: {sorted(unsupported)}"
                ),
                retryable=False,
                suggested_action="route the rule to DA03.15 for manual decidability",
            )
        )
    if rule.exceptions and not exception_specs:
        issues.append(
            Issue(
                code="da06.exceptions_not_compiled",
                severity=Severity.warning,
                message="rule has exception clauses but no exception expressions were proposed",
                retryable=False,
                suggested_action="re-propose with exceptions or judge the exceptions manually",
            )
        )
    status = CapabilityStatus.partial if issues else CapabilityStatus.ok
    return CapabilityResult[GenerateFunctionExpressionsOutput](
        status=status,
        data=GenerateFunctionExpressionsOutput(spec=spec, exception_specs=exception_specs),
        issues=issues,
        completeness=helpers.complete("expression generation"),
    )


# --- DA06.3.1 ----------------------------------------------------------------


class GenerateSingleTableSqlInput(_IO):
    table_ref: dict[str, Any]
    metrics: list[dict[str, Any]] = PydanticField(default_factory=list)
    requirement: dict[str, Any] | None = None
    statement: str | None = None
    proposal: dict[str, Any] | None = None
    egress_decision_ref: str | None = None
    destination: dict[str, str] | None = None


class GenerateSingleTableSqlOutput(_IO):
    spec: ExecutableSpec
    table_name: str


_AGG_FUNCS = {"sum": "sum", "avg": "avg", "min": "min", "max": "max", "count": "count"}

# A bound filter's text is expected to be a predicate "field <op> value"; the
# operator and the constant are part of the caliber (review §5), not just the
# field's presence.
_FILTER_PREDICATE = re.compile(
    r"^\s*(?P<field>[^\s!=<>~]+)\s*(?P<op>!=|>=|<=|=|>|<)\s*(?P<value>.+?)\s*$"
)
_OP_NAMES = {"=": "eq", "!=": "ne", ">": "gt", ">=": "ge", "<": "lt", "<=": "le"}
_SQLGLOT_OPS = {
    "eq": "eq", "neq": "ne", "ne": "ne", "gt": "gt", "gte": "ge", "lt": "lt", "lte": "le",
}
_QUOTE_FOLD = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})
_THOUSANDS_SEPARATOR = re.compile(r"(?<=\d),(?=\d)")


def _normalize_filter_value(value: Any) -> str | None:
    """Comparable form of a filter/SQL literal; ``None`` when not comparable."""

    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return None
    if not isinstance(value, (str, int, float)):
        return None
    text = str(value).strip().translate(_QUOTE_FOLD)
    if len(text) >= 2 and text[0] in "'\"" and text[-1] == text[0]:
        text = text[1:-1]
    return _THOUSANDS_SEPARATOR.sub("", text).strip().lower()


def _collect_conjunctive(
    node: Any,
    predicates: dict[str, set[tuple[str, str]]],
    lineage: dict[str, tuple[str, Any]] | None = None,
) -> None:
    """Collect the predicates that hold *unconditionally* in a WHERE clause.

    A bound fixed filter or time range is only carried by a predicate that
    must be true for every row the SQL keeps: a conjunct of the WHERE's
    top-level AND chain. A predicate beneath an OR is an *alternative*
    (``approved = true OR approved = false`` holds for every row, so it
    binds nothing), and one beneath a NOT is inverted — neither may satisfy
    a bound filter or range (tester r22 B1).

    *lineage* maps the exported column names of the read sources (CTE /
    derived table) to what they carry; a predicate on a column a read
    source computed (``amount * 2 AS amount``) constrains that derived
    value, not the physical bound column, so it binds nothing (tester
    r26 B1).
    """

    while isinstance(node, exp.Paren):
        node = node.this
    if isinstance(node, exp.And):
        _collect_conjunctive(node.this, predicates, lineage)
        _collect_conjunctive(node.expression, predicates, lineage)
        return
    if isinstance(node, (exp.Or, exp.Not)):
        return  # alternatives and negations never bind a fixed constraint
    if isinstance(node, exp.Between):
        column = node.this
        if isinstance(column, exp.Column):
            physical = _lineage_physical(column.name.lower(), lineage)
            if physical is None:
                return  # the derived column is not the bound column
            for op, side in (("ge", node.args.get("low")), ("le", node.args.get("high"))):
                normalized = _normalize_filter_value(_literal_value(side))
                if normalized is not None:
                    predicates.setdefault(physical, set()).add((op, normalized))
        return
    if not isinstance(node, exp.Binary):
        return
    op = _SQLGLOT_OPS.get(node.key)
    if op is None:
        return
    left, right = node.this, node.expression
    if isinstance(left, exp.Column) and not isinstance(right, exp.Column):
        column, literal = left.name.lower(), _literal_value(right)
    elif isinstance(right, exp.Column) and not isinstance(left, exp.Column):
        column, literal = right.name.lower(), _literal_value(left)
    else:
        return
    physical = _lineage_physical(column, lineage)
    if physical is None:
        return  # the derived column is not the bound column
    normalized = _normalize_filter_value(literal)
    if normalized is None:
        # Non-literal comparison: keep a presence marker only.
        predicates.setdefault(physical, set()).add(("?", "?"))
    else:
        predicates.setdefault(physical, set()).add((op, normalized))


def _iter_where_conjuncts(node: Any):
    """Yield the top-level AND conjuncts of a WHERE clause.

    Every conjunct must hold for *every* row the SELECT keeps; a predicate
    beneath an OR is an alternative, not a conjunct (tester r22 B1).
    """

    while isinstance(node, exp.Paren):
        node = node.this
    if isinstance(node, exp.And):
        yield from _iter_where_conjuncts(node.this)
        yield from _iter_where_conjuncts(node.expression)
        return
    yield node


def _bounds_physical_column(conjunct: Any) -> bool:
    """Whether the conjunct is a form a bound operator/value pair can match.

    Only simple comparisons (``col <op> literal``, either side) and
    ``col BETWEEN low AND high`` map onto the bound predicate pairs; every
    other form over an allowed column (IN, LIKE, OR alternatives, NOT, IS
    NULL, ...) constrains it in a way the binding cannot check and is
    rejected by the caller (tester r27 B1).
    """

    node = conjunct
    while isinstance(node, exp.Paren):
        node = node.this
    if isinstance(node, exp.Between):
        return isinstance(node.this, exp.Column)
    if not isinstance(node, exp.Binary):
        return False
    if _SQLGLOT_OPS.get(node.key) is None:
        return False
    left, right = node.this, node.expression
    return (
        isinstance(left, exp.Column) and not isinstance(right, exp.Column)
    ) or (
        isinstance(right, exp.Column) and not isinstance(left, exp.Column)
    )


# --- scope-aware caliber collection (07 §5.2 / W0 §3; tester r24/r25 B1) ---------
#
# A bound filter, time window or measure aggregation carries the caliber only
# when it constrains the rows the delivered result actually aggregates. A
# predicate that lives in a CTE nobody reads, an EXISTS or scalar subquery
# binds nothing, a windowed ``sum(x) OVER ()`` is not the group aggregate, and
# a self-join multiplies rows. Collection therefore walks the SELECT that
# produces the result, follows the CTE / derived-table data flow down to the
# bound physical table, and never descends into unrelated subquery scopes.
#
# The aggregate's *shape* carries the caliber too (W0 §3): it must be
# ``<aggregation>(<measure field_id>)``, and the projection may not transform
# it — neither around the aggregate (``sum(amount) * 2``), inside its
# argument (``sum(amount * 2)``, ``sum(CASE ...)``) nor via a FILTER clause;
# reading a CTE column that an inner SELECT computed by aggregating is only
# allowed as the bare column. A read source's exported columns carry a
# *lineage* (tester r26): only the bare passthrough of a physical column
# binds — a computed or renamed export (``amount * 2 AS amount``) makes an
# outer aggregate or predicate bind nothing. HAVING, LIMIT/OFFSET and the
# ROLLUP/CUBE/GROUPING SETS family change the delivered groups/rows without
# touching the bound text and never carry the caliber. Finally, only the
# bound filters themselves may select the rows (tester r27): every WHERE
# conjunct — of the result SELECT or a CTE/derived table it reads — must be
# a recognized predicate on the bound time/filter columns; any other
# conjunct (a dimension/measure filter, a predicate on a derived or
# aggregated column — a post-aggregation WHERE is a HAVING in disguise —
# or a column-less constant such as ``1 = 0``) narrows the delivered rows
# outside the bound caliber. Joins and samples never carry the caliber
# either (tester r29): a JOIN's ON conjunct is a WHERE in disguise
# (``JOIN (SELECT 'north') x ON t.region = x.keep``), an equi-join's right
# side can fan rows out by an unbounded factor, an ON subquery re-reads
# the bound table outside the read-once guard, and TABLESAMPLE / USING
# SAMPLE drops rows before the bound aggregation — none of it is verifiable
# against the bound predicates, so every join and every sampler is rejected.

_SCOPE_BARRIERS = (
    exp.Select,
    exp.Union,
    exp.Except,
    exp.Intersect,
    exp.Subquery,
    exp.Exists,
    exp.Window,
)
_MAX_SCOPE_DEPTH = 16


def _iter_scope(node: Any):
    """Yield the nodes of *one* query scope; subquery scopes are not entered."""

    yield node
    if isinstance(node, _SCOPE_BARRIERS):
        return
    for value in node.args.values():
        children = value if isinstance(value, list) else [value]
        for child in children:
            if isinstance(child, exp.Expression):
                yield from _iter_scope(child)


def _select_arg(select: exp.Select, key: str) -> Any:
    """``select.args`` value tolerating the ``from_``/``with_`` spellings."""

    if key in select.args:
        return select.args[key]
    return select.args.get(f"{key}_")


class _CaliberScope:
    """Binding facts accumulated from the SELECT scopes the result reads."""

    def __init__(self) -> None:
        self.predicates: dict[str, set[tuple[str, str]]] = {}
        self.where_columns: set[str] = set()
        # every top-level WHERE conjunct of every collected scope, as
        # (columns, bounds_physical, snippet): *columns* holds the resolved
        # physical column names — or ``#derived:<name>`` markers for columns
        # a read source computed/aggregated — *bounds_physical* says whether
        # the conjunct is a comparison/BETWEEN a bound predicate can match
        # (tester r27 B1).
        self.where_conjuncts: list[tuple[frozenset[str], bool, str]] = []
        self.aggregates: set[tuple[str, str]] = set()
        self.distinct_aggregates: set[tuple[str, str]] = set()
        self.filtered_aggregates: set[tuple[str, str]] = set()
        self.transformed_aggregates: set[tuple[str, str]] = set()
        self.group_columns: set[str] = set()
        self.table_refs: dict[str, int] = {}
        self.cte_refs: dict[str, int] = {}


# Value-preserving wrappers a projection may apply around its aggregate — or
# around an aggregated column a read source computed — (W0 §3 / tester r25).
# Anything else (arithmetic, CASE, string ops, ...) changes the delivered
# value and must not carry the metric version. They are equally allowed
# *inside* the aggregation around the bare measure column (tester r26:
# ``sum(CAST(amount AS DOUBLE))`` keeps every summand).
_VALUE_PRESERVING_WRAPPERS = (exp.Cast, exp.TryCast, exp.Paren)

# A lineage entry says what a SELECT's exported column carries:
#   ("column", <physical column>)  a bare column of the read source/table
#   ("agg", (<func>, <column>))    the bound aggregation computed in-scope
#   ("expr", <sqlglot node>)       anything a read source computed/renamed
#   ("ambiguous", None)            the same name exported by several sources
_Lineage = dict[str, tuple[str, Any]]


def _lineage_physical(
    name: str, lineage: _Lineage | None
) -> str | None:
    """Physical column a scope's column name resolves to, if it is one.

    A name the read sources do not export is a column of the physical table
    (``FROM t``) and resolves to itself; a name a read source exports only
    carries the caliber when it is the bare passthrough of a physical column
    — anything computed (``amount * 2 AS amount``) binds nothing (tester
    r26 B1).
    """

    if lineage is None:
        return name
    entry = lineage.get(name)
    if entry is None:
        return name
    if entry[0] == "column":
        return entry[1]
    return None


def _merge_lineage(target: _Lineage, extra: _Lineage) -> None:
    """Merge a read source's exported lineage into the scope's map."""

    for name, entry in extra.items():
        if name in target and target[name] != entry:
            target[name] = ("ambiguous", None)
        else:
            target[name] = entry


def _aggregate_shape(node: exp.Func, lineage: _Lineage | None = None) -> tuple[str, str | None]:
    """Classify an aggregate against W0 §3's ``<aggregation>(<field_id>)``.

    Returns ``(kind, column)``: *kind* is ``"exact"`` when the argument is
    the bare measure column (a value-preserving CAST around it aside), 
    ``"distinct"``/``"filtered"`` when a DISTINCT set or a FILTER clause
    changes what the aggregation computes, and ``"transformed"`` when the
    argument is any other expression (``sum(amount * 2)``,
    ``sum(CASE ...)``, ...). *column* is the argument's column name when it
    names one (set membership + diagnostics), else ``None``.

    The argument column is resolved through the read sources' *lineage*:
    ``sum(amount)`` over a CTE that exported ``amount * 2 AS amount`` is a
    transformed aggregate, not the bound measure (tester r26 B1).
    """

    arg = node.args.get("this")
    if isinstance(getattr(node, "parent", None), exp.Filter):
        kind = "filtered"
    elif isinstance(arg, exp.Distinct):
        inner = arg.expressions
        if len(inner) == 1 and isinstance(inner[0], exp.Column):
            return "distinct", inner[0].name.lower()
        kind = "transformed"
    else:
        inner = arg
        while isinstance(inner, _VALUE_PRESERVING_WRAPPERS):
            inner = inner.this
        if isinstance(inner, exp.Column):
            physical = _lineage_physical(inner.name.lower(), lineage)
            if physical is None:
                return "transformed", inner.name.lower()
            return "exact", physical
        kind = "transformed"
    column = None
    if isinstance(arg, exp.Expression):
        for inner in arg.find_all(exp.Column):
            column = inner.name.lower()
            break
    return kind, column


def _cte_map(statement: exp.Select, errors: list[str]) -> dict[str, exp.Select]:
    """``{cte_name: select}`` of the statement's WITH clause, if checkable."""

    with_clause = _select_arg(statement, "with")
    if with_clause is None:
        return {}
    if with_clause.args.get("recursive"):
        errors.append("recursive CTEs cannot be caliber-checked")
        return {}
    ctes: dict[str, exp.Select] = {}
    for cte in with_clause.expressions:
        name = cte.alias_or_name.lower()
        if not isinstance(cte.this, exp.Select):
            errors.append(f"CTE {name!r} is not a plain SELECT and cannot be caliber-checked")
            continue
        ctes[name] = cte.this
    return ctes


_GROUP_EXTENSIONS = (exp.Rollup, exp.Cube, exp.GroupingSets)


def _collect_caliber_scope(
    select: exp.Select,
    ctes: dict[str, exp.Select],
    scope: _CaliberScope,
    errors: list[str],
    depth: int = 0,
) -> _Lineage:
    """Accumulate one SELECT's binding facts, following its FROM sources.

    WHERE conjuncts, projection aggregates and GROUP BY columns of the result
    SELECT count; the same facts of a CTE or derived table the SELECT reads
    count too (its rows are exactly what the result aggregates). Subqueries
    that only produce scalars or EXISTS guards never count.

    Returns the *lineage* of the columns this SELECT exports: which of them
    are bare physical columns, which carry an aggregate (tester r25 — a
    scope that reads them may only project them as bare columns), and which
    a read source computed or renamed (tester r26 — such a column is not the
    bound ``field_id`` even when it shares its name).
    """

    if depth > _MAX_SCOPE_DEPTH:
        errors.append("CTE/derived-table nesting is too deep to caliber-check")
        return {}
    if depth and _select_arg(select, "with") is not None:
        errors.append("a WITH clause nested inside a CTE/derived table cannot be caliber-checked")
        return {}
    # tester r26 B1: HAVING, LIMIT/OFFSET and the grouping-set extensions
    # change which groups/rows are delivered without touching the bound
    # aggregate text, so they never carry the bound caliber.
    if _select_arg(select, "having") is not None:
        errors.append(
            "HAVING filters the aggregated groups and is not part of the bound "
            "caliber; restate the constraint as a WHERE conjunct before aggregation"
        )
    if _select_arg(select, "limit") is not None or _select_arg(select, "offset") is not None:
        errors.append(
            "LIMIT/OFFSET truncates the delivered rows outside the row budget; "
            "the executor applies the budget (07 §5.4)"
        )
    # tester r27 B1: QUALIFY is the same class of post-aggregation row filter
    # as HAVING — it picks which aggregated groups are delivered without
    # touching the bound text, so it never carries the caliber.
    if _select_arg(select, "qualify") is not None:
        errors.append(
            "QUALIFY filters the aggregated groups after aggregation (a "
            "HAVING/LIMIT-class group filter) and is not part of the bound caliber"
        )
    if _select_arg(select, "laterals"):
        errors.append("LATERAL cannot be caliber-checked")
        return {}
    # FROM first: the WHERE / GROUP BY / projection checks below need the
    # read sources' column lineage.
    lineage: _Lineage = {}
    sources: list[Any] = []
    joins = _select_arg(select, "joins") or []
    # tester r29 B1: a JOIN — inner/outer/semi, ON/USING/NATURAL or a comma
    # cross join — selects or multiplies the delivered rows in ways the
    # binding cannot verify: an ON conjunct is a WHERE in disguise
    # (``ON t.region = x.keep``, ``ON a.total > y.threshold``), an
    # equi-join's right side can fan the bound rows out by an unbounded
    # factor, and a subquery inside the ON re-reads the bound table outside
    # the read-once guard. Only the bound filters may select rows, so every
    # join is rejected (the join sources below are still counted for the
    # read-once diagnostics).
    for join in joins:
        if join.args.get("natural"):
            errors.append(
                "a NATURAL JOIN matches rows on implicit shared columns and cannot "
                "be caliber-checked; only the bound filters may select rows"
            )
            continue
        kind = (
            " ".join(part for part in (join.args.get("side"), join.args.get("kind")) if part)
            or "JOIN"
        )
        if join.args.get("using"):
            errors.append(
                f"a {kind} with USING matches rows on the shared column(s) and cannot "
                "be caliber-checked; restate any constraint as a bound WHERE conjunct"
            )
        elif join.args.get("on") is not None:
            errors.append(
                f"the {kind} ON condition selects or multiplies the delivered rows "
                "outside the bound caliber (an ON conjunct is a WHERE in disguise, and "
                "an ON subquery re-reads the sources outside the read-once guard); "
                "restate the constraint as a bound WHERE conjunct"
            )
        else:
            errors.append(
                f"a {kind} without a verifiable condition multiplies the delivered "
                "rows by an unbounded right side and is not part of the bound caliber"
            )
    # tester r29 B2: DuckDB's select-level sampler drops rows before the
    # bound aggregate (``USING SAMPLE 1 PERCENT``).
    if _select_arg(select, "sample") is not None:
        errors.append(
            "USING SAMPLE samples the rows before the bound aggregation and is not "
            "part of the bound caliber"
        )
    from_clause = _select_arg(select, "from")
    if from_clause is not None:
        sources.append(from_clause.this)
    sources.extend(join.args.get("this") for join in joins)
    for source in sources:
        if source is None:
            errors.append("the SQL uses a FROM shape that cannot be caliber-checked")
        elif isinstance(source, exp.Table):
            if source.args.get("sample") is not None:
                # tester r29 B2: a table-level sampler (``FROM t TABLESAMPLE
                # 1 PERCENT``) drops rows the bound aggregate should have read.
                errors.append(
                    "TABLESAMPLE samples the rows the bound aggregation reads and is "
                    "not part of the bound caliber"
                )
            name = source.name.lower()
            if name in ctes:
                scope.cte_refs[name] = scope.cte_refs.get(name, 0) + 1
                _merge_lineage(
                    lineage,
                    _collect_caliber_scope(ctes[name], ctes, scope, errors, depth + 1),
                )
            else:
                scope.table_refs[name] = scope.table_refs.get(name, 0) + 1
        elif isinstance(source, exp.Subquery) and isinstance(source.this, exp.Select):
            _merge_lineage(
                lineage,
                _collect_caliber_scope(source.this, ctes, scope, errors, depth + 1),
            )
        else:
            errors.append(
                "the SQL reads a FROM source that cannot be caliber-checked: "
                f"{source.sql()[:48]!r}"
            )
    where = _select_arg(select, "where")
    if where is not None:
        _collect_conjunctive(where.this, scope.predicates, lineage)
        # tester r27 B1: record *every* conjunct so the checker can reject
        # filters outside the bound ones; columns inside subquery barriers
        # (EXISTS / scalar subqueries) never count — they are not of this
        # scope.
        for conjunct in _iter_where_conjuncts(where.this):
            columns: set[str] = set()
            for node in _iter_scope(conjunct):
                if isinstance(node, exp.Column):
                    raw = node.name.lower()
                    physical = _lineage_physical(raw, lineage)
                    columns.add(
                        physical if physical is not None else "#derived:" + raw
                    )
            scope.where_conjuncts.append(
                (
                    frozenset(columns),
                    _bounds_physical_column(conjunct),
                    conjunct.sql(dialect=SQL_DIALECT)[:48],
                )
            )
        for node in _iter_scope(where.this):
            if isinstance(node, exp.Column):
                physical = _lineage_physical(node.name.lower(), lineage)
                if physical is not None:
                    scope.where_columns.add(physical)
    group = _select_arg(select, "group")
    if group is not None:
        for node in _iter_scope(group):
            if isinstance(node, _GROUP_EXTENSIONS) or any(
                group.args.get(modifier) for modifier in ("rollup", "cube", "totals")
            ):
                errors.append(
                    "GROUP BY ROLLUP/CUBE/GROUPING SETS adds subtotal/grand-total "
                    "rows and changes the bound grain"
                )
                break
        for node in _iter_scope(group):
            if isinstance(node, exp.Column):
                name = node.name.lower()
                physical = _lineage_physical(name, lineage)
                if physical is None:
                    errors.append(
                        f"GROUP BY uses the derived column {name!r}; group by the "
                        "bound dimension column itself"
                    )
                    scope.group_columns.add("#derived:" + name)
                else:
                    scope.group_columns.add(physical)
    exported: _Lineage = {}
    for projection in select.expressions:
        if isinstance(projection, exp.Star):
            if any(projection.args.get(key) for key in ("except", "replace", "rename")):
                errors.append(
                    "SELECT * with EXCEPT/REPLACE/RENAME changes the exported columns "
                    "and cannot be caliber-checked"
                )
            continue  # a plain * passes the physical columns through unchanged
        aggregates_here: list[exp.Func] = []
        exact_entry: tuple[str, str] | None = None
        for node in _iter_scope(projection):
            if not isinstance(node, exp.Func):
                continue
            func = _AGG_FUNCS.get(type(node).__name__.lower())
            if func is None:
                continue
            aggregates_here.append(node)
            kind, column = _aggregate_shape(node, lineage)
            entry = (func, column if column is not None else "*")
            if kind == "exact":
                exact_entry = entry
            {
                "exact": scope.aggregates,
                "distinct": scope.distinct_aggregates,
                "filtered": scope.filtered_aggregates,
                "transformed": scope.transformed_aggregates,
            }[kind].add(entry)
        carries = {
            node.name.lower() for node in _iter_scope(projection) if isinstance(node, exp.Column)
        } & {name for name, entry in lineage.items() if entry[0] == "agg"}
        if not (aggregates_here or carries):
            # A plain column projection: export its (resolved) lineage.
            expr = projection.this if isinstance(projection, exp.Alias) else projection
            while isinstance(expr, _VALUE_PRESERVING_WRAPPERS):
                expr = expr.this
            if isinstance(expr, exp.Column):
                name = expr.name.lower()
                export_name = (
                    projection.alias_or_name.lower()
                    if isinstance(projection, exp.Alias)
                    else name
                )
                entry = lineage.get(name)
                exported[export_name] = entry if entry is not None else ("column", name)
            elif isinstance(projection, exp.Alias):
                # a computed/renamed export: the name no longer stands for
                # the physical column (tester r26 B1)
                exported[projection.alias_or_name.lower()] = ("expr", expr)
            continue
        # W0 §3 / tester r25: a projection that holds an aggregate — or reads a
        # column a read source computed by aggregating — must deliver it
        # untouched: the aggregate itself (value-preserving CAST aside) or the
        # bare column. Arithmetic around the aggregate delivers a different
        # number under the metric's version.
        expr = projection.this if isinstance(projection, exp.Alias) else projection
        while isinstance(expr, _VALUE_PRESERVING_WRAPPERS):
            expr = expr.this
        if isinstance(expr, exp.Column):
            if isinstance(projection, exp.Alias):
                entry = lineage.get(expr.name.lower())
                exported[projection.alias_or_name.lower()] = (
                    entry if entry is not None else ("column", expr.name.lower())
                )
            continue
        if any(expr is node for node in aggregates_here):
            if isinstance(projection, exp.Alias) and exact_entry is not None:
                exported[projection.alias_or_name.lower()] = ("agg", exact_entry)
            continue
        if carries:
            errors.append(
                "a projection transforms the aggregated column(s) "
                f"{sorted(carries)} outside their aggregation; an aggregated column "
                "may only be projected as itself (value-preserving CAST aside)"
            )
        else:
            errors.append(
                "a projection transforms its aggregate outside the aggregation "
                f"({expr.sql(dialect=SQL_DIALECT)[:48]!r}); the projection must be "
                "the bound aggregation itself (value-preserving CAST aside)"
            )
    return exported


_DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _time_key(value: Any) -> str | None:
    """Comparable date key of a bound time endpoint or a SQL literal.

    The bound ``TimeRange`` endpoints are aware datetimes; the SQL states
    date (or datetime) literals. Both sides reduce to their ``YYYY-MM-DD``
    prefix, so ``'2026-01-01'`` binds ``2026-01-01T00:00:00+00:00``.
    """

    if isinstance(value, datetime):
        text = value.isoformat()
    elif isinstance(value, (str, int, float)) and not isinstance(value, bool):
        text = str(value)
    else:
        return None
    text = text.strip().translate(_QUOTE_FOLD)
    if len(text) >= 2 and text[0] in "'\"" and text[-1] == text[0]:
        text = text[1:-1]
    match = _DATE_PREFIX.match(text)
    return match.group(0) if match else text.lower()


_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _prev_date_key(key: str) -> str | None:
    """``<date - 1 day>`` of a ``YYYY-MM-DD`` key; ``None`` for anything else."""

    if not _DATE_ONLY.match(key):
        return None
    try:
        return (date.fromisoformat(key) - timedelta(days=1)).isoformat()
    except ValueError:
        return None


def _literal_value(node: Any) -> Any:
    """Python value of a sqlglot literal leaf; ``None`` when not a literal."""

    if isinstance(node, exp.Boolean):
        return bool(node.this)
    if isinstance(node, exp.Literal):
        if node.is_string:
            return node.this
        try:
            return int(node.this) if "." not in node.this else float(node.this)
        except ValueError:
            return node.this
    if isinstance(node, exp.Neg):
        inner = _literal_value(node.this)
        return -inner if isinstance(inner, (int, float)) else None
    return None


def sql_caliber_errors(
    sql: str,
    requirement: RequirementSpec,
    metrics: list[SemanticDraft],
    table_name: str | None = None,
) -> list[str]:
    """Deterministic caliber binding of a proposed SQL (07 §5, review §5).

    A bound requirement pins, per metric: the measure column, the
    aggregation, the fixed filters *including their operator and constant*,
    and the bound dimensions/grain. A SQL that parses, uses the bound
    table and no blacklisted function but computes a different measure,
    flips a fixed filter's value, drops a bound dimension or groups by a
    non-bound column is rejected — "SQL correct, caliber wrong" must not
    pass with the metric's version attached.

    Binding is *scope-aware* (tester r24 B1): only the WHERE conjuncts,
    projection aggregates and GROUP BY of the SELECT that produces the
    result — plus the CTE / derived-table chain it reads — carry the
    caliber. Predicates in an unused CTE, an EXISTS or a scalar subquery
    bind nothing, and with ``table_name`` the bound table may be read only
    once (no self-joins: they change row multiplicity).

    Binding is also *aggregate-shape-aware* (W0 §3 / tester r25 B1): the
    aggregation must be ``<aggregation>(<measure field_id>)`` — the bare
    measure column (value-preserving CAST aside), DISTINCT/FILTER-free —
    and a projection may only deliver it as the aggregate itself
    (value-preserving CAST aside), or as a bare column when a read
    CTE/derived table already computed it. ``sum(amount * 2)``,
    ``sum(amount) FILTER (...)``, ``sum(amount) * 2`` and scaling an
    aggregated column in an outer SELECT are all rejected.

    Binding is *column-lineage-aware* (tester r26 B1): a CTE/derived-table
    column only carries the caliber when it is the bare passthrough of the
    bound column — ``amount * 2 AS amount`` makes an outer ``sum(amount)``
    a transformed aggregate, and a predicate on a derived filter/time
    column binds nothing. HAVING, LIMIT/OFFSET and
    ROLLUP/CUBE/GROUPING SETS change the delivered groups/rows without
    touching the bound text and are rejected; a second predicate on the
    bound time field or on a fixed-filter column (``approved = true AND
    approved = false``) neutralizes the bound caliber and is rejected too.
    ``BETWEEN`` is accepted as the equivalent expansion of the bound window
    (``>= low AND <= high``, with ``<= <to - 1 day>`` the date-granularity
    equivalent of the exclusive bound ``to``).

    Binding is *conjunct-closed* (tester r27 B1): only the bound filters
    may select the delivered rows. QUALIFY is a HAVING/LIMIT-class group
    filter and is rejected; every WHERE conjunct must be a recognized
    predicate on a bound time/filter column — a dimension or measure
    filter (``region = 'north'``, ``amount > 150``, an IN list), a
    predicate on a CTE/derived-table column (a post-aggregation WHERE is a
    HAVING in disguise) or a column-less constant (``1 = 0``) narrows the
    caliber and is rejected.

    Binding is *join/sample-closed* (tester r29 B1/B2): every JOIN —
    inner/outer/semi, ON/USING/NATURAL or a comma cross join — and every
    sampler (``TABLESAMPLE`` on a source, ``USING SAMPLE`` on the select)
    selects or multiplies rows in ways the bound predicates cannot verify
    (an ON conjunct is a WHERE in disguise, an ON subquery re-reads the
    bound table outside the read-once guard, a right side fans rows out,
    a sampler drops them) and is rejected.
    """

    errors: list[str] = []
    try:
        statement = sqlglot_parse(sql, dialect=SQL_DIALECT)[0]
    except Exception:  # noqa: BLE001 - syntax was validated before
        return ["SQL does not parse; run the syntax validation first"]
    if not isinstance(statement, exp.Select):
        return ["SQL does not parse; run the syntax validation first"]

    scope = _CaliberScope()
    _collect_caliber_scope(statement, _cte_map(statement, errors), scope, errors)

    # Row-multiplicity guard: the bound table (and every CTE) may be read
    # only once — a self-join (``JOIN t x ON true``) multiplies the rows the
    # result aggregates, and a second read of the table opens scoping
    # smuggling even when its predicates are unused (tester r24 B1).
    if table_name is not None:
        bound = table_name.lower()
        reads = scope.table_refs.get(bound, 0)
        if reads == 0:
            errors.append(
                f"the SQL does not read the bound table {table_name!r} in its FROM clause"
            )
        elif reads > 1:
            errors.append(
                f"the bound table {table_name!r} is read {reads} times; self-joins and "
                "duplicate reads change row multiplicity and are not allowed"
            )
    for cte_name, count in sorted(scope.cte_refs.items()):
        if count > 1:
            errors.append(
                f"CTE {cte_name!r} is read {count} times; joining a CTE with itself "
                "multiplies rows and is not allowed"
            )

    by_id = {d.draft_id: d for d in metrics}
    aggregates = scope.aggregates
    distinct_aggregates = scope.distinct_aggregates
    filtered_aggregates = scope.filtered_aggregates
    transformed_aggregates = scope.transformed_aggregates
    where_columns = scope.where_columns
    where_predicates = scope.predicates

    time_fields: set[str] = set()
    for ref in requirement.metrics:
        draft = by_id.get(ref.id)
        if draft is None:
            continue
        measure = draft.definition.measure
        expected = (measure.aggregation.lower(), measure.field_ref.lower())
        if expected not in aggregates:
            if expected in distinct_aggregates:
                errors.append(
                    f"metric {ref.id}: DISTINCT changes the semantics of "
                    f"{measure.aggregation!r} on {measure.field_ref!r}; the bound "
                    "aggregation has no DISTINCT"
                )
            elif expected in filtered_aggregates:
                errors.append(
                    f"metric {ref.id}: a FILTER clause changes the rows "
                    f"{measure.aggregation!r} aggregates on {measure.field_ref!r}; "
                    "the bound aggregation has no FILTER"
                )
            elif expected in transformed_aggregates:
                errors.append(
                    f"metric {ref.id}: the {measure.aggregation!r} argument is not the "
                    f"bare measure column {measure.field_ref!r}; the aggregation must "
                    f"be {measure.aggregation}({measure.field_ref}) "
                    "(value-preserving CAST aside)"
                )
            else:
                errors.append(
                    f"metric {ref.id}: SQL must aggregate {measure.field_ref!r} with "
                    f"{measure.aggregation!r} (found aggregates: {sorted(aggregates) or 'none'})"
                )
        if draft.definition.time and draft.definition.time.time_field:
            time_fields.add(draft.definition.time.time_field.lower())
    time_field = sorted(time_fields)[0] if len(time_fields) == 1 else None
    if requirement.time is not None and time_field and time_field not in where_columns:
        errors.append(
            "the bound time range is not applied (no WHERE "
            f"constraint on the time field {time_field!r})"
        )
    # The bound time range must actually pin the time field's window (tester
    # r22 B1): the WHERE has to constrain the start and the end with the
    # bound values — a column that merely appears (``occurred_on IS NOT
    # NULL``) or is filtered on a different window (2020 instead of 2026)
    # does not carry the caliber. The window is half-open, ``>= from`` and
    # ``< to`` (07 §5.2); ``BETWEEN 'a' AND 'b'`` is the equivalent expansion
    # of ``>= a AND <= b``, so it is only equivalent when ``b`` is
    # ``<to - 1 day>``. Exactly one operator/value pair is accepted per
    # endpoint (tester r32 B1): ``> from`` drops the inclusive start row and
    # ``<= to`` keeps the exclusive end row, so neither may carry the
    # metric's version — with a boundary row present they deliver a different
    # total than the bound window under the same metric version.
    if requirement.time is not None and time_field and time_field in where_columns:
        bound_time = where_predicates.get(time_field, set())
        accepted_time: set[tuple[str, str]] = set()
        for endpoint, ops, label, prev_op in (
            (requirement.time.from_, ("ge",), "start", "gt"),
            (requirement.time.to, ("lt",), "end", "le"),
        ):
            expected_key = _time_key(endpoint)
            if expected_key is None:
                continue
            endpoint_accepted = {(op, expected_key) for op in ops}
            previous = _prev_date_key(expected_key)
            if previous is not None:
                endpoint_accepted.add((prev_op, previous))
            accepted_time |= endpoint_accepted
            if not any(p in endpoint_accepted for p in bound_time):
                stated = ", ".join(
                    f"{op} {value!r}" for op, value in sorted(bound_time)
                )
                errors.append(
                    f"the bound time range is not applied on {time_field!r}: the "
                    f"{label} {expected_key!r} is not constrained (WHERE states: "
                    f"{stated or 'no comparison on that column'})"
                )
        # tester r26 B1: a *second* predicate on the bound time field can
        # neutralize or narrow the window even when both bound endpoints
        # appear verbatim (``AND occurred_on >= '2030-01-01'``); only the
        # bound endpoints may constrain the time field.
        extra_time = bound_time - accepted_time
        if extra_time:
            stated = ", ".join(f"{op} {value!r}" for op, value in sorted(extra_time))
            errors.append(
                f"extra predicate(s) on the bound time field {time_field!r} narrow or "
                f"neutralize the bound window (only the bound endpoints may constrain "
                f"it; extra: {stated})"
            )

    # Bound dimensions / grain: every bound dimension must be grouped, and no
    # column outside the bound grain (dimensions + the time field) may be
    # grouped (review §5 / tester r20 B2).
    group_columns = scope.group_columns
    allowed_group = {dim.lower() for dim in requirement.dimensions} | time_fields
    if requirement.dimensions:
        missing = {dim.lower() for dim in requirement.dimensions} - group_columns
        if missing:
            errors.append(
                "the bound dimensions are not grouped (grain "
                f"{requirement.grain!r} requires GROUP BY {sorted(missing)})"
            )
    extra = group_columns - allowed_group
    if extra:
        errors.append(
            "SQL groups by column(s) outside the bound grain: "
            f"{sorted(extra)} (bound dimensions: {sorted(requirement.dimensions)})"
        )

    # Fixed filters: the field, the operator and the constant must match
    # (review §5 / tester r20 B2 — presence of the column is not enough).
    allowed_filter: dict[str, set[tuple[str, str | None]]] = {}
    for item in requirement.filters:
        predicate = _FILTER_PREDICATE.match(item.text)
        if predicate is None:
            continue  # free-form text: the presence check below is all we can bind
        bound = (
            _OP_NAMES[predicate.group("op")],
            _normalize_filter_value(predicate.group("value")),
        )
        for field_id in item.referenced_fields:
            allowed_filter.setdefault(field_id.lower(), set()).add(bound)
    for item in requirement.filters:
        for field_id in item.referenced_fields:
            column = field_id.lower()
            if column not in where_columns:
                errors.append(
                    f"fixed filter {item.text!r} on {field_id!r} is not applied in the SQL"
                )
                continue
            predicate = _FILTER_PREDICATE.match(item.text)
            if predicate is None:
                continue  # free-form text: the presence check above is all we can bind
            bound = (
                _OP_NAMES[predicate.group("op")],
                _normalize_filter_value(predicate.group("value")),
            )
            if bound[1] is not None and bound not in where_predicates.get(column, set()):
                stated = ", ".join(
                    f"{op} {value!r}" for op, value in sorted(where_predicates.get(column, set()))
                )
                errors.append(
                    f"fixed filter {item.text!r} on {field_id!r} is not applied with the "
                    f"bound operator/value (WHERE states: {stated or 'nothing on that column'})"
                )
    # tester r26 B1: a second predicate on a fixed-filter column can
    # neutralize the bound value (``approved = true AND approved = false``)
    # even though the bound predicate appears verbatim; only the bound
    # operator/value pairs may constrain a fixed-filter column.
    for column, allowed in sorted(allowed_filter.items()):
        if column in where_columns:
            extra = where_predicates.get(column, set()) - allowed
            if extra:
                stated = ", ".join(f"{op} {value!r}" for op, value in sorted(extra))
                errors.append(
                    f"extra predicate(s) on the fixed-filter column {column!r} narrow or "
                    f"neutralize the bound filter (only the bound operator/value may "
                    f"constrain it; extra: {stated})"
                )
    # tester r27 B1: the bound caliber is the full set of rows the bound
    # filters select, so *only* those filters may select rows. Every WHERE
    # conjunct — of the result SELECT or a CTE/derived table it reads — must
    # be a recognized predicate on a bound time/filter column; anything
    # else narrows the delivered result under the metric's version.
    allowed_where = set(allowed_filter) | time_fields
    for columns, bounds_physical, snippet in scope.where_conjuncts:
        derived = sorted(c.split(":", 1)[1] for c in columns if c.startswith("#derived:"))
        if derived:
            errors.append(
                "a WHERE conjunct filters the derived/aggregated column(s) "
                f"{derived} ({snippet!r}); a post-aggregation WHERE is a HAVING in "
                "disguise and is not part of the bound caliber"
            )
            continue
        if not columns:
            errors.append(
                f"a WHERE conjunct filters rows without referencing a column "
                f"({snippet!r}); a constant conjunct is the equivalent of LIMIT 0 "
                "and is not part of the bound caliber"
            )
            continue
        extra = sorted(columns - allowed_where)
        if extra:
            errors.append(
                "extra WHERE filter(s) on column(s) outside the bound filters "
                f"narrow the caliber: {extra} ({snippet!r}); only the bound time "
                "window and fixed filters may filter rows"
            )
            continue
        if not bounds_physical:
            errors.append(
                f"the WHERE conjunct {snippet!r} constrains the bound column(s) "
                f"{sorted(columns)} with a form the binding cannot check; only the "
                "bound time-window endpoints and fixed-filter operator/value "
                "predicates may constrain them"
            )
    return errors


@operation(
    "DA06.3.1",
    input_model=GenerateSingleTableSqlInput,
    output_model=GenerateSingleTableSqlOutput,
    description="单表 SQL 生成（两段式）：sqlglot 校验单条 SELECT、绑定表与函数黑名单；绑定口径后校验度量列、聚合与固定过滤（DA06.3.1）",
)
def generate_single_table_sql(
    data: GenerateSingleTableSqlInput, ctx: CallContext, runtime
) -> CapabilityResult[GenerateSingleTableSqlOutput]:
    from dataagent_contracts.core import TableRef

    table_ref = TableRef.model_validate(data.table_ref)
    table = helpers.load_table(runtime, table_ref)
    table_name = _sql_table_name(table_ref)
    metric_drafts = [SemanticDraft.model_validate(item) for item in data.metrics]
    for draft in metric_drafts:
        if draft.kind != "metric":
            raise invalid_input(
                f"metrics[] must be kind=metric SemanticDrafts, got kind={draft.kind!r}",
                target="metrics",
            )
    metric_statements = [d.definition.statement for d in metric_drafts]
    if data.proposal is None:
        requirement = (
            RequirementSpec.model_validate(data.requirement) if data.requirement else None
        )
        # r40 F1b: every caller-supplied model-visible text in the request is
        # cited *by content address*, so the EgressDecision must cover those
        # bytes — a table-only decision no longer vouches for the caller's
        # statement/metrics/requirement. The ``table`` section is rebuilt from
        # the bound table asset, which the table ref already covers.
        statement = data.statement or (requirement.statement if requirement else None)
        metric_filters = {
            d.draft_id: [f.text for f in (d.definition.filters or [])] for d in metric_drafts
        }
        requirement_view = requirement.model_dump(mode="json") if requirement else None
        caller_refs: list[VersionedRef] = []
        if statement is not None:
            caller_refs.append(helpers.caller_content_ref(statement))
        if metric_statements:
            caller_refs.append(helpers.caller_content_ref(metric_statements))
        if metric_filters:
            caller_refs.append(helpers.caller_content_ref(metric_filters))
        if requirement_view is not None:
            caller_refs.append(helpers.caller_content_ref(requirement_view))
        request = {
            "kind": "single_table_sql",
            "statement": statement,
            "table": {
                "sql_name": table_name,
                "columns": table.schema_fields(),
                "row_identity": table_ref.row_identity,
            },
            "metrics": metric_statements,
            "metric_filters": metric_filters,
            "requirement": requirement_view,
            "dialect": SQL_DIALECT,
            "constraints": [
                "exactly one SELECT statement (CTEs allowed)",
                f"only the bound table may be referenced (as {table_name}), exactly once (no self-joins)",
                "no file/extension/network functions (read_*, COPY, ATTACH, INSTALL, ...)",
                "aggregate each bound metric's measure column with its declared aggregation as <aggregation>(<measure field_id>) — bare column argument (value-preserving CAST aside), no DISTINCT/FILTER, no arithmetic inside or around the aggregate; a CTE/derived-table column may only stand in for the bound column when it selects it unchanged",
                "apply every fixed filter of the bound metrics (metric_filters / requirement.filters) as unconditional WHERE conjuncts of the main query (or the CTE chain it reads), and make the WHERE conjuncts exactly the bound filters and time-window endpoints: no other predicate on any column (dimension, measure, derived or aggregated), no IN/LIKE/IS filters on the bound columns, no constant conjunct (e.g. 1 = 0)",
                "no HAVING or QUALIFY (they filter the aggregated groups; restate group filters as WHERE conjuncts before aggregation), no LIMIT/OFFSET (the executor applies the row budget), no GROUP BY ROLLUP/CUBE/GROUPING SETS (they add subtotal rows outside the bound grain)",
                "no JOIN of any kind (inner/outer/semi, ON/USING/NATURAL or comma cross join — an ON conjunct is a WHERE in disguise and a join fans rows out; the bound table is read exactly once) and no row sampler (TABLESAMPLE / USING SAMPLE drops rows before the bound aggregation)",
                "the bound time window is half-open: constrain the time field with >= from and < to (date-granularity equivalents: > <from - 1 day> and <= <to - 1 day>); > from drops the inclusive start row and <= to keeps the exclusive end row, so neither carries the caliber",
            ],
            "instruction": (
                "Produce a single SELECT over the bound table that computes the requested "
                "metrics at the requested grain with the requested filters."
            ),
        }
        content_refs = [
            VersionedRef(id=table_ref.asset.id, revision=table_ref.asset.revision)
        ] + caller_refs
        request, gate_issues, allowed = helpers.gate_inference_request(
            runtime,
            request,
            data.egress_decision_ref,
            content_refs=content_refs,
            check=egress_check,
            destination=data.destination,
        )
        if allowed:
            issues = [
                Issue(
                    code="da06.inference_required",
                    severity=Severity.info,
                    message="agent-provided SQL is required",
                    retryable=False,
                    suggested_action="replay with a proposal {sql}",
                    inference_request=request,
                )
            ] + gate_issues
        else:
            issues = [
                issue.model_copy(update={"inference_request": request})
                for issue in gate_issues
            ]
        return CapabilityResult[GenerateSingleTableSqlOutput](
            status=CapabilityStatus.needs_input,
            data=None,
            issues=issues,
            completeness=helpers.complete("single-table SQL generation"),
        )

    sql = data.proposal.get("sql")
    if not isinstance(sql, str) or not sql.strip():
        raise invalid_input("proposal.sql must be a non-empty string", target="proposal.sql")
    errors = validate_single_select_sql(sql, {table_name})
    if errors:
        raise invalid_input(
            "SQL validation failed: " + "; ".join(errors), target="proposal.sql"
        )
    # Caliber binding against the bound requirement (B4): same table, right
    # measure, right aggregation, fixed filters applied.
    if data.requirement is not None:
        requirement = RequirementSpec.model_validate(data.requirement)
        caliber_errors = sql_caliber_errors(sql, requirement, metric_drafts, table_name=table_name)
        if caliber_errors:
            return CapabilityResult[GenerateSingleTableSqlOutput](
                status=CapabilityStatus.failed,
                data=None,
                issues=[
                    Issue(
                        code="da06.sql_caliber_mismatch",
                        severity=Severity.error,
                        message="SQL caliber check failed: " + "; ".join(caliber_errors),
                        retryable=False,
                        suggested_action="aggregate the bound measure with the declared aggregation and apply every fixed filter",
                    )
                ],
            )
    import duckdb

    spec = ExecutableSpec(
        spec_id=f"sql:{sql_digest(sql).split(':', 1)[1][:16]}",
        revision="r1",
        backend_kind="sql",
        expression_or_call={"sql": sql, "dialect": SQL_DIALECT},
        source_refs=[VersionedRef(id=table_ref.asset.id, revision=table_ref.asset.revision)],
        engine_binding=EngineBinding(
            engine_id=SQL_ENGINE_ID, engine_version=duckdb.__version__
        ),
    )
    return CapabilityResult[GenerateSingleTableSqlOutput](
        status=CapabilityStatus.ok,
        data=GenerateSingleTableSqlOutput(spec=spec, table_name=table_name),
        completeness=helpers.complete("single-table SQL generation"),
    )
