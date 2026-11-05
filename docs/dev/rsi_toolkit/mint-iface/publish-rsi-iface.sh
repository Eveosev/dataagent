#!/usr/bin/env bash
# 把 rsi-iface-* 契约包发布到 MintHub。
#
# 与 packages/kernel-iface/publish-iface-online.sh 保持同一套约定：
#   * 令牌只从 stdin 进 `mint login`，不进命令行/日志；
#   * 已存在的版本按 version_taken 视为 SKIP（幂等）；
#   * 逐包核对远端可见性。
#
# 与它的**唯一实质差别**：默认不发布。默认只做 pack + publish --dry-run，
# 必须显式 --publish 才真的上传。发布是不可撤销的对外副作用，不该由"忘了加参数"触发。
#
# 用法：
#   export MINT_TOKEN='mint_...'
#   ./publish-rsi-iface.sh --check                       # 只看可达性/登录/远端已有版本
#   ./publish-rsi-iface.sh --dir /abs/gen --scope acme   # 默认：pack + dry-run
#   ./publish-rsi-iface.sh --dir /abs/gen --scope acme --publish
#
# 前置：
#   1. 已用 gen_contract_packages.py 生成包目录；
#   2. scope 必须是你拥有且能在 MintHub 控制台签发 publish-new/publish-update 令牌的那个；
#   3. `local/` 只能用于本地验收，不能作为发布命名空间。

set -uo pipefail

HUB_URL="${MINT_HUB_URL:-https://mint-hub.ea.modelbest.co}"
MINT_BIN="${MINT_BIN:-$HOME/.mint/bin/mint}"
DIR=""
SCOPE=""
CHECK_ONLY=0
DO_PUBLISH=0

fail() { echo "[FAIL] $*" >&2; exit 1; }
info() { echo "· $*"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --dir) DIR="${2:-}"; shift 2 ;;
    --scope) SCOPE="${2:-}"; shift 2 ;;
    --check) CHECK_ONLY=1; shift ;;
    --publish) DO_PUBLISH=1; shift ;;
    -h|--help) awk 'NR>1 && /^#/ {sub(/^# ?/,""); print; next} NR>1 {exit}' "$0"; exit 0 ;;
    *) fail "未知参数：$1" ;;
  esac
done

[ -x "$MINT_BIN" ] || fail "找不到 mint 二进制：$MINT_BIN（用 MINT_BIN=/path/to/mint 覆盖）"
info "hub  = $HUB_URL"
info "mint = $MINT_BIN"

# 1) 线上可达性
code=$(curl -s -m 10 -o /dev/null -w "%{http_code}" "$HUB_URL/api/v1/auth/config" || true)
[ "$code" = "200" ] || fail "线上 hub 不可达（/api/v1/auth/config -> $code）"
info "hub 可达（auth/config 200）"

# 2) 登录（令牌经 stdin）
[ -n "${MINT_TOKEN:-}" ] || fail "请先 export MINT_TOKEN='mint_...'"
printf '%s' "$MINT_TOKEN" | "$MINT_BIN" login --token-stdin --registry "$HUB_URL" -y \
  || fail "mint login 失败（令牌无效或缺少 ea-mint 权限？）"
info "login 成功"

if [ "$CHECK_ONLY" = "1" ]; then
  info "--check 模式：列出远端已有的 rsi 契约包"
  "$MINT_BIN" --registry "$HUB_URL" search rsi-iface || true
  exit 0
fi

[ -n "$DIR" ] || fail "需要 --dir <生成目录>"
[ -d "$DIR" ] || fail "目录不存在：$DIR"
[ -n "$SCOPE" ] || fail "需要 --scope <你拥有的 scope>"
[ "$SCOPE" != "local" ] || [ "$DO_PUBLISH" = "0" ] || fail "local/ 不能作为发布命名空间"

# 生成目录里的 mint.toml 用的是生成时的 scope；这里核对一次，避免发错命名空间。
for d in "$DIR"/rsi-iface-*; do
  [ -d "$d" ] || continue
  got=$(sed -n 's/^name = "\([^/]*\)\/.*/\1/p' "$d/mint.toml" | head -1)
  [ "$got" = "$SCOPE" ] || fail "$(basename "$d") 的 scope 是 '$got'，与 --scope '$SCOPE' 不一致（重新生成）"
done

ok=0; skip=0; bad=0
for d in "$DIR"/rsi-iface-*; do
  [ -d "$d" ] || continue
  name=$(basename "$d")

  # 3) pack：结构问题在本地就暴露，别等上传
  if ! "$MINT_BIN" --json --offline pack "$d" --out "$DIR/.pack" >/dev/null 2>&1; then
    echo "[FAIL] $name（pack 失败）"; "$MINT_BIN" --offline pack "$d" --out "$DIR/.pack" 2>&1 | tail -3
    bad=$((bad+1)); continue
  fi

  if [ "$DO_PUBLISH" = "0" ]; then
    out=$("$MINT_BIN" --registry "$HUB_URL" publish "$d" --dry-run -y 2>&1); rc=$?
    if [ $rc -eq 0 ]; then echo "[DRY ] $name"; ok=$((ok+1));
    else echo "[FAIL] $name（dry-run）"; echo "$out" | tail -3; bad=$((bad+1)); fi
    continue
  fi

  # 4) 真发布
  out=$("$MINT_BIN" --registry "$HUB_URL" publish "$d" -y -v 2>&1); rc=$?
  if [ $rc -eq 0 ]; then echo "[ OK ] $name"; ok=$((ok+1));
  elif echo "$out" | grep -qiE "version_taken|409|已存在"; then echo "[SKIP] $name（版本已存在）"; skip=$((skip+1));
  else echo "[FAIL] $name"; echo "$out" | tail -3; bad=$((bad+1)); fi
done

# 5) 远端核验
echo "--- 远端核验 ---"
"$MINT_BIN" --registry "$HUB_URL" search rsi-iface || true

echo "--- 汇总：ok=$ok skip=$skip fail=$bad ---"
if [ "$DO_PUBLISH" = "0" ]; then
  echo "（本次是 dry-run；加 --publish 才真正上传）"
fi
[ "$bad" -eq 0 ] || exit 1
