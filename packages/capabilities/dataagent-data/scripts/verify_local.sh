#!/usr/bin/env bash
# Local release gate for the DataAgent data layer (Round 4).
#
# Runs every gate the 06 §14 acceptance table names, in one pass:
# tests, schema, snapshot, CLI/MCP counts, bundle inventory, mint dry-run,
# the audit manifest and an isolated wheel install/cold start. Commands and
# output are logged to evidence/round4/verify_local.log.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTRACTS="$(cd "$ROOT/../dataagent-contracts" && pwd)"
REPO="$(cd "$ROOT/../../.." && pwd)"
LOG="$ROOT/evidence/round4/verify_local.log"
BUNDLE="$ROOT/packaging/bundle"
EXPECTED_BUNDLE_FILES=85  # W1b: dataagent_runtime vendored into the bundle

mkdir -p "$(dirname "$LOG")"
# Mirror both commands (set -x) and output into the evidence log.
exec > >(tee "$LOG") 2>&1
set -x

echo "# verify_local $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "== dev prerequisites =="
# The gate runs pytest in both packages, but the optional ``dev`` extra is
# not part of the frozen default sync (reviewer r21 N6). Fail up front with
# the fix command instead of surfacing a missing test runner mid-gate.
for _pkg in "$CONTRACTS" "$ROOT"; do
  if ! (cd "$_pkg" && uv run --frozen --no-sync python -c 'import pytest' >/dev/null 2>&1); then
    echo "verify_local: pytest is missing in the $_pkg environment" >&2
    echo "  fix: (cd $_pkg && uv sync --frozen --extra dev)" >&2
    exit 1
  fi
done
if ! (cd "$CONTRACTS" && uv run --frozen --no-sync python -c 'import jsonschema' >/dev/null 2>&1); then
  echo "verify_local: jsonschema is missing in the contracts environment" >&2
  echo "  fix: (cd $CONTRACTS && uv sync --frozen --extra dev)" >&2
  exit 1
fi
echo "dev prerequisites present (pytest in both packages, jsonschema in contracts)"
echo "== contracts tests =="
(cd "$CONTRACTS" && uv run --frozen pytest -o addopts="" -q)
echo "== contracts schema =="
(cd "$CONTRACTS" && uv run --frozen python scripts/generate_schema.py --check)

cd "$ROOT"
echo "== data tests =="
uv run --frozen pytest -o addopts="" -q
echo "== catalog snapshot =="
uv run --frozen python scripts/export_catalog_snapshot.py --check

echo "== CLI catalog =="
CLI_COUNT="$(uv run --frozen python -m dataagent_data.interfaces.cli --list \
  | uv run --frozen python -c 'import json,sys; print(len(json.load(sys.stdin)))')"
test "$CLI_COUNT" = "32"

echo "== MCP tools/list =="
MCP_COUNT="$(printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  | uv run --frozen python -m dataagent_data.interfaces.mcp_server \
  | uv run --frozen python -c 'import json,sys; print(len(json.load(sys.stdin)["result"]["tools"]))')"
test "$MCP_COUNT" = "32"

echo "== bundle inventory =="
uv run --frozen python scripts/build_bundle.py
BUNDLE_FILES="$(find "$BUNDLE" -type f | wc -l | tr -d ' ')"
test "$BUNDLE_FILES" = "$EXPECTED_BUNDLE_FILES"
test "$(find "$BUNDLE" -name '*.pyc' | wc -l | tr -d ' ')" = "0"

echo "== mint publish --dry-run (isolated copy) =="
command -v mint >/dev/null 2>&1 || {
  echo "verify_local: mint is not installed; cannot run the publish gate" >&2
  exit 1
}
TMP="$(mktemp -d "${TMPDIR:-/tmp}/dataagent-verify.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
cp -R "$BUNDLE" "$TMP/bundle"
(cd "$TMP/bundle" && mint publish --dry-run)

echo "== audit manifest =="
(cd "$REPO" && shasum -a 256 -c "$ROOT/evidence/round4/manifest.sha256")

echo "== isolated wheel install + cold start =="
(
  cd "$CONTRACTS"
  uv build --wheel --out-dir "$TMP/wheels" -q
)
(
  cd "$ROOT/../dataagent-runtime"
  uv build --wheel --out-dir "$TMP/wheels" -q
)
(
  cd "$ROOT"
  uv build --wheel --out-dir "$TMP/wheels" -q
)
uv venv --python 3.12 "$TMP/venv" -q
VIRTUAL_ENV="$TMP/venv" uv pip install --no-deps -q "$TMP"/wheels/*.whl
VIRTUAL_ENV="$TMP/venv" uv pip install -q "pydantic>=2.7,<3" "openpyxl>=3.1,<4" "pdfplumber>=0.11,<1"

cat > "$TMP/req.ndjson" <<'EOF'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
EOF
export MINT_HOME="$TMP/mint-home"
START="$(python3 -c 'import time; print(time.time())')"
ISOLATED_OUT="$(cd "$TMP" && "$TMP/venv/bin/python" -m dataagent_data.interfaces.mcp_server < "$TMP/req.ndjson")"
END="$(python3 -c 'import time; print(time.time())')"
printf '%s\n' "$ISOLATED_OUT"
ISOLATED_COUNT="$(printf '%s\n' "$ISOLATED_OUT" | python3 -c '
import json, sys
count = -1
for line in sys.stdin:
    if not line.strip():
        continue
    message = json.loads(line)
    if message.get("id") == 2:
        count = len(message["result"]["tools"])
print(count)
')"
test "$ISOLATED_COUNT" = "32"
COLD_SECONDS="$(python3 - "$START" "$END" <<'PY'
import sys
print(f"{float(sys.argv[2]) - float(sys.argv[1]):.2f}")
PY
)"
python3 - "$COLD_SECONDS" <<'PY'
import sys
seconds = float(sys.argv[1])
if seconds >= 120:
    raise SystemExit(f"cold start {seconds}s exceeds the 120s budget")
print(f"cold start OK: {seconds}s < 120s")
PY
export -n MINT_HOME || true

echo "== package runtime artifacts =="
test ! -e "$ROOT/.dataagent"
test -z "$(find "$ROOT" -maxdepth 1 -name '.dataagent' -print -quit)"
test -z "$(find "$ROOT" -maxdepth 1 \( -name 'dist' -o -name '*.egg-info' \) -print -quit)"
echo "no package-local .dataagent / dist / egg-info"

echo "verify_local: OK"
