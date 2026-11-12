---
version: 2
date: 2026-11-12
dataagent_commit: 1683409
kernel_commit: e40b1fee696d2d82ac98c9534e5fc24f66678c0a
mint_cli: 0.1.30
---

# Mint 离线安装与操作

Mint 路径从 TUI 或原生 GUI 发起任务，DataAgent 工作台用于查看来源和审核。同一任务共享 Mint 项目目录。模型推理需要可用的本机端点。只想手工探查和映射时，使用[本机工作台手册](local-offline-quickstart.md)。

## 1. 创建 Mint 测试项目

准备已缓存的 Mint Core、对应的界面制品和 uv 依赖。安装使用工作树的本地 `preset-intake`。需要重建制品时，执行[本机手册的构建命令](local-offline-quickstart.md#1-准备本地组件)。

```sh
export DATAAGENT_CHECKOUT="$HOME/Vibe/AgentOS/.worktrees/dataagent-local-intake"
export PATH="$HOME/.mint/bin:$PATH"
export UV_OFFLINE=1 MINT_NET_OFFLINE=1
if [ -d /private/tmp/dataagent-uv-cache ]; then
  export UV_CACHE_DIR=/private/tmp/dataagent-uv-cache
fi

export DATAAGENT_TEST="$(mktemp -d "${TMPDIR:-/tmp}/dataagent-mint.XXXXXX")"
cd "$DATAAGENT_TEST"
mint init --no-preset --offline -y
mint add "path:$DATAAGENT_CHECKOUT/build/local/preset-intake" --offline -y

DATAAGENT="./.mint/packages/dataagent/cli@0.1.0/bin/dataagent"
"$DATAAGENT" setup
"$DATAAGENT" doctor
```

`doctor` 应报告 `data-layer`、`workbench`、`operations` 环境均为 `ok`。按[测试用例](offline-input-cases.md#准备测试输入)把样例放入该项目。

## 2. 从 TUI 或原生 GUI 操作

```sh
cd "$DATAAGENT_TEST"
mint model status --offline
mint chat --offline -y
```

原生 GUI 使用 `mint chat --gui --offline -y`，在界面中打开当前测试项目。两种入口均在发送消息前选好本机模型端点。`mint model status --offline` 检查 Mint 托管部署，用户自行运行的本机端点以实际配置为准。

文件映射可先发这条消息。

> 请用 dataagent-intake 接入当前目录的 invoices.csv，映射到采购资料 Ontology。number 和 currency 原样保留，amount_minor 从分转成元。请生成预览并打开同一任务的工作台，等我核对。

在工作台核对 `INV-001` 为 1260 CNY、`INV-002` 为 900 CNY。点击「保存接入」，或在聊天明确确认保存当前映射。成功后任务为 `saved`，有 `release` 引用。将返回的任务 ID 赋给 `SESSION_ID`，用下列命令查询或重新打开同一任务。

```sh
"$DATAAGENT" workbench status "$SESSION_ID"
"$DATAAGENT" workbench view "$SESSION_ID"
```

SQLite 发现任务可直接发起，或粘贴工作台的「复制指令」继续同一任务。

> 请用 dataagent-intake 从当前目录的 sales-discovery.db 发现本体。根据证据提出实体、每行粒度、标识、属性和关系。区分数据库声明的关系和观测值匹配的候选，打开工作台等我审核。

工作台「确认当前草案」保存发现草案与审核决定。测试 PostgreSQL 和 REST 时，在启动 Mint 前设置[测试连接](offline-input-cases.md#数据库和-api-输入)，在聊天中引用连接 ID。

## 3. 无本机模型时验证安装和工具

从工作树运行。每次创建独立 Mint 项目。固定提案由验收脚本提交。

```sh
cd "$DATAAGENT_CHECKOUT"
bash scripts/verify_local.sh --phase bootstrap
bash scripts/verify_local.sh --phase discovery
```

`discovery` 输出 `project`、`session_id` 和报告路径。进入输出中的项目，运行项目内的 DataAgent CLI `workbench view` 打开待审核草案。文件、连接和工作流的单项检查见[测试用例](offline-input-cases.md)。

已验证离线装包、已安装工具提交 SQLite 固定草案、工作台审核。SQLite 的真实模型提案和 Mint 原生 GUI 的端到端操作待验收。
