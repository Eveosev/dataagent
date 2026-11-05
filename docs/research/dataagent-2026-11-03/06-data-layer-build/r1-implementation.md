---
round: 1
date: 2026-11-03
updated: Round 4.3（测试计数、冷启动）
plan: ../06-data-layer-build-plan.md
---

# 实现基线

## 1. 落地范围

| 项 | 结果 |
|-|-|
| `dataagent-contracts` | 36 个类型（34 个具体 + `CapabilityResult<T>`、`Assessment<V>` 2 个泛型绑定）；13 个枚举（10 封闭 + 3 开放）；111 个测试通过；`scripts/generate_schema.py --check` 生成 66 个 schema |
| `dataagent-data` | 32/32 个 S0 原子注册；11 个实现模块；187 个测试通过；MCP `tools/list` 返回 32 个工具 |
| 族分布 | 骨干 9、判定族 14、计算族 9；运行时按总 Catalog 的 `s0_family` 硬校验 |
| 入口 | MCP：标准库 NDJSON JSON-RPC（`initialize` / `tools/list` / `tools/call`）；CLI：`python -m dataagent_data.interfaces.cli <operation>` |
| 存储 | 内容寻址文件库；SQLite 版本库（显式 revision、乐观并发）；SQLite append-only 轨迹（cursor、`event_id` 去重、checkpoint digest） |
| 打包 | `mint.toml`、`.mcp.json`、两个 Skill、`packaging/source-ref.toml`、`packaging/bundle/` 自包含 staging + `uv.lock` |

## 2. 环境基线

| 项 | 值 |
|-|-|
| 系统 | macOS（arm64） |
| Python | 3.12.14（`uv` 管理的 CPython）；包声明 `>=3.11,<3.14`，bundle 锁文件解析到 3.13.15 |
| uv | 0.12.17 |
| pydantic | 2.14.x |
| 内核 | `agent-kernel@f0fa521`（方案基线；本次未修改内核） |

## 3. 验证命令与结果

```text
# 契约包
cd packages/capabilities/dataagent-contracts
uv run --frozen pytest -q                 # 111 passed
uv run --frozen python scripts/generate_schema.py --check   # schema OK: 66 files（另加 index.json）

# 数据层
cd packages/capabilities/dataagent-data
uv run --frozen pytest -q                 # 187 passed
uv run --frozen python scripts/export_catalog_snapshot.py --check  # 32 atoms
uv run --frozen python -m dataagent_data.interfaces.cli --list     # 32 operations

# MCP 黑盒（含 initialize / tools/list / tools/call / 坏 JSON / 缺 context）
uv run --frozen python -m pytest tests/test_interfaces.py -q   # 11 passed

# Mint bundle
uv run python scripts/build_bundle.py
find packaging/bundle -name '*.pyc' | wc -l     # 0；staging 共 69 个文件
uv run --frozen --project packaging/bundle python -m dataagent_data.interfaces.mcp_server
#   → tools/list = 32
cd packaging/bundle && mint publish --dry-run   # 0，生成 dataagent-data-layer-0.1.0.mint.tar.zst

# 冷启动（bundle 拷贝、无 .venv、UV_CACHE_DIR 为空）
UV_CACHE_DIR=$(mktemp -d) ...                    # initialize + tools/list = 19.1s（Round 3 历史值；Round 4 隔离安装实测见 r4-fixes.md）

# Wheel 安装（不依赖源码树）
uv build --wheel --out-dir /tmp/dawheels          # contracts 与 data 各一个
uv venv -p 3.12 /tmp/davenv
uv pip install --python /tmp/davenv/bin/python /tmp/dawheels/*.whl pydantic openpyxl pdfplumber
cd /tmp && echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | /tmp/davenv/bin/python -m dataagent_data.interfaces.mcp_server
#   → tools = 32（快照随 wheel 发布，不读 docs/ 或仓库兄弟目录）
```

## 4. 与方案的差异

| 差异 | 理由 |
|-|-|
| `Issue.inference_request` 为新增字段 | 原 `Issue` 只有 `suggested_action` / `alternatives`，无法稳定承载候选锚点、目标 schema 与词表；已回写 05 §3.3，属向后兼容的可选字段 |
| Catalog 计数为 9/14/9 | 总 Catalog 的 `s0_family` 与逐项枚举一致；方案原表的 8/10 是笔误 |
| 契约类型计数写作“36 = 34 具体 + 2 泛型” | 与 05 §3.2 一致；方案曾出现“35 named + 2”的表述，已按实现校准 |
| 运行时读打包快照而非研究文档 | bundle 不包含 `docs/`；快照由 `export_catalog_snapshot.py` 从总 Catalog 生成，`--check` 防止漂移 |
| Bundle 采用 staging + vendoring | 路径依赖在单目录 bundle 中不可解析；`scripts/build_bundle.py` 把 `dataagent_contracts` 一并装进 staged 项目，并重写为普通依赖集 |
| `Measure.field_ref` 存字段名而非 `field_id` | 与 05 的 `Measure` 设计一致；`available_fields` 也以名称为契约，映射到物理列由抽取/画像层负责 |
| `classify_table_rows` 等输出含 `issues` 但不改 `TableRef` | 行角色是派生产物；`TableRef` 仍指向原始表，角色通过结果返回，避免内容寻址对象被就地修改 |
