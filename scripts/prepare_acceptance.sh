#!/usr/bin/env bash
# Prepare the local acceptance environment.
#
#   1. `uv sync --frozen` in every capability package that has a
#      pyproject.toml (the lock is authoritative; nothing is re-locked).
#   2. Rebuild the workbench frontend when the bundled static output is
#      missing or older than its web sources: `npm ci` + `npm run build`.
#   3. Build the installable local closure with the workbench bundle
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
WEB=$WORKBENCH/web
STATIC=$WORKBENCH/src/dataagent_workbench/static
BUILD_OUT=$ROOT/build/local

# FDE3-06: the static bundle is gitignored, and a stale one silently shipped an
# older UI. Rebuild when index.html is absent or any frontend input is newer;
# npm ci keeps the install pinned to web/package-lock.json.
frontend_stale() {
    [ -f "$STATIC/index.html" ] || return 0
    [ -n "$(find "$WEB/src" "$WEB/public" \
        "$WEB/index.html" "$WEB/package.json" "$WEB/package-lock.json" \
        "$WEB/vite.config.ts" "$WEB/tsconfig.json" "$WEB/tools" \
        -newer "$STATIC/index.html" -print -quit 2>/dev/null)" ]
}

if frontend_stale; then
    command -v npm >/dev/null 2>&1 || { echo "prepare_acceptance: npm not found on PATH (frontend build requires it)" >&2; exit 2; }
    echo "build: frontend static (missing or older than web inputs)"
    (cd "$WEB" && npm ci --prefer-offline --no-audit --no-fund && npm run build)
    [ -f "$STATIC/index.html" ] || { echo "prepare_acceptance: frontend build did not produce $STATIC/index.html" >&2; exit 2; }
else
    echo "frontend: static up to date"
fi

echo "build: $BUILD_OUT"
"$WORKBENCH/.venv/bin/python" "$WORKBENCH/tools/build_bundle.py" --out "$BUILD_OUT"
