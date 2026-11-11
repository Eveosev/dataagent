"""Read-only OpenAPI discovery and scoped observations."""

from datetime import datetime, timezone
from uuid import uuid4

from dataagent_contracts.environment import ActionBinding, CapabilityObservation, EnvironmentSnapshot

from .bindings import digest
from .planner import at, check_schema, validate_parameters, validate_value

METHODS = {"get", "post", "patch", "put", "delete", "head", "options", "trace"}


def schema_revision(document, environment):
    return digest([document, environment.model_dump(mode="json", exclude={"headers"})])


def expand(value, document, trail=(), budget=None):
    if budget is None:
        budget = [100_000]
    budget[0] -= 1
    if budget[0] < 0:
        raise ValueError("OpenAPI schema expansion exceeds the supported size")
    if len(trail) > 25:
        raise ValueError("OpenAPI reference chain is too deep")
    if isinstance(value, list):
        return [expand(item, document, trail, budget) for item in value]
    if isinstance(value, dict):
        pointer = value.get("$ref")
        if pointer is not None:
            if not isinstance(pointer, str) or not pointer.startswith("#/") or pointer in trail:
                raise ValueError("only non-recursive, local OpenAPI references are supported")
            target = at(document, pointer[1:])
            if not isinstance(target, dict):
                raise ValueError("OpenAPI reference does not name an object")
            expanded = expand(target, document, (*trail, pointer), budget)
            return expanded | expand({key: item for key, item in value.items() if key != "$ref"}, document, trail, budget)
        return {key: expand(item, document, trail, budget) for key, item in value.items()}
    return value


def _schemas(method, path, operation, inherited, document):
    parameters, required = {}, {}
    for raw in [*inherited, *operation.get("parameters", [])]:
        param = expand(raw, document)
        location, name = param["in"], param["name"]
        if location not in {"path", "query"}:
            if param.get("required"):
                raise ValueError(f"unsupported required {location} parameter")
            continue
        schema = param.get("schema")
        if not isinstance(schema, dict):
            raise ValueError("API parameter has no JSON schema")
        check_schema(schema)
        parameters.setdefault(location, {})[name] = schema
        names = required.setdefault(location, [])
        if name in names:
            names.remove(name)
        if param.get("required"):
            names.append(name)

    request = expand(operation.get("requestBody") or {}, document)
    request_schema = request.get("content", {}).get("application/json", {}).get("schema")
    if request.get("required") and request_schema is None:
        raise ValueError("required API body must be JSON")
    if request_schema is not None:
        check_schema(request_schema)

    response_schema = None
    for status, response in sorted(operation.get("responses", {}).items()):
        if str(status).startswith("2"):
            response = expand(response, document)
            response_schema = response.get("content", {}).get("application/json", {}).get("schema")
            if response_schema is not None:
                check_schema(response_schema)
                break
    return CapabilityObservation(
        operation_id=operation["operationId"], method=method.upper(), path=path,
        title=operation.get("summary", ""), description=operation.get("description", ""),
        parameters=parameters, required_parameters=required, request_schema=request_schema,
        request_required=bool(request.get("required")), response_schema=response_schema,
    )


def discover(client, environment_id, scope_ref, authorization_ref):
    document = client.description()
    if (
        not isinstance(document, dict) or not isinstance(document.get("openapi"), str)
        or not document["openapi"].startswith("3.1.") or not isinstance(document.get("paths"), dict)
    ):
        raise ValueError("environment must describe its API as OpenAPI 3.1")
    environment = client.environment
    capabilities = {}
    seen = set()
    gaps = []
    for path, entry in document["paths"].items():
        if not isinstance(entry, dict):
            continue
        for method, operation in entry.items():
            if method not in METHODS or not isinstance(operation, dict):
                continue
            name = operation.get("operationId")
            if not isinstance(name, str) or not name:
                continue
            if name in seen:
                raise ValueError(f"duplicate OpenAPI operation ID {name!r}")
            seen.add(name)
            try:
                found = _schemas(method, path, operation, entry.get("parameters", []), document)
            except (KeyError, TypeError, ValueError) as exc:
                gaps.append(f"{name}: {exc}")
                continue
            policy = environment.operations.get(name)
            if policy and (policy.method, policy.path) == (found.method, found.path):
                found.authorized = True
                if policy.effect:
                    effect = policy.effect
                    found.action = effect.action
                    found.binding = ActionBinding(
                        action=effect.action, operation_id=name, lookup_operation=effect.lookup_operation,
                        method=policy.method, path=policy.path, remote_idempotency=effect.remote_idempotency,
                        remote_fencing=effect.remote_fencing,
                        precondition=effect.before.model_dump(mode="json") if effect.before else None,
                        expected_effect=effect.applied.model_dump(mode="json"),
                    )
            capabilities[name] = found

    for name, policy in environment.operations.items():
        found = capabilities.get(name)
        if found is None or not found.authorized:
            gaps.append(f"{name}: configured operation is absent or its method/path differs")
            continue
        if policy.business_key_parameter and policy.method == "GET" and not policy.record_lookup:
            arguments = {"path": {}, "query": {
                policy.business_key_parameter: environment.business_key_prefix + "discovery-" + uuid4().hex,
            }, "body": {}}
            try:
                validate_parameters(arguments, found, policy)
                reply = client.read(name, arguments)
                if found.response_schema is not None:
                    validate_value(reply, found.response_schema)
            except ValueError as exc:
                gaps.append(f"{name}: read probe failed: {exc}")
                continue
            found.verification = "observed"
            lookup_collections = set()
            for dependent_id, dependent in environment.operations.items():
                target = dependent.effect or dependent
                lookup_id = target.lookup_operation if dependent.effect else dependent.record_lookup
                if lookup_id != name:
                    continue
                pointer = target.collection_pointer
                if isinstance(at(reply, pointer, default=None), list):
                    lookup_collections.add(pointer)
                else:
                    gaps.append(f"{dependent_id}: configured business lookup has no collection at {pointer!r}")
            found.evidence = {
                "probe": "scoped_business_key_query",
                "response_fields": sorted(reply) if isinstance(reply, dict) else [],
                "lookup_collections": sorted(lookup_collections),
            }

    return EnvironmentSnapshot(
        id=uuid4().hex, revision=schema_revision(document, environment), environment_id=environment_id,
        environment_identity=environment.identity, tenant=environment.tenant, scope_ref=scope_ref, authorization_ref=authorization_ref,
        observed_at=datetime.now(timezone.utc), title=document.get("info", {}).get("title", environment_id),
        capabilities=capabilities, gaps=gaps,
    )
