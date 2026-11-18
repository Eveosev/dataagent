---
version: 2
date: 2026-11-18
dataagent_commit: 79d58fe
kernel_commit: 8439ec884cab9844631a0f8a574810f8bcb522f2
mint_cli: 0.1.31
---

# 本机离线安装与操作

本机路径只运行浏览器工作台，不经过 Mint 会话。需要 Python 3.11–3.13、uv、浏览器和已缓存的 Python 依赖。文件、SQLite 和已配置的环回连接可直接探查，采购资料映射可在页面手工完成。

本文对应 DataAgent `feat/p1-intake` 的 `79d58fe`，Mint CLI 0.1.31。构建和安装包与 [Mint 手册](mint-offline-quickstart.md#1-构建与安装)共用同一套入口。

## 1. 构建与安装

### 1.1 构建安装闭包

```sh
export DATAAGENT_CHECKOUT="$HOME/Vibe/AgentCPM-OS/projects/dataagent"
cd "$DATAAGENT_CHECKOUT"
git switch feat/p1-intake
export UV_OFFLINE=1
if [ -d /private/tmp/dataagent-uv-cache ]; then
  export UV_CACHE_DIR=/private/tmp/dataagent-uv-cache
fi

bash scripts/prepare_acceptance.sh
test -f build/local/manifest.json
```

`scripts/prepare_acceptance.sh` 是唯一构建入口：同步各 Python 包的锁定依赖，再生成 `build/local/preset-intake`。它不生成前端；如果 `packages/capabilities/dataagent-workbench/src/dataagent_workbench/static/index.html` 不存在，先执行一次 `npm --prefix packages/capabilities/dataagent-workbench/web run build`（需要已安装的 Node 依赖），再运行 `prepare_acceptance.sh`。静态目录当前不在版本库中，换机器要重建。

### 1.2 创建本机项目

```sh
export PATH="$HOME/.mint/bin:$PATH"
export MINT_NET_OFFLINE=1
export DATAAGENT_TEST="$(mktemp -d "${TMPDIR:-/tmp}/dataagent-native.XXXXXX")"
cd "$DATAAGENT_TEST"
mint init --no-preset --offline -y
mint add "path:$DATAAGENT_CHECKOUT/build/local/preset-intake" --offline -y

DATAAGENT="./.mint/packages/dataagent/cli@0.1.0/bin/dataagent"
"$DATAAGENT" setup
```

本机模式仍用 Mint 装着安装闭包，只是不启动聊天；这样 `dataagent workbench` 和同一套组件版本才可用。`doctor` 在未配 OCR 时退出 3，`ocr:` 行提示 `dataagent setup --ocr-root`，见 [Mint 手册 §1.4](mint-offline-quickstart.md#14-doctor-的期望值)。

### 1.3 安装本机 OCR（扫描件需要）

```sh
export OCR_STAGE="$HOME/.dataagent/ocr-rapidocr"
OCR="$DATAAGENT_CHECKOUT/packages/capabilities/dataagent-ocr/.venv/bin/dataagent-ocr"
"$OCR" --data-root "$OCR_STAGE" engine plan rapidocr
# 展示计划并取得 plan_digest 后
"$OCR" --data-root "$OCR_STAGE" engine install rapidocr --confirm "<plan_digest>"
"$OCR" --data-root "$OCR_STAGE" configure-engine --engine rapidocr
"$OCR" --data-root "$OCR_STAGE" verify --profile rapidocr
"$DATAAGENT" setup --ocr-root "$OCR_STAGE/ocr"
```

已有验证目录（含 `active.json`）时只执行最后一条。OCR 的安装、固定和更换规则见 [Mint 手册 §1.3](mint-offline-quickstart.md#13-安装本机-ocr扫描件需要)。

### 1.4 追加项目沙箱片段

```sh
if ! grep -q '^\[core.sandbox\]' mint.toml; then
  cat .mint/packages/dataagent/preset-intake@*/sandbox.toml >> mint.toml
fi
```

`mint add` 不会合并 `[core.sandbox]` 和 `[rules]`，这段必须手动追加一次；它只收紧权限，不扩大授权。说明见 [Mint 手册 §1.5](mint-offline-quickstart.md#15-追加项目沙箱片段)。

## 2. 启动、查看和停止工作台

先按[测试用例](offline-input-cases.md#准备测试输入)准备样例。在一个终端前台启动：

```sh
cd "$DATAAGENT_TEST"
"$DATAAGENT" workbench serve --port 8765
```

服务只监听 `127.0.0.1`。按 `Ctrl-C` 停止；服务正常退出时会删除 `.dataagent/runtime/workbench.json`。需要后台运行时把输出重定向，再用 `workbench stop` 停止：

```sh
mkdir -p .dataagent/runtime
"$DATAAGENT" workbench serve --port 8765 > .dataagent/runtime/serve.log 2>&1 &
sleep 2   # 等描述文件和 /health 就绪；也可先跑 doctor 看 service 行
"$DATAAGENT" workbench list
"$DATAAGENT" workbench stop
```

- `workbench list` 列出任务、阶段和发布引用，不需要服务在运行。
- `workbench stop` 只停当前工作区的服务；没有运行或描述文件过期时返回 `not_running`。
- `workbench status <SESSION_ID>` 读任务状态；`workbench view <SESSION_ID>` 启动服务（如未运行）并请服务端打开页面。
- 下次用同一目录重启，保存浏览器地址中 `#session=` 后的任务 ID 即可恢复任务；需要重新认证时从工作台首页再点一次入口。

## 3. 打开本地工作台

未认证时，`http://127.0.0.1:8765` 显示「打开本地工作台」。点击按钮后，服务端调用默认浏览器打开带 `#nonce=` 的一次性链接；nonce 60 秒过期，链接只在当前机器有效。按钮只是发起请求，当前页不会提示浏览器是否真的打开。

没有默认浏览器、在远程机器或通过 SSH 使用时，不能直接用 `BROWSER=... "$DATAAGENT" workbench serve`：统一 CLI 的分发器会清理宿主环境，只保留 `DATAAGENT_*`、`PATH` 等白名单变量，`BROWSER` 传不进去。改为直接用安装目录里的 workbench 解释器启动同一服务：

```sh
WORKBENCH=$(ls -d .mint/packages/dataagent/workbench@* | head -1)
BROWSER='echo %s' "$WORKBENCH/.venv/bin/python" \
  -m dataagent_workbench.interfaces.cli --workspace "$PWD" serve --port 8765
```

点击「打开本地工作台」后，带 nonce 的地址会打印在 `serve` 输出里；在 60 秒内用能访问 `127.0.0.1:8765` 的浏览器打开。远程场景需要先做 SSH 端口转发。`workbench view` 返回的 `url` 不带 nonce，不能当认证链接复制；当前没有直接打印一次性链接的 CLI 命令（FDE-15 待补）。`dataagent workbench stop` 仍可停止这个服务，描述文件和健康检查与统一 CLI 启动时相同。

## 4. 手工核对

打开工作台后选择文件或已配置连接，填写接入目标，先跑 [CSV 基线](offline-input-cases.md#文件输入)，再选择其他用例。

- 采购资料映射先核对来源证据，再生成映射预览。核对编号、金额、币种后点击「保存接入」。
- 陌生 SQLite 库选择「从数据库发现本体」。本机工作台可直接检查结构、样本和关系候选。固定提案的端到端审核可运行下方浏览器用例，模型生成的草案按 [Mint 手册](mint-offline-quickstart.md)提交。
- 保存被拦时，工作台网页可纠正当前值、修订这类来源的映射或提本体草案；标记空白页、排除记录、缺键记录单列和只保存无问题对象要用 `dataagent-intake` 的工具，见[保存被拦怎么办](offline-input-cases.md#保存被拦怎么办)。

## 5. 本机回归

开发工作树已准备测试依赖时，可运行以下用例。浏览器验收使用本机 Chrome。

```sh
cd "$DATAAGENT_CHECKOUT"
packages/capabilities/dataagent-workbench/.venv/bin/python scripts/verify_browser.py
```

预期覆盖 CSV、文本 PDF、两来源归并、并发映射编辑和 SQLite 发现审核。SQLite 用例通过公开工具提交固定草案，并在 Chrome 确认和刷新复核。

装包后的文件阶段回归用。`verify_local.sh` 的所有阶段都会先跑 `bootstrap.prepare`，所以运行前要先装好 OCR 并 `export OCR_ROOT`，且 `doctor` 要有 `ocr: ... version=` 行；下面的 `--ocr-root` 只用于 `files` 的扫描用例：

```sh
export OCR_ROOT="$OCR_STAGE/ocr"
bash scripts/verify_local.sh --phase files --ocr-root "$OCR_ROOT"
```
