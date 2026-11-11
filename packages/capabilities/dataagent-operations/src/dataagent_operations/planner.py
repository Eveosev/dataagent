"""Validate workflow graphs, references, and API request bindings."""

from collections import defaultdict, deque
import re

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing import Registry

from dataagent_contracts.workflow import ReadStep, VerificationRequirement

from .bindings import encode

MISSING = object()


def at(value, pointer, default=MISSING):
    for token in pointer.split("/")[1:]:
        key = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict):
            value = value.get(key, MISSING)
        elif isinstance(value, list) and re.fullmatch(r"0|[1-9][0-9]*", key) and len(key) < 10:
            index = int(key)
            value = value[index] if index < len(value) else MISSING
        else:
            value = MISSING
        if value is MISSING:
            if default is MISSING:
                raise ValueError(f"no value at {pointer!r}")
            return default
    return value


def same(left, right):
    return encode(left) == encode(right)


def matches(predicate, value):
    if predicate is None:
        return False
    try:
        selected = at(value, predicate.pointer)
    except ValueError:
        return False
    return any(same(selected, candidate) for candidate in predicate.one_of)


def reference(value):
    if isinstance(value, dict) and "$ref" in value:
        if set(value) != {"$ref"} or not isinstance(value["$ref"], str):
            raise ValueError("value references must contain a single JSON pointer")
        path = value["$ref"]
        if not re.fullmatch(r"(/([^~]|~[01])*)+", path):
            raise ValueError(f"invalid reference pointer {path!r}")
        return path
    return None


def references(value):
    path = reference(value)
    if path:
        yield path
    elif isinstance(value, dict):
        for child in value.values():
            yield from references(child)
    elif isinstance(value, list):
        for child in value:
            yield from references(child)


def resolve(value, context):
    path = reference(value)
    if path:
        return at(context, path)
    if isinstance(value, dict):
        return {key: resolve(child, context) for key, child in value.items()}
    if isinstance(value, list):
        return [resolve(child, context) for child in value]
    return value


def check_schema(schema):
    """Only self-contained JSON schemas are accepted from Agent or API."""

    def local_refs(value):
        if isinstance(value, list):
            for child in value:
                local_refs(child)
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"$ref", "$dynamicRef"} and (
                    not isinstance(child, str) or not child.startswith("#/")
                ):
                    raise ValueError("JSON schema references must be local JSON pointers")
                if key in {"$id", "$schema"}:
                    raise ValueError("JSON schema resource identifiers and dialect overrides are unsupported")
                local_refs(child)

    local_refs(schema)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ValueError(f"invalid JSON schema: {exc.message}") from exc


def validate_value(value, schema):
    validator = Draft202012Validator(schema, registry=Registry())
    try:
        error = next(validator.iter_errors(value), None)
    except Exception as exc:
        raise ValueError(f"unsupported JSON schema constraint: {type(exc).__name__}") from exc
    if error:
        position = "/".join(str(key) for key in error.absolute_path)
        raise ValueError(f"{position or '/'}: {error.message}")


def validate_template(template, schema):
    if reference(template):
        return
    if not any(references(template)):
        validate_value(template, schema)
        return
    if isinstance(template, dict) and schema.get("type") == "object":
        properties = schema.get("properties", {})
        missing = set(schema.get("required", [])) - template.keys()
        if missing:
            raise ValueError(f"missing required fields: {', '.join(sorted(missing))}")
        for name, value in template.items():
            selected = properties.get(name, schema.get("additionalProperties", {}))
            if selected is False:
                raise ValueError(f"unexpected request field {name!r}")
            if isinstance(selected, dict):
                try:
                    validate_template(value, selected)
                except ValueError as exc:
                    raise ValueError(f"{name}: {exc}") from exc
    elif isinstance(template, list) and isinstance(schema.get("items"), dict):
        for value in template:
            validate_template(value, schema["items"])


def managed_parameters(policy):
    managed = defaultdict(dict)
    if policy.business_key_parameter:
        managed["query"][policy.business_key_parameter] = "business_key"
    if policy.record_id_parameter:
        managed["path"][policy.record_id_parameter] = "record_id"
    if policy.effect:
        effect = policy.effect
        if effect.business_key_field:
            managed["body"][effect.business_key_field] = "business_key"
        if effect.request_key_field:
            managed["body"][effect.request_key_field] = "request_key"
        if effect.record_id_parameter:
            managed["path"][effect.record_id_parameter] = "record_id"
    return managed


def validate_parameters(arguments, observation, policy, *, template=False):
    validate = validate_template if template else validate_value
    managed = managed_parameters(policy)
    for location in ("path", "query"):
        entries = arguments[location]
        schema = observation.parameters.get(location, {})
        if template and managed[location].keys() & entries.keys():
            raise ValueError(f"workflow cannot override host-managed {location} parameters")
        provided = entries.keys() | (managed[location].keys() if template else set())
        unknown = provided - schema.keys()
        if unknown:
            raise ValueError(f"undocumented {location} parameters: {', '.join(sorted(unknown))}")
        missing = set(observation.required_parameters.get(location, [])) - provided
        if missing:
            raise ValueError(f"missing required {location} parameters: {', '.join(sorted(missing))}")
        for name, value in entries.items():
            validate(value, schema[name])
    body = arguments["body"].copy()
    if template:
        if body.keys() & managed["body"].keys():
            raise ValueError("workflow cannot override host-managed body fields")
        body.update({name: {"$ref": "/business_key"} for name in managed["body"]})
    if observation.request_schema is not None:
        if body or observation.request_required:
            validate(body, observation.request_schema)
    elif body:
        raise ValueError("undocumented JSON body")


def validate_spec(spec, work, snapshot, environment):
    check_schema(spec.input_schema)
    if spec.input_schema.get("type") != "object":
        raise ValueError("workflow input_schema must describe an object")
    nodes = {node.id: node for node in spec.nodes}
    if len(nodes) != len(spec.nodes) or spec.entry not in nodes:
        raise ValueError("workflow needs unique step IDs and an existing entry step")
    children = {}
    parents = defaultdict(set)
    for node in spec.nodes:
        branches = [node.next] if node.next else []
        if node.kind == "decide":
            if not node.next or node.next == node.otherwise:
                raise ValueError(f"{node.id}: decision needs two distinct successors")
            branches.append(node.otherwise)
        if not branches and node.kind != "verify":
            raise ValueError(f"{node.id}: terminal step must verify actual business state")
        if any(branch not in nodes for branch in branches):
            raise ValueError(f"{node.id}: unknown successor")
        children[node.id] = branches
        for branch in branches:
            parents[branch].add(node.id)

    if parents[spec.entry]:
        raise ValueError("entry step cannot have a predecessor")
    queue = deque([spec.entry])
    before = {}
    remaining = {key: len(value) for key, value in parents.items()}
    while queue:
        step = queue.popleft()
        parent_steps = parents[step]
        before[step] = set.intersection(*(before[p] | {p} for p in parent_steps)) if parent_steps else set()
        for branch in children[step]:
            remaining[branch] -= 1
            if remaining[branch] == 0:
                queue.append(branch)
    if len(before) != len(nodes):
        raise ValueError("all steps must be reachable through an acyclic workflow")

    criteria = set(range(len(work.acceptance_criteria)))
    raw_checks = work.constraints.get("workflow_verification")
    checks = []
    if raw_checks is not None:
        if not isinstance(raw_checks, list) or not raw_checks:
            raise ValueError("trusted workflow_verification must be a nonempty list")
        checks = [VerificationRequirement.model_validate(raw) for raw in raw_checks]
    for node in spec.nodes:
        if isinstance(node, ReadStep):
            operation = environment.operations.get(node.operation_id)
            observed = snapshot.capabilities.get(node.operation_id)
            if operation is None or observed is None or not observed.authorized:
                raise ValueError(f"{node.id}: operation {node.operation_id!r} is outside the validated environment scope")
            if (node.kind == "act") != (operation.effect is not None):
                raise ValueError(f"{node.id}: incompatible API method for {node.kind}")
            lookup_id = operation.effect.lookup_operation if operation.effect else operation.record_lookup
            if lookup_id:
                lookup = snapshot.capabilities.get(lookup_id)
                collection = operation.effect.collection_pointer if operation.effect else operation.collection_pointer
                evidence = (lookup.evidence or {}) if lookup is not None else {}
                if collection not in evidence.get("lookup_collections", []):
                    raise ValueError(f"{node.id}: no observed business-key lookup collection at {collection!r}")
            arguments = node.parameters.model_dump(mode="json", exclude={"extensions"})
            try:
                validate_parameters(arguments, observed, operation, template=True)
            except ValueError as exc:
                raise ValueError(f"{node.id}: {exc}") from exc
            pointers = list(references(arguments))
        elif node.kind == "transform":
            pointers = list(references(node.assign))
        else:
            pointers = []
        if node.kind == "decide":
            pointers.append(node.condition.pointer)
        for pointer in pointers:
            parts = pointer.split("/")
            if len(parts) < 2 or parts[1] not in {"inputs", "steps", "business_key"}:
                raise ValueError(f"{node.id}: invalid input reference {pointer!r}")
            if parts[1] == "steps" and (len(parts) < 3 or parts[2] not in before[node.id]):
                raise ValueError(f"{node.id}: reference requires a completed step on every incoming path")
        if node.kind in {"wait", "verify"}:
            if not node.condition.pointer.startswith("/response/"):
                raise ValueError(f"{node.id}: predicate must inspect a fresh API response")
            if not operation.business_key_parameter and not operation.record_lookup:
                raise ValueError(f"{node.id}: predicate must inspect data scoped to the run business key")
        if node.kind == "verify":
            covered = set(node.criteria)
            if not covered <= criteria or (not node.next and covered != criteria):
                raise ValueError(f"{node.id}: terminal verification must cover all trusted acceptance criteria")
            if checks and not node.next and not any(
                node.operation_id == check.operation_id
                and node.condition == check.condition
                and covered == set(check.criteria)
                for check in checks
            ):
                raise ValueError(f"{node.id}: terminal verification differs from the pinned WorkSpec predicate")
        if node.kind == "human":
            check_schema(node.input_schema)
            if node.input_schema.get("type") != "object":
                raise ValueError(f"{node.id}: human input_schema must describe an object")



def _resolve_known(value, context):
    path = reference(value)
    if path:
        parts = path.split("/")
        if parts[1] == "steps" and parts[2] not in context["steps"]:
            return value
        return at(context, path)
    if isinstance(value, dict):
        return {key: _resolve_known(child, context) for key, child in value.items()}
    if isinstance(value, list):
        return [_resolve_known(child, context) for child in value]
    return value


def validate_start_bindings(spec, inputs, business_key, snapshot, environment):
    """Check bindings determined by the starting inputs before creating a run."""
    nodes = {step.id: step for step in spec.nodes}
    context = {"inputs": inputs, "business_key": business_key, "steps": {}}
    cursor = spec.entry
    while cursor:
        step = nodes[cursor]
        cursor = step.next
        if step.kind == "transform":
            value = _resolve_known(step.assign, context)
            if not any(references(value)):
                context["steps"][step.id] = value
        elif step.kind == "decide":
            parts = step.condition.pointer.split("/")
            if parts[1] == "steps" and parts[2] not in context["steps"]:
                return
            outcome = matches(step.condition, context)
            context["steps"][step.id] = outcome
            cursor = step.next if outcome else step.otherwise
        elif isinstance(step, ReadStep):
            arguments = step.parameters.model_dump(mode="json", exclude={"extensions"})
            arguments = _resolve_known(arguments, context)
            try:
                validate_parameters(
                    arguments, snapshot.capabilities[step.operation_id],
                    environment.operations[step.operation_id], template=True,
                )
            except ValueError as exc:
                raise ValueError(f"{step.id}: {exc}") from exc
