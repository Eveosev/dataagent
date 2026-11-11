"""Business-key queries provide evidence for action outcome classification."""

from .adapters.api import ApiError
from .planner import at, matches, same, validate_parameters


def query_record(client, snapshot, operation_id, collection_pointer, key, key_pointer):
    policy = client.environment.operations[operation_id]
    observation = snapshot.capabilities.get(operation_id)
    if observation is None or not observation.authorized:
        raise ValueError("business-key lookup is absent from the validated environment")
    arguments = {"path": {}, "query": {policy.business_key_parameter: key}, "body": {}}
    validate_parameters(arguments, observation, policy)
    reply = client.read(operation_id, arguments)
    try:
        records = at(reply, collection_pointer)
        if (
            not isinstance(records, list) or len(records) > 1 or
            (records and at(records[0], key_pointer) != key)
        ):
            raise ValueError("business-key lookup returned ambiguous or unrelated records")
    except ValueError as exc:
        raise ApiError(str(exc)) from exc
    return records[0] if records else None


def effect_record(client, snapshot, policy, key):
    return query_record(
        client, snapshot, policy.lookup_operation, policy.collection_pointer, key, policy.record_key_pointer,
    )


def classify(policy, arguments, record):
    if record is None:
        return "unknown"
    if matches(policy.applied, record):
        try:
            fields_match = all(
                same(at(record, observed), at(arguments["body"], requested))
                for observed, requested in policy.match_fields.items()
            )
        except ValueError:
            fields_match = False
        return "applied" if fields_match else "partial"
    if matches(policy.partial, record):
        return "partial"
    if matches(policy.definitive_not_applied, record):
        return "not_applied"
    return "unknown"
