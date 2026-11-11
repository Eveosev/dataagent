"""CLI and stdio MCP entry points."""

import argparse
import json
import sys
from uuid import uuid4

from dataagent_contracts.core import CapabilityStatus

from .mcp import OPERATIONS, invoke, load_service, main as serve


def main():
    parser = argparse.ArgumentParser(prog="dataagent-operations")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("mcp", help="serve stdio MCP")
    call = commands.add_parser("call", help="read one operation's JSON arguments from stdin")
    call.add_argument("operation", choices=sorted(OPERATIONS))
    commands.add_parser("revoke", help="revoke the authorization in the trusted host configuration")
    args = parser.parse_args()
    if args.command == "mcp":
        return serve()
    try:
        service = load_service()
        if args.command == "revoke":
            service.revoke()
            print(json.dumps({"revoked": service.config.authorization_ref}))
            return 0
        payload = json.load(sys.stdin)
        context = {
            "request_id": uuid4().hex,
            "scope_ref": service.config.scope_ref,
            "authorization_ref": service.config.authorization_ref,
        }
        result = invoke(args.operation, payload, context)
        print(result.model_dump_json())
        return int(result.status == CapabilityStatus.failed)
    except (ValueError, OSError) as exc:
        print(f"dataagent-operations: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
