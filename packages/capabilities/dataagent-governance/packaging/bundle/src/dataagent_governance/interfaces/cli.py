"""CLI for the governance layer.

Three entry kinds:

- unified argv mode (12-unified-cli-research §5.3) — ``list``, ``run <op>``
  with ``--input-file`` / ``--set`` / ``--set-json`` / ``--ref`` /
  ``--proposal-file`` / ``--authorize`` / ``--detail``, summary JSON on
  stdout and the full result under ``<data_root>/results/``;
- ``confirm <file>`` / legacy ``confirm-criteria`` — the trusted-host
  management entry that activates a draft criteria (review §9). It is
  deliberately not an MCP tool: the repair flow must not be able to drive
  it from inside a model context;
- ``policy apply <file>`` — write an access policy document into the
  versioned repository (12 §5.3).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from dataagent_runtime.interfaces.unified import EXIT_USAGE, LayerHooks, main as unified_main

from dataagent_governance import __version__  # noqa: F401 - re-exported for parity
from dataagent_governance.registry import validate_registry
from dataagent_governance.runtime import default_runtime
from dataagent_governance.runtime.runtime import GovernanceRuntime

USAGE = """usage: python -m dataagent_governance.interfaces.cli list
       python -m dataagent_governance.interfaces.cli run <op> [--input-file F] [--set k=v] ...
       python -m dataagent_governance.interfaces.cli <op> --help
       python -m dataagent_governance.interfaces.cli confirm <criteria.json>
       python -m dataagent_governance.interfaces.cli policy apply <policy.json>
       python -m dataagent_governance.interfaces.cli <operation>            (legacy: JSON on stdin)
       python -m dataagent_governance.interfaces.cli confirm-criteria       (legacy: JSON on stdin)
       python -m dataagent_governance.interfaces.cli --list                 (legacy: JSON list)
"""


def _invoke(operation, payload, context):
    from dataagent_runtime.invoke import invoke

    return invoke(operation, payload, context, runtime=default_runtime())


def _list_operations():
    from dataagent_runtime.registry import list_operations

    from dataagent_governance.registry import load_operations

    load_operations()
    return list_operations()


def _read_json_file(path: str, *, command: str) -> dict[str, Any] | None:
    """JSON object from a file; ``None`` (already reported) on failure."""

    try:
        body = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"{command}: file not found: {path}", file=sys.stderr)
        return None
    except (OSError, json.JSONDecodeError) as exc:
        print(f"{command}: cannot read {path}: {exc}", file=sys.stderr)
        return None
    if not isinstance(body, dict):
        print(f"{command}: JSON must be an object", file=sys.stderr)
        return None
    return body


def _confirm_criteria(body: dict[str, Any]) -> int:
    """Activate a draft with an authorized confirmation record.

    ``authorized_confirmers`` comes from the trusted host configuration
    (``DATAAGENT_CONFIRMERS``, comma-separated subject refs) — never from
    the JSON body.
    """

    from dataagent_governance.contracts import CriteriaConfirmation
    from dataagent_governance.evaluation.criteria_samples import (
        confirm_acceptance_criteria,
    )

    confirmers = {
        part.strip()
        for part in (os_environ("DATAAGENT_CONFIRMERS", "").split(","))
        if part.strip()
    }
    if not confirmers:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "issues": [
                        {
                            "code": "da12.access_denied",
                            "severity": "error",
                            "message": "no authorized confirmers configured "
                            "(DATAAGENT_CONFIRMERS); refusing to activate",
                            "retryable": False,
                        }
                    ],
                },
                ensure_ascii=False,
            )
        )
        return 1
    from dataagent_runtime.errors import CapabilityError
    from dataagent_contracts.core import CriteriaRef
    from pydantic import ValidationError

    try:
        confirmation = CriteriaConfirmation.model_validate(body.get("confirmation"))
        criteria_id = str(body["criteria_id"])
        criteria_revision = str(body["criteria_revision"])
    except ValidationError as exc:
        print(f"confirm: invalid confirmation record: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except KeyError as exc:
        print(f"confirm: missing required field: {exc.args[0]}", file=sys.stderr)
        return EXIT_USAGE
    try:
        rt: GovernanceRuntime = default_runtime()
        ref: CriteriaRef = confirm_acceptance_criteria(
            rt,
            criteria_id,
            criteria_revision,
            confirmation,
            authorized_confirmers=confirmers,
        )
    except CapabilityError as exc:
        issue = exc.to_issue()
        print(
            json.dumps(
                {
                    "status": "failed",
                    "issues": [
                        {
                            "code": issue.code,
                            "severity": issue.severity.value,
                            "message": issue.message,
                            "retryable": issue.retryable,
                        }
                    ],
                },
                ensure_ascii=False,
            )
        )
        return 1
    print(json.dumps(ref.model_dump(mode="json"), ensure_ascii=False))
    return 0


def _policy_apply(path: str) -> int:
    """Write an access policy document (12 §5.3 ``policy apply <file>``)."""

    from dataagent_contracts.core import VersionedRef

    body = _read_json_file(path, command="policy apply")
    if body is None:
        return EXIT_USAGE
    from dataagent_governance.contracts import PolicyDocument
    from pydantic import ValidationError

    try:
        policy = PolicyDocument.model_validate(body)
    except ValidationError as exc:
        print(f"policy apply: invalid policy document: {exc}", file=sys.stderr)
        return EXIT_USAGE
    rt: GovernanceRuntime = default_runtime()
    ref: VersionedRef = rt.policy.save(policy)
    print(json.dumps(ref.model_dump(mode="json"), ensure_ascii=False))
    return 0


def os_environ(name: str, default: str = "") -> str:
    import os

    return os.environ.get(name, default)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in {"confirm", "confirm-criteria"}:
        try:
            validate_registry()
        except Exception as exc:  # noqa: BLE001
            print(f"dataagent-governance: registry check failed: {exc}", file=sys.stderr)
            return 3
        if argv[0] == "confirm":
            if len(argv) != 2:
                print("usage: ... cli confirm <criteria.json>", file=sys.stderr)
                return EXIT_USAGE
            body = _read_json_file(argv[1], command="confirm")
            return EXIT_USAGE if body is None else _confirm_criteria(body)
        raw = sys.stdin.read()
        try:
            body = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError as exc:
            print(f"invalid JSON on stdin: {exc.msg}", file=sys.stderr)
            return 2
        if not isinstance(body, dict):
            print("stdin JSON must be an object", file=sys.stderr)
            return 2
        return _confirm_criteria(body)
    if argv[:2] == ["policy", "apply"]:
        try:
            validate_registry()
        except Exception as exc:  # noqa: BLE001
            print(f"dataagent-governance: registry check failed: {exc}", file=sys.stderr)
            return 3
        if len(argv) != 3:
            print("usage: ... cli policy apply <policy.json>", file=sys.stderr)
            return EXIT_USAGE
        return _policy_apply(argv[2])
    hooks = LayerHooks(
        layer="gov",
        list_operations=_list_operations,
        invoke=_invoke,
        validate=validate_registry,
        runtime_factory=default_runtime,
        program="dataagent-governance",
        usage=USAGE,
    )
    return unified_main(argv, hooks=hooks)


if __name__ == "__main__":
    raise SystemExit(main())
