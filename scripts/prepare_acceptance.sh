#!/usr/bin/env bash
# Prepare the local acceptance environment.
#
#   1. `uv sync --frozen` in every capability package that has a
#      pyproject.toml (the lock is authoritative; nothing is re-locked).
#   2. Build the installable local closure with the workbench bundle
#      builder: packages/capabilities/dataagent-workbench/tools/build_bundle.py
#      --out build/local
#
# Acceptance commands then run through scripts/verify_local.sh, which uses
# the workbench .venv and the freshly built build/local/preset-intake.
set -euo pipefail

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
CAP_DIR=${CAP:-packages/capabilities}
case $CAP_DIR in
    /*) ;;
    *) CAP_DIR="$ROOT/$CAP_DIR" ;;
esac

[ -d "$CAP_DIR" ] || { echo "prepare_acceptance: capability directory not found: $CAP_DIR" >&2; exit 2; }
command -v uv >/dev/null 2>&1 || { echo "prepare_acceptance: uv not found on PATH" >&2; exit 2; }

for dir in "$CAP_DIR"/dataagent-*; do
    [ -f "$dir/pyproject.toml" ] || continue
    pkg=$(basename "$dir")
    echo "sync: $pkg"
    (cd "$dir" && uv sync --frozen)
done

WORKBENCH=$CAP_DIR/dataagent-workbench
BUILD_OUT=$ROOT/build/local
echo "build: $BUILD_OUT"
"$WORKBENCH/.venv/bin/python" "$WORKBENCH/tools/build_bundle.py" --out "$BUILD_OUT"
