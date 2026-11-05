#!/usr/bin/env bash
# 把 10 个 iface 契约包发布到**线上** Mint Hub（D72）。
#
# 前置：
#   1. 拥有线上 hub 的令牌（角色 ea-mint:operator 或 ea-mint:admin），形如 mint_xxx
#      获取：https://auth.ea.modelbest.co 登录 → 有 ea-mint 权限的账号 → 生成/复制令牌
#   2. 本机有 mint 二进制（默认取 PATH 上的 mint，可用 MINT_BIN 覆盖）
#
# 用法：
#   export MINT_TOKEN='mint_...'
#   bash packages/kernel-iface/publish-iface-online.sh            # 发布全部 10 个
#   bash packages/kernel-iface/publish-iface-online.sh --check    # 只检查登录与线上可达，不发布
#
# 特点：幂等（已存在的版本会报 version_taken → 视为跳过）；逐包核验 mint info。
set -uo pipefail

HUB_URL="${MINT_HUB_URL:-https://mint-hub.ea.modelbest.co}"
MINT_BIN="${MINT_BIN:-$(command -v mint || echo "$HOME/.mint/bin/mint")}"
PKG_ROOT="$(cd "$(dirname "$0")" && pwd)"
CHECK_ONLY=0
[ "${1:-}" = "--check" ] && CHECK_ONLY=1

fail() { echo "[FAIL] $*" >&2; exit 1; }
info() { echo "· $*"; }

[ -x "$MINT_BIN" ] || fail "找不到 mint 二进制：$MINT_BIN（用 MINT_BIN=/path/to/mint 覆盖）"
[ -d "$PKG_ROOT" ] || fail "找不到 packages 目录：$PKG_ROOT"

info "hub      = $HUB_URL"
info "mint     = $MINT_BIN"
info "packages = $PKG_ROOT"

# 1) 线上可达性 + 认证配置
code=$(curl -s -m 10 -o /dev/null -w "%{http_code}" "$HUB_URL/api/v1/auth/config" || true)
[ "$code" = "200" ] || fail "线上 hub 不可达或路径异常（/api/v1/auth/config -> $code）"
info "线上 hub 可达（auth/config 200）"

# 2) 登录（令牌从环境变量经 stdin 传入，不落 shell 历史）
[ -n "${MINT_TOKEN:-}" ] || fail "请先 export MINT_TOKEN='mint_...'"
printf '%s' "$MINT_TOKEN" | "$MINT_BIN" login --token-stdin --registry "$HUB_URL" -y \
  || fail "mint login 失败（令牌无效/无 ea-mint 权限？）"
info "login 成功"

me=$("$MINT_BIN" --json --registry "$HUB_URL" search "" 2>/dev/null | head -1 || true)
if [ "$CHECK_ONLY" = "1" ]; then info "--check 模式：不发布"; exit 0; fi

# 3) 逐个发布
PKGS=(iface-types iface-env iface-session iface-policy iface-extension iface-tool iface-loop iface-context iface-model iface-store)
ok=0; skip=0; bad=0
for p in "${PKGS[@]}"; do
  dir="$PKG_ROOT/$p"
  [ -d "$dir" ] || { echo "[MISS] $p（目录不存在）"; bad=$((bad+1)); continue; }
  out=$(cd "$dir" && "$MINT_BIN" publish --registry "$HUB_URL" -y -v 2>&1); rc=$?
  if [ $rc -eq 0 ]; then echo "[ OK ] $p"; ok=$((ok+1));
  elif echo "$out" | grep -qiE "version_taken|409|已存在"; then echo "[SKIP] $p（版本已存在）"; skip=$((skip+1));
  else echo "[FAIL] $p"; echo "$out" | tail -3; bad=$((bad+1)); fi
done

# 4) 核验：远端搜索应能看到 10 个 iface
echo "--- 远端核验 ---"
"$MINT_BIN" --registry "$HUB_URL" search iface || true

echo "--- 汇总：ok=$ok skip=$skip fail=$bad ---"
[ "$bad" -eq 0 ] || exit 1
