---
version: 3
date: 2026-11-18
dataagent_commit: 79d58fe
kernel_commit: 8439ec884cab9844631a0f8a574810f8bcb522f2
mint_cli: 0.1.31
---

# Mint 离线安装与操作

Mint 路径从 TUI 或原生 GUI 发起任务，DataAgent 工作台用于查看来源、核对映射和审核。同一任务共享 Mint 项目目录。模型推理需要可用的本机端点；只想用浏览器手工探查和映射时，使用[本机工作台手册](local-offline-quickstart.md)。

本文对应 DataAgent `feat/p1-intake` 的 `79d58fe`，Mint CLI 0.1.31，Core 0.1.47-std。

## 1. 构建与安装

### 1.1 构建安装闭包

在子项目仓库构建。`agentcpm-os` 下的路径是 `projects/dataagent`；分支用 `feat/p1-intake` 或包含本次改动的集成分支。

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

`scripts/prepare_acceptance.sh` 是后端与安装闭包的正式构建入口。它对每个 `packages/capabilities/dataagent-*` 执行 `uv sync --frozen`，再用工作台的 `build_bundle.py --out build/local` 生成 `build/local/preset-intake`。不要按旧手册分别运行 `npm … run build` 和 `build_bundle.py`。

脚本不生成前端。它直接打包 `packages/capabilities/dataagent-workbench/src/dataagent_workbench/static/` 里已有的产物；该目录当前不在版本库中，新检出如果缺少 `static/index.html`，先执行一次前端构建（需要已安装的 Node 依赖），再运行 `prepare_acceptance.sh`：

```sh
npm --prefix packages/capabilities/dataagent-workbench/web run build
```

前端构建是否应并入 `prepare_acceptance.sh` 或改为提交静态产物，待确认。

### 1.2 创建 Mint 测试项目

准备已缓存的 Mint Core、界面制品和 uv 依赖。`mint add` 使用刚生成的本地 `preset-intake`。

```sh
export PATH="$HOME/.mint/bin:$PATH"
export MINT_NET_OFFLINE=1
export DATAAGENT_TEST="$(mktemp -d "${TMPDIR:-/tmp}/dataagent-mint.XXXXXX")"
cd "$DATAAGENT_TEST"
mint init --no-preset --offline -y
mint add "path:$DATAAGENT_CHECKOUT/build/local/preset-intake" --offline -y

DATAAGENT="./.mint/packages/dataagent/cli@0.1.0/bin/dataagent"
"$DATAAGENT" setup
```

`setup` 对已安装的各层执行 `uv sync --frozen`。`doctor` 的期望值见 §1.4。

### 1.3 安装本机 OCR（扫描件需要）

跳过本节时，文件、SQLite 和 REST 仍可用；扫描 PDF 会在预览时报 OCR 未配置。OCR 由单独的 `dataagent-ocr` 命令生成一个验证过的目录，再由 `dataagent setup --ocr-root` 装进项目。`prepare_acceptance.sh` 已为仓库内的 `dataagent-ocr` 创建 `.venv`。

```sh
export OCR_STAGE="$HOME/.dataagent/ocr-rapidocr"
OCR="$DATAAGENT_CHECKOUT/packages/capabilities/dataagent-ocr/.venv/bin/dataagent-ocr"

"$OCR" --data-root "$OCR_STAGE" engine plan rapidocr
# 退出码 3，输出 plan_digest；把步骤、包和磁盘占用给用户看，确认后继续
"$OCR" --data-root "$OCR_STAGE" engine install rapidocr --confirm "<plan_digest>"
"$OCR" --data-root "$OCR_STAGE" configure-engine --engine rapidocr
"$OCR" --data-root "$OCR_STAGE" verify --profile rapidocr

"$DATAAGENT" setup --ocr-root "$OCR_STAGE/ocr"
```

- `engine plan` 只出计划，不安装；`engine install` 需要 `--confirm` 的摘要与计划一致。首次安装要从包索引或预热的 uv 缓存取得 `rapidocr-onnxruntime`。
- `configure-engine` 写 profile，`verify` 用内置探针测试并固定；固定后 `$OCR_STAGE/ocr/active.json` 指向该 profile。
- `setup --ocr-root` 复制整个验证目录到项目的 `.dataagent/ocr`，幂等；目标已有不同固定时拒绝替换，换引擎仍走 `dataagent-ocr verify`。
- 已有验证过的目录（含 `active.json`、引擎和验证记录）时，只需在项目里执行最后一条 `setup --ocr-root <目录>`。

### 1.4 doctor 的期望值

```sh
"$DATAAGENT" doctor; echo "exit=$?"
```

未配置 OCR 时退出码是 **3**，stderr 包含：

```text
ocr:      none (run: dataagent setup --ocr-root <verified ocr dir>, or dataagent-ocr configure + verify)
doctor: failing checks above (exit 3)
```

这是「还没装 OCR」的失败检查，不是安装失败。配置 OCR 后，同一位置变为：

```text
ocr:      engine rapidocr version=1.4.4 verification=ocrv-...
```

退出码为 0。

`doctor` 还检查连接清单、每个凭据逻辑名、当前工作区服务、policy 和 enforcement 模式。连接或凭据缺失、凭据权限不对时同样退出 3，并给出修复提示；它只报有无，不输出凭据值。本预设不安装 governance 层，`policy` 行显示 `local-owner workspace only` 不算失败。

### 1.5 追加项目沙箱片段

`mint add` 只合并预设的 `[packages]`、`[ui]` 和 `[policy]`，不会合并 `[core.sandbox]` 与 `[rules]`。项目级沙箱必须手动追加一次：

```sh
if ! grep -q '^\[core.sandbox\]' mint.toml; then
  cat .mint/packages/dataagent/preset-intake@*/sandbox.toml >> mint.toml
fi
```

片段设置 `workspace-write` 和 `deny_paths`（`.dataagent/secrets/`、`.mint/config.toml`、`.mint/credentials.toml`、`credentials.toml`）。它只能收紧用户已有的策略，不能扩大授权；用户策略是只读时，项目仍不能写 `.dataagent`。`workspace-write` 给整个工作区写权限，不按路径过滤；新凭据默认放在项目外的 `$HOME/.dataagent/secrets`。

## 2. 审批

默认审批下，Mint 会逐个询问 DataAgent 的工具调用，只读工具也会问。这是已知限制 G1.5 / IF-01，M1 不修：

- TUI 交互使用时逐个确认；无人值守时会超时拒绝 DataAgent 工具，任务停在第一次 `intake_start` 或 `intake_advance`。
- `mint chat -y` 的 `-y` 只跳过能力确认和信任门，不跳过工具审批。
- `mint run --json -y --approve all` 会放行全部工具（包括 shell），只用于脚本化证据采集，不要作为真实用户的操作方式。
- 在 `mint.toml` 追加 §1.5 的沙箱片段后，受保护路径的读取会被拒绝；被拒时不要换 shell、换工具或换路径重试。

## 3. 从 TUI 或 GUI 操作

```sh
cd "$DATAAGENT_TEST"
mint model status --offline
mint chat --offline -y
```

真人用自然业务话术即可触发 `dataagent-intake` 技能。先发这条：

> 这是我们这个月的采购发票，帮我接进来。发票号、币种照原样，金额表里是分，帮我换成元。先给我看核对页，我确认了再保存。

在工作台核对 `INV-001` 为 1260 CNY、`INV-002` 为 900 CNY。点击「保存接入」，或在聊天明确确认保存当前映射。成功后任务为 `saved`，有 `release` 引用。将返回的任务 ID 赋给 `SESSION_ID`，用下列命令查询或重新打开同一任务。

```sh
"$DATAAGENT" workbench list
"$DATAAGENT" workbench status "$SESSION_ID"
"$DATAAGENT" workbench view "$SESSION_ID"
"$DATAAGENT" workbench stop
```

`workbench list` 列出本工作区的任务、阶段和发布引用；`status` 读任务状态；`view` 启动（如未运行）并请服务端打开同一任务的页面；`stop` 停止本工作区服务。需要手动起服务或固定端口时用 `"$DATAAGENT" workbench serve --port 8765`。

工作台未认证时首页是「打开本地工作台」。按钮会让服务端用默认浏览器打开带 `#nonce=` 的一次性链接，nonce 60 秒过期；该链接只在当前机器有效。按钮只发请求，不保证浏览器真的打开：

- 没有默认浏览器、在远程机器或通过 SSH 使用时，统一 CLI 的 `dataagent` 分发器会清掉 `BROWSER`，不能靠 `BROWSER=... "$DATAAGENT" workbench serve` 打印链接。按[本机手册 §3](local-offline-quickstart.md#3-打开本地工作台)用安装目录里的 workbench 解释器直接启动同一个服务，把带 nonce 的链接打印出来；链接 60 秒内有效，过期后重新点一次。
- `workbench view` 返回的 `url` 不带 nonce，不能当认证链接复制；当前也没有直接打印一次性链接的 CLI 命令（FDE-15 待补）。

SQLite 发现任务可直接发起：

> 这是我们销售系统的数据库，帮我看看客户、订单和明细，整理成一套资料草案。先给我审，不要直接保存。

REST 先按[测试连接](offline-input-cases.md#数据库和-api-输入)在工作区根目录配置 `source-connections.json`，再在聊天里引用连接 ID：

> 财务系统的发票接口也接进来，和刚才两份表对一下三边账。连接叫 accounting，先别保存，等我核对。

## 4. 保存被拦怎么办

`mapping_apply` 返回 `preview contains unresolved issues` 时，先看 `intake_propose` / `mapping_preview` 里的 `issues`、`disposition_options` 和每条 issue 的 `actions`。真实处置只有下面几类，工作台网页没有「标记空白页」「排除整页」按钮：

| 现象 | 处置 | 参数 |
| --- | --- | --- |
| 空白页或读不到的分区（`ontology.incomplete_source`） | `intake_dispose`，`action="partition_not_applicable"` | `session_id`、最新 `expected_revision`、`source_id`、`partition`、`reason` |
| 被误当成记录的表头行或明显无关的记录 | `intake_dispose`，`action="exclude_record"` | `session_id`、`expected_revision`、`source_id`、`record`（0 起，取 issue 的 `row`）、`reason` |
| 缺键记录（`candidate:`）挡住整批保存 | `mapping_apply` 的 `allow_partial=true`，缺键记录单列；不要它时逐条 `exclude_record` | `decision` 不带 `changes`，顶层 `allow_partial` 和 `reason` |
| 冲突值、必填缺失 | 打开 `workbench view`，在对象页纠正当前值 | 对象页选「纠正当前对象的值」，填属性、值、原因，保存后重新校验 |
| 只想先保存无问题对象 | 同 `allow_partial` | 只发布 `saved`；`suspended` 和 `unidentified_records` 不发布 |

- `intake_dispose` 的 `reason` 必填，写入审计；处置后预览失效，用返回的 `session_revision` 重新 `intake_propose` / `intake_propose_sources` 生成新预览。
- `allow_partial` 只在至少有一个无阻断对象、且没有全局阻断（例如未处置的分区缺口）时生效；否则整批仍被拦。
- 网页可纠正当前值、修订这类来源的映射或提本体草案，但没有「标记空白页」「排除整页」按钮。纠正后的最新修订用 `intake_status` 或 `mapping_preview` 重新取，不要沿用旧 `preview_ref`。
- issue 没有 `actions`、`disposition_options` 也没有对应项时，直说没有这项处置；不要编造入口。

完整的报错、参数和预期结果见[保存被拦的处置](offline-input-cases.md#保存被拦怎么办)。

## 5. GUI

在项目目录用 `mint gui`：

```sh
cd "$DATAAGENT_TEST"
mint gui -y
```

`mint gui` 等于 `mint chat --ui mint/gui`，使用 cpmrt 非 Kernel 布局；首次会安装 `mint/gui`（离线运行需要已有缓存或联网），启动后能看到 DataAgent 的 MCP 工具。工具数以当时实测为准：`gui-channel-check.md` 当时记录 80 个、DataAgent 56 个；当前 `tool_schema.py` 为 16 个。

不要用打包版 `Mint Agent.app` 做接入验收：它的 `kernel-stdio-v1` 布局只装配少量内建工具，技能能加载，但 DataAgent 的 MCP 工具不可见（IF-13）。核实记录见[打包桌面版 GUI 工具通道核实](gui-channel-check.md)。

## 6. 无本机模型时验证安装和工具

从工作树运行。每次创建独立 Mint 项目。固定提案由验收脚本提交。

```sh
cd "$DATAAGENT_CHECKOUT"
export OCR_ROOT="$HOME/.dataagent/ocr-rapidocr/ocr"
bash scripts/verify_local.sh --phase bootstrap
bash scripts/verify_local.sh --phase discovery
```

`scripts/verify_local.sh` 的六个阶段（`bootstrap`、`files`、`sources`、`discovery`、`api-workflow`、`mixed-workflow`）都会先执行 `bootstrap.prepare`，所以每个阶段都必须先装好验证过的本机 OCR，并 `export OCR_ROOT` 指向 `.../ocr`；脚本还会断言 `doctor` 有 `ocr: ... version=` 行。未设置 `OCR_ROOT` 会在 `bootstrap.prepare` 直接抛 `RuntimeError`。`files` 阶段另加 `--ocr-root "$OCR_ROOT"`，它只供扫描用例，不能替代 `OCR_ROOT`；`可跳过 OCR` 只适用于不跑验收脚本的手工试用。`discovery` 输出 `project`、`session_id` 和报告路径。进入输出中的项目，运行项目内的 DataAgent CLI `workbench view` 打开待审核草案。文件、连接和工作流的单项检查见[测试用例](offline-input-cases.md)。

已验证离线装包、安装产物上的 SQLite 固定草案和工作台审核。SQLite 的真实模型提案和 Mint 原生 GUI 的端到端操作待验收。
