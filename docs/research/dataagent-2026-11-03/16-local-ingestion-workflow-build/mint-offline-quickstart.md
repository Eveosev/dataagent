---
version: 1
date: 2026-11-11
dataagent_commit: e22eaac
kernel_commit: c6b049e0691828df71cec376a2c4c1d793b37529
mint_cli: 0.1.30
mint_core: 0.1.47
---

# DataAgent 本机离线安装与使用

先用合成 CSV 在工作台跑通「识别 → 探查 → Ontology 映射 → 核对证据 → 保存」。组件由 Mint 离线安装，手工核对和保存可在本机浏览器完成。要从 Mint 聊天自动提出映射，再接入可用的模型。

## 1. 在新目录离线装包

从 Mac 终端运行。当前 DataAgent 工作区已经生成 `build/local/preset-intake`，使用本机已有的 Mint Core、Python 和 uv 缓存。

```sh
export DATAAGENT_CHECKOUT="$HOME/Vibe/AgentOS/.worktrees/dataagent-local-intake"
export PATH="$HOME/.mint/bin:$PATH"
export UV_OFFLINE=1

# 当前 Mac 的验收使用这份 uv 缓存，缓存移走后改为实际位置。
if [ -d /private/tmp/dataagent-uv-cache ]; then
  export UV_CACHE_DIR=/private/tmp/dataagent-uv-cache
fi

DATAAGENT_TEST="$(mktemp -d "${TMPDIR:-/tmp}/dataagent-offline.XXXXXX")"
cd "$DATAAGENT_TEST"

mint init --no-preset --offline -y
mint add "path:$DATAAGENT_CHECKOUT/build/local/preset-intake" --offline -y

DATAAGENT="./.mint/packages/dataagent/cli@0.1.0/bin/dataagent"
"$DATAAGENT" setup
"$DATAAGENT" doctor

FIXTURES="$DATAAGENT_CHECKOUT/packages/capabilities/dataagent-scenarios/fixtures/intake"
cp "$FIXTURES/invoices.csv" "$FIXTURES/invoice.pdf" .
printf '测试目录 %s\n' "$PWD"
```

`doctor` 应显示 `data-layer`、`workbench`、`operations` 三个环境均为 `ok`。记下测试目录，后续回到同一目录即可读取任务。

## 2. 无外网、无模型时测试工作台

在刚才的测试目录启动工作台。

```sh
"$DATAAGENT" workbench serve --port 8765
```

在本机浏览器访问 `http://127.0.0.1:8765`，点击「打开本地工作台」。在打开的页面按以下步骤操作。

1. 接入目标填写「核对合成采购发票，金额从分转换为元」，选择测试目录中的 `invoices.csv`，点击「开始接入」。
2. 来源探查完成后，将 `number`、`currency` 绑定到同名字段。将 `amount` 的来源字段选为 `amount_minor`，转换方式选「分 → 元（÷100）」。
3. 点击「生成映射预览」。核对两个对象 `INV-001` 和 `INV-002`，金额分别为 `1260 CNY`、`900 CNY`。点击 `amount` 可核对原值和来源行。
4. 点击「保存接入」，确认显示「接入已保存」。刷新页面复核结果。按 `Ctrl-C` 停止前台服务，后续从同一测试目录重启可继续查看持久任务。

接着用 `invoice.pdf` 新建一次接入，按相同方式映射。在金额行核对第 1 页原图高亮，展开「查看文本与精确位置」，核对原值 `126000` 和转换值 `1260`。

需要回到已知任务时，在测试目录执行 `"$DATAAGENT" workbench status <任务ID>` 或 `"$DATAAGENT" workbench view <任务ID>`。浏览器地址中的 `#session=` 后是任务 ID。

## 3. 从 Mint TUI 发起同一类任务

在测试目录打开 Mint TUI。

```sh
mint chat --offline -y
```

`--offline` 让 Mint 使用已缓存的包与 Core。完全断网时，发送消息前确认已配置可用的本机模型端点。可用 `mint model status --offline` 查看 Mint 管理的本地模型服务。本次检查显示暂无托管部署，离线启动 TUI 已复验，断网模型推理待验收。

本机模型就绪后，可将以下文字粘贴到 TUI。

> 请用 dataagent-intake 接入当前目录的 invoices.csv，映射到采购资料 Ontology。number 是单据编号，amount_minor 是分，转换为元，currency 原样保留。先探查并生成预览，打开同一任务的工作台，等我确认后保存。

核对后告诉 Agent「确认保存当前预览，返回任务 ID、最终状态和发布引用」。成功时任务状态为 `saved`，并有 `release` 引用。同结构再次接入可验证映射复用。Mint 官方桌面 GUI 的完整接入流程待验收。

## 4. 从 SQLite 发现本体

在离线安装后的测试目录创建合成库。

```sh
sqlite3 sales-discovery.db < "$FIXTURES/sales-discovery.sql"
```

在工作台上传 `sales-discovery.db`，填写业务目标，选择「从数据库发现本体」，开始接入。展开「来源证据」查看 `party`、`doc_hdr`、`doc_line` 的键、字段类型和样本。关系证据应包含数据库声明的明细 → 订单复合外键，以及观测值匹配的订单 → 客户候选。

同一 Mint 工作区的本机模型就绪后，将工作台的「复制指令」结果发送给 TUI 或 Mint GUI。也可从 Mint 直接发起任务。

> 请用 dataagent-intake 从当前目录的 sales-discovery.db 发现本体。根据来源证据提出实体、每行粒度、标识、属性和关系。提交草案并打开同一任务的工作台，等我审核。

工作台会自动显示草案及待核对项。核对来源表和字段后点击「确认当前草案」或「退回草案」。确认保存草案和审核记录。

无本机模型时，从 DataAgent 工作区运行以下命令。它离线装包并用固定提案走同一工具校验链。用输出中的 `project` 和 `session_id` 打开待审核草案。

```sh
cd "$DATAAGENT_CHECKOUT"
MINT_NET_OFFLINE=1 UV_OFFLINE=1 bash scripts/verify_local.sh --phase discovery
cd <输出中的 project>
./.mint/packages/dataagent/cli@0.1.0/bin/dataagent workbench view <输出中的 session_id>
```

## 5. 扩展测试

在 DataAgent 工作区运行下列脚本。每个阶段创建独立的临时 Mint 项目，输出 JSON 证据路径。

```sh
cd "$DATAAGENT_CHECKOUT"
export MINT_NET_OFFLINE=1 UV_OFFLINE=1
bash scripts/verify_local.sh --phase bootstrap
bash scripts/verify_local.sh --phase api-workflow
bash scripts/verify_local.sh --phase mixed-workflow
```

| 想验证的场景 | 入口与前提 |
| --- | --- |
| Excel、JSON | 上传样例目录中的 `invoices.xlsx` 或 `invoices.json`，核对工作表单元格或 JSON Pointer |
| SQLite | 在工作台上传 `.sqlite`、`.sqlite3` 或 `.db` 文件，再核对表、字段与主键证据 |
| PostgreSQL 与分页 REST | 配置 [宿主连接](../../../../packages/capabilities/dataagent-workbench/README.md#来源连接)，从工作台选择连接。组合验收用 `bash scripts/verify_local.sh --phase sources --postgres-locator "$LOCAL_TEST_POSTGRES"`，需要按[验收记录](implementation-2026-11-11.md)准备本机测试表及只读角色 |
| 扫描 PDF | 已固定并验证本地 RapidOCR 后，运行 `bash scripts/verify_local.sh --phase files --ocr-root "$LOCAL_OCR_DIR"`。期望得到 `INV-003`、`1260.00 CNY` 及原文证据 |
| API 报销和回执恢复 | `api-workflow` 自动启动本地合成业务系统，独立核验单据进入 `waiting_approval` |
| API 超时后的浏览器对账 | `mixed-workflow` 使用本机 Node、Playwright 与 Chrome，核对同一业务键，确认提交仅派发一次 |

## 6. 常见问题

| 现象 | 检查方式 |
| --- | --- |
| 缺少本地 preset 或要重新构建 | 在 DataAgent 工作区运行 `npm --prefix packages/capabilities/dataagent-workbench/web run build`，再运行 `UV_OFFLINE=1 python3 packages/capabilities/dataagent-workbench/tools/build_bundle.py --out build/local`。前端构建使用工作区已有的 Node 依赖 |
| `setup` 报离线缓存缺包 | 检查当前终端的 `UV_CACHE_DIR` 与本地 Python 环境。缺少的锁定依赖需先准备到缓存，再重试 |
| 工作台端口已占用 | 将启动命令中的 `8765` 改为未占用的端口，并用同一端口访问 |
| 浏览器要求重新进入工作台 | 回到环回地址，重新点击「打开本地工作台」。打开已知任务也可用 `workbench view` |
| 扫描件显示需要 OCR | 使用已验证的本地 OCR 目录复跑扫描场景。首轮可继续使用文本 PDF 和 CSV 验证映射 |

全新测试目录已通过离线安装、`setup`、`doctor`、环回工作台健康检查与 TUI 启动。CSV、PDF、多源映射和 SQLite 本体发现均有浏览器回归覆盖，两个本地工作流阶段已通过。Mint CLI 运行版本与内核源码核对基线见文首。iface 同步脚本返回 77 并跳过旧制品检查。
