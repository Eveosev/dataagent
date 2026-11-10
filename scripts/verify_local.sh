#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec "$ROOT/packages/capabilities/dataagent-workbench/.venv/bin/python" "$ROOT/scripts/verify_local.py" "$@"
