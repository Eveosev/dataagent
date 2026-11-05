"""Thin dispatch adapter over the shared ``dataagent_runtime.invoke`` (W1b).

Guarantees the data layer's operation modules are registered before the
dispatch, and that calls without an explicit ``runtime`` use the data
layer's default runtime (which wires the trace repository and the optional
OCR engine). The wire contract is unchanged: ``invoke(operation, input,
CallContext) -> CapabilityResult``.

DA12.1 (08 §4.3, W1d): this is the product path — the shared invoke runs the
access recheck for every operation that declares ``resource_fields``. The
mode and resolver default to the runtime's (``DATAAGENT_ENFORCEMENT_MODE``,
``data_root/db/decisions.sqlite3``) and can be narrowed per call by the
trusted host (``resolver`` / ``enforcement``), never by call arguments.
"""

from __future__ import annotations

from typing import Any

from dataagent_contracts.core import CallContext, CapabilityResult


def invoke(
    operation: str,
    payload: dict[str, Any] | None,
    context: CallContext | dict[str, Any],
    *,
    runtime: Any = None,
    resolver: Any = None,
    enforcement: Any = None,
) -> CapabilityResult[Any]:
    from dataagent_data.registry import load_operations
    from dataagent_data.runtime import default_runtime
    from dataagent_runtime.invoke import invoke as shared_invoke

    load_operations()
    return shared_invoke(
        operation,
        payload,
        context,
        runtime=runtime or default_runtime(),
        resolver=resolver,
        enforcement=enforcement,
    )


__all__ = ["invoke"]
