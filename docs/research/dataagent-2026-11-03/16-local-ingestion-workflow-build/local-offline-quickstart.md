---
version: 1
date: 2026-11-12
---

# 本机离线安装与操作

本机路径直接运行浏览器工作台。需要 Python 3.11–3.13、uv、浏览器和已缓存的 Python 依赖。文件、SQLite 和已配置的环回连接可直接探查，采购资料映射可在页面手工完成。

## 1. 准备本地组件

```sh
export DATAAGENT_CHECKOUT="$HOME/Vibe/AgentOS/.worktrees/dataagent-local-intake"
export UV_OFFLINE=1
if [ -d /private/tmp/dataagent-uv-cache ]; then
  export UV_CACHE_DIR=/private/tmp/dataagent-uv-cache
fi

cd "$DATAAGENT_CHECKOUT"
test -f build/local/manifest.json
```

首次准备组件或更新源码后，在工作树执行以下命令。前端构建使用已安装的 Node 依赖。

```sh
npm --prefix packages/capabilities/dataagent-workbench/web run build
python3 packages/capabilities/dataagent-workbench/tools/build_bundle.py --out build/local
```

创建独立测试目录，复制工作台和数据层，按锁文件离线安装。

```sh
export DATAAGENT_TEST="$(mktemp -d "${TMPDIR:-/tmp}/dataagent-native.XXXXXX")"
mkdir -p "$DATAAGENT_TEST/.components"
cp -R "$DATAAGENT_CHECKOUT/build/local/workbench" \
      "$DATAAGENT_CHECKOUT/build/local/data-layer" "$DATAAGENT_TEST/.components/"
uv sync --offline --frozen --project "$DATAAGENT_TEST/.components/workbench"
uv sync --offline --frozen --project "$DATAAGENT_TEST/.components/data-layer"
cd "$DATAAGENT_TEST"
```

## 2. 启动工作台

先按[测试用例](offline-input-cases.md#准备测试输入)准备样例。测试 REST 或 PostgreSQL 时，先按对应步骤配置连接，再启动工作台。

```sh
cd "$DATAAGENT_TEST"
.components/workbench/.venv/bin/python - <<'PY'
from pathlib import Path
import uvicorn
from dataagent_workbench.adapters.layer_client import LayerClient
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.interfaces.http_api import create_app

workspace = Path.cwd()
workbench = Workbench(workspace, layer_client=LayerClient(workspace / '.components/data-layer'))
uvicorn.run(create_app(workbench), host='127.0.0.1', port=8765)
PY
```

打开 `http://127.0.0.1:8765`，点击「打开本地工作台」完成本机认证。选择文件或已配置连接，填写接入目标。先跑 [CSV 基线](offline-input-cases.md#文件输入)，再选择其他用例。

- 采购资料映射先核对来源证据，再生成映射预览。核对编号、金额、币种后点击「保存接入」。
- 陌生 SQLite 库选择「从数据库发现本体」。本机工作台可直接检查结构、样本和关系候选。固定提案的端到端审核可运行下方浏览器用例，模型生成的草案按 [Mint 手册](mint-offline-quickstart.md)提交。

按 `Ctrl-C` 停止服务。下次用同一目录重启，保存浏览器地址中 `#session=` 后的任务 ID 即可恢复任务。需要重新认证时，从工作台首页打开本机入口。

## 3. 本机回归

开发工作树已准备测试依赖时，可运行以下用例。浏览器验收使用本机 Chrome。

```sh
cd "$DATAAGENT_CHECKOUT"
packages/capabilities/dataagent-workbench/.venv/bin/python scripts/verify_browser.py
```

预期覆盖 CSV、文本 PDF、两来源归并、并发映射编辑和 SQLite 发现审核。SQLite 用例通过公开工具提交固定草案，并在 Chrome 确认和刷新复核。
