---
version: 1
date: 2026-11-11
status: 实施中
branch: codex/16-local-intake
---

# 离线安装与链路验收

| 场景 | 验收结果 | 可核对记录 |
| --- | --- | --- |
| Mint 离线安装 | 全新项目安装 preset、数据层、工作台、Operations 和统一 CLI，`setup` / `doctor` 成功 | [包清单](../../../../build/local/manifest.json) |
| Mint TUI CSV | 新建接入和同结构复用均保存，金额 1260 与 900，已保存任务拒绝使用最新修订再次提案 | 会话 `s_269164af7922`，[发布与工具轨迹](../../../../.superpowers/sdd/16-local-ingestion-workflow-build-plan/acceptance/tui-revalidation.json) |
| 扫描 PDF | 本地 RapidOCR 1.4.4 读取 INV-003、1260.00 和 CNY，字段引用 OCR 原文和原页，已保存 | 任务 `acc4b42e20d54e948fad27e9692a39f1`，[安装后验收](../../../../.superpowers/sdd/16-local-ingestion-workflow-build-plan/acceptance/files.json) |
| 工作台审核 | Chrome 完成 CSV、文本 PDF、CSV 与 JSON 合并、双标签页并发。文本 PDF 显示原页高亮，原金额 126000 对应 Ontology 金额 1260。多源行顺序不同仍定位到正确记录 | [浏览器用例](../../../../packages/capabilities/dataagent-workbench/web/tests/mapping.spec.ts)、[审核截图](../../../../.superpowers/sdd/16-local-ingestion-workflow-build-plan/acceptance/mapping-live.png) |
| 跨源接入 | CSV、SQLite、临时 PostgreSQL 和本地分页 REST 对齐为一个 INV-003。REST 第二页 429 后续跑，第一页只读一次。跨源金额冲突保留各方证据并阻止保存 | 任务 `f5a1810c040941ab9cf78d244a35bfd9`，[多源证据](../../../../.superpowers/sdd/16-local-ingestion-workflow-build-plan/acceptance/sources.json) |
| API 报销 | 从 OpenAPI 和已保存 WorkSpec 建立候选并校验。独立查询业务系统得到 `waiting_approval`，建单和提交各派发一次 | 运行 `55d6b20b39734fe583c3b5b8b2b9da7e`，[单据及动作回执](../../../../.superpowers/sdd/16-local-ingestion-workflow-build-plan/acceptance/api-workflow.json) |
| API 与浏览器对账 | 提交已经生效但响应超时，且业务键 API 查询暂时不可用。只读浏览器以可见的业务键及状态确认结果，保留截图和观察修订，提交总派发次数为 1 | 运行 `cc3dcee6551249f78037152a630f810a`，[对账观察](../../../../.superpowers/sdd/16-local-ingestion-workflow-build-plan/acceptance/mixed-workflow.json) |
| Ossie | 使用 `d700cdeac41d15a7004eb2f9b0b38a2b1d517a18` 的三份 schema 离线校验单实体、单数据集交换。复合身份与有序角色参与投影，DataAgent sidecar 保留完整证据与扩展并登记损失 | [交换用例](../../../../packages/capabilities/dataagent-ontology/tests/test_ossie_roundtrip.py) |

安装测试用 Mint CLI 0.1.30，TUI 运行用 Core 0.1.47。内核检查基线为 `agent-kernel@4c6e4fdb1970059b6911fd69ea143e63faa3fad8`，iface 同步检查返回 77 并跳过旧制品检查。实际运行证据对应各报告中的包文件 digest。

## 本地复跑

已生成本地 preset。在新的合成测试目录运行以下命令，`DATAAGENT_CHECKOUT` 指向本工作区。

```sh
mint init --no-preset
mint add "path:$DATAAGENT_CHECKOUT/build/local/preset-intake" --offline -y
./.mint/packages/dataagent/cli@0.1.0/bin/dataagent setup
mint chat -y
```

从 DataAgent 工作区构建产物。前端使用已安装的锁定依赖，Python 使用本机 uv 缓存。

```sh
npm --prefix packages/capabilities/dataagent-workbench/web run build
UV_OFFLINE=1 python3 packages/capabilities/dataagent-workbench/tools/build_bundle.py --out build/local
bash scripts/verify_local.sh --phase bootstrap
bash scripts/verify_local.sh --phase files --ocr-root "$LOCAL_OCR_DIR"
bash scripts/verify_local.sh --phase sources --postgres-locator "$LOCAL_TEST_POSTGRES"
bash scripts/verify_local.sh --phase api-workflow
bash scripts/verify_local.sh --phase mixed-workflow
packages/capabilities/dataagent-workbench/.venv/bin/python scripts/verify_browser.py
```

扫描件使用已通过探针的本机 OCR 目录。数据库场景使用本机临时 PostgreSQL，`invoice` 表包含合成单据 INV-003、金额 1260.00、币种 CNY、日期 2026-11-11，使用拥有表 SELECT 权限的测试角色。浏览器观察和对账使用本机 Node、锁定 Playwright 和 Chrome。正式宿主连接配置见 [工作台](../../../../packages/capabilities/dataagent-workbench/README.md) 和 [Operations](../../../../packages/capabilities/dataagent-operations/README.md)。

## 评审与剩余验收

| 发现 | 修复与复验 |
| --- | --- |
| REST 版本混合和续跑漏行 | 跨页版本不一致停止合并，未验证快照保持部分覆盖，重试使用已保存偏移 |
| 数据库主键名称可覆盖表标识 | 主键字段独立保存在 `primary_key`，表名和 schema 保留 |
| 跨源排序和并发草稿 | 根据字段证据定位来源行，保留本地编辑的基准修订，冲突时提示重新载入 |
| 浏览器请求与业务状态证据 | 路由限制在配置的导航与资源，拒绝重定向和写请求，只采信唯一可见的业务键和状态 |

| 待验收 | 当前边界 |
| --- | --- |
| Mint 官方 GUI | 已安装并打开，实际窗口停在历史工作区；需要从合成测试工作区发起任务、核对 PDF 和保存 |
| 工作流 Agent 验收 | 已装包的 MCP 端口以结构化候选完成真实本机执行；仍需在 Mint 会话中由模型根据业务目标提出候选 |
| Web Computer Use 写入与重规划 | 已验证读取控件、发现必填字段变化和只读对账；仍需绑定并执行浏览器写步骤、登录过期处理和受影响步骤重规划 |
| 交付与数据变体 | 混排和低置信度 PDF、独立业务变体、Mint 双端连接入口及体验指标待验收 |
