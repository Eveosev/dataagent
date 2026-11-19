---
version: 5
date: 2026-11-19
status: M1 验收盘点（最终复跑）
---

# 测试数据与验收场景清单

逐项准备材料、操作和核对结果见[离线输入测试用例](offline-input-cases.md)。

| 里程碑 | 已有证据 | 当前验收状态 |
| --- | --- | --- |
| M1 文件接入 | 离线装包、真实 Mint Agent、Mint TUI 首次接入与复用、Chrome 文件映射、RapidOCR 扫描 PDF；M1 收口复跑安装产物 files 阶段（8 类 + docx）、sources 阶段与浏览器 e2e；S2 门禁修复与 RU1 部分覆盖复用修复；最终复跑 `test_all` 11 个包与五个验收阶段 | 可验收。S2 修复 D1/D2，`verify_browser.py` 在 `7ebf7af0`、`0e16b094` 各连续两次 78 passed、恢复阶段 1 passed、flaky 清单为空；T50 C-01/C-03 已由验收人裁定（C-01-3、C-03-1 关闭；C-01-1、C-01-4 接受为已知限制；C-01-2 安排交互式 TUI 补测；C-03-2 转 RU1 并已合入 `0e16b094`），见 [r1-review](r1-review.md) §0、§7.1；GUI 的 C-01/C-02 待验（非 Kernel 布局 `mint gui` 已可见 56 个 DataAgent 工具，打包版 `Mint Agent.app` 仍为 IF-13 外部阻断）；T54 可记「M1 合入」，验收状态由验收人填写 |
| M2 数据库和 API | CSV、SQLite、PostgreSQL 和分页 REST 对齐并保存，429 断点续跑；M1 收口复跑 sources 阶段 | 已验证（M1 范围）：SQLite、REST token/分页/429、跨源冲突与部分保存通过；Mint GUI 的 C-01/C-02 待 T51 验（打包版 IF-13） |
| M3 API 工作流 | API 环境探查、候选校验、合成报销提交、审批等待和重启恢复 | Mint Agent 根据自然语言形成候选待验收 |
| M4 Computer Use 与交付 | 实际浏览器读取控件、必填项变化、API 结果未知后的只读浏览器对账、Ossie 交换 | 浏览器写入绑定、登录失效后的局部重规划和独立变体验收待完成 |

「已验证」对应本栏所写的入口与范围。「部分通过」表示有正向证据，仍缺验收步骤或存在已发现的问题。「待验证」涵盖已写用例待运行、已有数据待走通和待准备的数据。

## 测试入口

| 入口 | 覆盖范围 |
| --- | --- |
| 各能力包的 `tests/` | 契约、读写边界、规则计算、治理、包内容一致性和各组件行为 |
| M1 后端测试 | `dataagent-data`、`dataagent-workbench`、`dataagent-ontology`、`dataagent-contracts`、`dataagent-runtime`、`dataagent-ocr`、`dataagent-cli` 的 `tests/`：文件与 docx 探查、SQLite/REST 分页与 429 续跑、分段与映射复用、凭据逻辑名、发现/发布/修订/停用、查询、部分保存与处置 |
| M1 浏览器 e2e | `packages/capabilities/dataagent-workbench/web/tests/` 的 20 个 spec、79 条用例：上传、字段选择、映射修订、对象页纠正、冲突、发现、发布、修订、按本体浏览、坏输入、探查重试、刷新与服务重启恢复；最终 @7ebf7af0、@0e16b094 各连续两次 78 passed、恢复阶段 1 passed、flaky 清单为空；S2 前首轮 1 failed + 1 flaky 的复现记录见 [r1-review](r1-review.md) §2 |
| M1 验收阶段 | `scripts/verify_local.sh` 的 `bootstrap`、`files`、`sources`、`discovery`、`ontology`：安装产物、8 类文件、跨源、发现证据、D0–D7 全链 |
| 验收脚本单测 | [`scripts/acceptance/tests/test_ontology.py`](../../../../scripts/acceptance/tests/test_ontology.py)：D7 报告解包、原因过滤、日期比较与打分辅助 |
| [S0 跨层场景](../../../../packages/capabilities/dataagent-scenarios/README.md) | 授权复检、判定、计算和验收报告 |
| [本地装包验收](../../../../scripts/verify_local.sh) 与 [浏览器验收](../../../../scripts/verify_browser.py) | 多源接入、Ontology 映射审核、工作流和浏览器对账 |
| [Benchmark 自测](../09-benchmark/harness/README.md) | 评分口径、金标回填、扰动和评分报告 |

已删除 4 个引用迁移前路径的历史探针、3 个重复正式用例和 1 条恒真断言。无授权拒绝、SQL 正向执行、治理守恒判定和包内容一致性的断言继续由现有用例覆盖。历史探针及其输出可从原评审记录和提交 `fbe24d8` 查阅。

清理后复跑 Runtime 115 项、应用层 201 项、治理层 123 项和 S0 跨层 12 项，全部通过。三个既有 bundle 已同步 `environment.py` 与 `workflow.py`，打包契约与源码逐文件一致。

### M1 新增测试（2026-11-19 登记）

最终复跑（@0e16b094）：11 个包全部通过；RU1 新增 8 条工作台用例后 workbench 385 项全部通过。S2、RU1 合入前的收口复跑为 1975 passed、2 skipped、3 warning，分项：application 201、cli 39（另 2 skipped）、contracts 134、data 735、governance 123、ocr 45、ontology 40、operations 27、runtime 229、scenarios 25、workbench 377。跳过项是需要真实 Mint/宿主凭据的用例。

| 类型 | 文件 | 覆盖 |
| --- | --- | --- |
| 文件与 docx | `dataagent-data/tests/test_file_profiles.py`、`test_documents.py`、`test_docx_profiles.py`、`test_docx_record_sets.py`、`test_ingestion.py` | 8 类格式、docx 正文/表格、锚点、坏输入、字节上限 |
| SQLite/REST/续跑 | `test_database_rest.py`、`test_segment_resume.py`、`test_cli_credentials.py`、`test_bundle_dependencies.py` | 复合键、分页/429、30 MB 分段、凭据逻辑名、安装产物依赖 |
| 映射与复用 | `dataagent-workbench/tests/test_proposal_loop.py`、`test_scan_reuse_changed.py`、`test_multi_concept_target.py`、`test_intake_repairs.py`、`test_reuse_partial.py` | 单/多来源复用、部分失败不伪复用、扫描件变化、多概念目标、修订、部分覆盖来源复用 |
| 处置与部分保存 | `test_disposition_tools.py`、`test_partial_save.py`、`test_intake_source_fit.py`、`test_disposition_types.py` | 来源级处置、部分保存、来源与概念不符、处置类型、分区号整数归一 |
| 发现/发布/修订/查询 | `dataagent-workbench/tests/test_ontology_discovery.py`、`test_publish_gate.py`、`test_revision_publish.py`、`test_query.py`、`test_query_http.py`；`dataagent-ontology/tests/` | D0–D7 主链、人工确认门禁、修订、停用回退、查询 |
| 浏览器 e2e | `dataagent-workbench/web/tests/*.spec.ts`（20 个文件、79 条用例） | 上传、映射、对象页、冲突、发现、发布、修订、浏览、坏输入、探查重试、刷新/重启 |
| D7 验收脚本单测 | `scripts/acceptance/tests/test_ontology.py` | D7 报告解包、原因过滤、日期比较与打分辅助；本次 22 passed |

### M1 门禁与复用修复（2026-11-19 登记）

| 卡 | 合入 | 变化 | 验证 |
| --- | --- | --- | --- |
| S2 | `7ebf7af0` | 映射类用例显式 `pinBuiltinOntology`；`bad-input.spec.ts`、`object-issues.spec.ts`、`dispositions.spec.ts` 固定目标；新增 `probe-retry.spec.ts`、`probe-retry-helper.spec.ts` 与 `awaitProbed`/`awaitEvidenceProbed`，重试请求返回前只点击一次；`verify_browser.py` 默认把 flaky 计为失败，`--allow-flaky` 仅本地排查 | 20 个 spec、79 条用例；@7ebf7af0、@0e16b094 各连续两次 78 passed、恢复阶段 1 passed、flaky 清单为空、退出码 0 |
| RU1 | `0e16b094` | 部分覆盖来源也复用已验证映射，缺口照常列为待处置；`tests/test_reuse_partial.py` 7 条，`tests/test_disposition_tools.py` 增 1 条；`scripts/acceptance/sources.py` 的 `_verify_reuse_after_partial` 新增二次接入断言 | sources 阶段断言 `mapping_reused=true`、REST 缺键缺口保留、未自动保存、`mapping_apply` 被预览问题拦截；@0e16b094 复跑通过 |

## 测试数据

### 文件样例

可直接拷贝到临时 Mint 工作区的材料都在 [接入样例目录](../../../../packages/capabilities/dataagent-scenarios/fixtures/intake)。文件和服务样例使用合成业务数据。

| 输入 | 数据内容 | 核对点 |
| --- | --- | --- |
| [invoices.csv](../../../../packages/capabilities/dataagent-scenarios/fixtures/intake/invoices.csv) | INV-001 / 126000 分 / CNY，INV-002 / 90000 分 / CNY | 两个对象金额分别为 1260、900 元，金额能定位到来源记录。已用于浏览器、真实 Mint Agent 和 TUI |
| [invoice.pdf](../../../../packages/capabilities/dataagent-scenarios/fixtures/intake/invoice.pdf) | 文本 PDF，INV-001 / 126000 分 / CNY | 单据编号、金额、币种和第 1 页定位。HTTP 已实际渲染页图，Chrome 已验证定位和保存 |
| [mixed.pdf](../../../../packages/capabilities/dataagent-scenarios/fixtures/intake/mixed.pdf) | 第 1 页单据编号和金额，第 2 页无文本层，第 3 页币种 | 保留第 1、3 页，报告第 2 页缺口。另需真正混排文本与扫描图像的样本验证 OCR 路由 |
| [scan.pdf](../../../../packages/capabilities/dataagent-scenarios/fixtures/intake/scan.pdf) | 纯图片 PDF，INV-003，1260.00 CNY | 实际 OCR、页与文本证据、映射金额。RapidOCR 已在装包后完成识别、原文引用、映射和保存 |
| [invoices.xlsx](../../../../packages/capabilities/dataagent-scenarios/fixtures/intake/invoices.xlsx) | 单 sheet，2 条记录，中间空行 | 第二条金额定位到 B4。稀疏行定位已有数据层测试，安装后 files 阶段已验证 |
| [invoices.json](../../../../packages/capabilities/dataagent-scenarios/fixtures/intake/invoices.json) | 一条 INV-001，金额字段为字符串 | 保留原值，建立 JSON Pointer。另有根对象、嵌套数组动态样例。安装后 files 阶段已验证 |
| [sales-discovery.sql](../../../../packages/capabilities/dataagent-scenarios/fixtures/intake/sales-discovery.sql) | 两个客户、两张销售单、三条明细 | 已用离线包和 Chrome 核对复合外键、无声明客户关联、草案与待核对项 |
| [expected.json](../../../../packages/capabilities/dataagent-scenarios/fixtures/intake/expected.json) | 文本 PDF、缺页、Excel 单元格、扫描件期望值 | 用于独立核对结果，保留在验收侧 |

### 测试运行时生成的数据

| 数据组 | 数据与变体 | 生成位置 |
| --- | --- | --- |
| 文件结构与故障 | CSV 3 行取 2 行、稀疏 Excel、JSON 根对象和选择数组、两页带线框的 PDF 表格、无文本页、非法 PDF、工作区外路径与符号链接 | [文件探查测试](../../../../packages/capabilities/dataagent-data/tests/observation/test_file_profiles.py) |
| 映射、身份和证据 | 十进制超长金额、复合键、同名异租户、同一对象金额冲突、多元关系及有序角色、必需属性缺失、扩展字段、原值和用户纠正证据 | [契约测试](../../../../packages/capabilities/dataagent-contracts/tests/test_intake_ontology_contracts.py)、[映射测试](../../../../packages/capabilities/dataagent-ontology/tests/test_mapping_semantics.py)、[审核测试](../../../../packages/capabilities/dataagent-ontology/tests/test_review_service.py) |
| 持久任务与并发 | 真实作业、任务修订、过期预览、草稿与 Agent 提案冲突、请求键重复、事务回滚、事件分页、浏览器授权及一次性入口 | [持久存储测试](../../../../packages/capabilities/dataagent-runtime/tests/test_workbench_store.py)、[工作台测试](../../../../packages/capabilities/dataagent-workbench/tests) |
| OCR 引擎 | 内置英文探针图、其期望文本、测试用本地 worker 和 OpenAI 兼容响应替身。涵盖固定版本、凭据缺失、格式错误、质量下降和外发判定 | [OCR 测试目录](../../../../packages/capabilities/dataagent-ocr/tests)、[OCR 实施记录](../13-ocr-build/r1-implementation.md) |
| SQLite | 临时 `data.sqlite`，表 `entries` 使用 `(tenant,n)` 复合键。跨租户同名、NULL、日期、样本范围、表结构变化及第二张 `other` 表 | [数据库与 REST 测试](../../../../packages/capabilities/dataagent-data/tests/observation/test_database_rest.py) |
| REST | 本地 HTTP 动态响应，有限分页、游标分页、嵌套对象和数组、429、500、循环、重定向、未授权地址、版本变化、分页不完整、内存凭据 | [数据库与 REST 测试](../../../../packages/capabilities/dataagent-data/tests/observation/test_database_rest.py) |
| 本地 OA/CRM | 报销 `expense-1`、订单 `po-1`、附件文本和独立 SQLite 状态。可注入新增 `organization`、按钮改名、布局和分页变化、提交成功但响应丢失、审批迟到 | [测试系统](../../../../packages/capabilities/dataagent-scenarios/src/dataagent_scenarios/business_system)、[业务系统测试](../../../../packages/capabilities/dataagent-scenarios/tests/test_business_system_fixture.py) |

### 待准备的验收数据

| 数据 | 最小内容 | 用途 |
| --- | --- | --- |
| 完整 PDF 验收组 | 同一 PDF 含文本页与实际扫描页，一份重复表头的跨页表，一份低置信度数字或旋转页 | 验证逐页路由、表块定位、识别质量、保留成功页及补录 |
| 非规则 Excel | 标题行、合并表头或多表区，另设一个需要用户选择表头的文件 | 验证自动候选、澄清、精确单元格证据 |
| 跨源业务对象组 | PDF、SQLite、PostgreSQL、REST 共享同一单据标识。分别放入同名异对象、冲突金额、时态变化和缺键记录 | 验证身份对齐、冲突保留、复合键和发布结果 |
| 独立业务环境变体 | 独立的无演示数据租户、字段与布局不同的报销和订单配置、提交后可查询的业务键。验收侧持有期望状态和注入开关 | 验证 Agent 依据环境形成和修订流程 |
| Ossie 交换组 | 固定 schema、多元关系、身份约束、未知表达式、实例扩展与证据 sidecar | 验证交换往返、支持范围和逐项损失 |

## 验收矩阵

### M1 文件识别、探查、映射与审核

| 编号 | 场景 | 已有证据 | 通过条件及待补验证 |
| --- | --- | --- | --- |
| M1-01 | 本地装包与任务恢复 | 已验证。本次 bootstrap 复跑：Mint 0.1.31 安装清单 5 个包，doctor 报 data-layer/workbench/operations venv ok、OCR 1.4.4、策略模式与连接状态；安装目录无开发仓路径 | GUI 与完整体验归 T51（C-01/C-02 待验）/T52 |
| M1-02 | 真实 Mint Agent 首次接入 | 已验证（3 份材料任务）。T50 C-01 真实 Mint Agent 会话完成探查、提案、预览、网页纠正和回聊天保存；4 份材料任务在 T50 时被 T50 缺陷 D6/D2 阻断；复跑 @040e8a1b 中网页纠正在重新提案后保留（T50 缺陷 D2 不再复现），混排 PDF 跨页币种的无编号记录仍在，可经现有处置保存（C-01-1 接受为已知限制） | T50 采集于 `f84a514`；复跑在 `$PRIVATE_DIR/t50-rerun/run2/`；GUI 归 T51（C-01/C-02 待验） |
| M1-03 | CSV 浏览器闭环 | 已验证。`verify_browser.py` 的 intake.spec 在真实工作台服务上完成上传、字段选择、分转元、预览、刷新恢复和保存 | 首次预览时间、完成时间、主动操作归 T52 |
| M1-04 | 文本 PDF 来源对照 | 已验证。files 阶段 invoice-lines.pdf 第 1 页 coverage=full、锚点与独立期望一致；T50 C-01 看到原图与高亮 | GUI 同一任务复跑归 T51（C-01/C-02 待验；打包版 IF-13） |
| M1-05 | 扫描 PDF 和混合 PDF | 已验证。files 阶段 scan.pdf 与 mixed-pages.pdf 与期望一致（第 2 页 `ocr_empty`）；RapidOCR 1.4.4 | 真实混排、低置信度数字和扫描框在浏览器的复核归 T51/T52 |
| M1-06 | Excel/JSON 来源接入 | 已验证。files 阶段 Excel/JSON/JSONL/TSV 样本 coverage=full，单元格/JSON Pointer 锚点与期望一致 | 无；安装后接入已由 files 阶段覆盖 |
| M1-07 | 审核与三种修改范围 | 已验证。intake.spec 覆盖三种修改范围；mapping.spec、source-preview.spec 覆盖映射修订 | 浏览器 e2e 门禁缺陷 D1、D2 已由 S2 修复（`7ebf7af0`），@7ebf7af0、@0e16b094 各连续两次 0 flaky，见 [r1-review](r1-review.md) §6；功能路径在复跑中通过 |
| M1-08 | 并发、刷新和重启 | 已验证。intake.spec 覆盖并发修改、过期决定拒绝、服务重启恢复；workbench 单测覆盖事务回滚 | 已复跑：@7ebf7af0、@0e16b094 各连续两次 78 passed、恢复阶段 1 passed、flaky 清单为空 |
| M1-09 | Mint TUI 复用与保存 | 部分通过并已裁定。T50 C-03：单来源与不含扫描件多来源 `mapping_reused=true`；含扫描件组合在复跑中 `mapping_reused=true`（C-03-1 关闭）；T50 C-01 的 3 份材料任务未复用已存映射；交互式 TUI 与终端录屏未验证（C-01-2 接受，安排真人补测） | 交互式 TUI 待真人补测；条件与证据见 [r1-review](r1-review.md) §7.1 |
| M1-10 | Mint GUI | 部分通过。非 Kernel 布局的 `mint gui` 冒烟得到 80 个工具，其中 DataAgent 56 个（workbench 13、data 32、operations 11），与 `mint run` 一致（[gui-channel-check](gui-channel-check.md)）；C-01/C-02 场景未跑。打包版 `Mint Agent.app`（kernel-stdio-v1）看不到工具，仍是 IF-13 | 按 `mint gui` 跑 C-01/C-02 并采证；打包版待 Mint 侧 IF-13 |
| M1-11 | 本地认证与模型披露 | 已验证到组件边界。一次性浏览器入口、跨站请求、任务成员、披露字段过滤有测试；真实会话令牌问题已脱敏，修复后的那次复验会话内未再出现文件/Shell 读取 | 宿主级注入与默认审批归 T51/G1.5；收口前查询抽查仍出现擦边读取（L2），见 [r1-review](r1-review.md) §5 |
| M1-12 | docx 正文与表格 | 已验证。files 阶段 docx coverage=full，正文 `paragraph:2`、表格 `table:1/row:2/col:2` 锚点与期望一致；docx 单测与安装产物依赖测试通过 | 复杂页眉页脚、文本框不在 M1 |
| M1-13 | D0–D7 本体发现全链 | 已验证。ontology 阶段 36 项检查 35 通过、1 不适用（N3.gate），覆盖发现→审核→发布→映射→查询；discovery 阶段覆盖表格/文档证据；真实 Agent TUI 运行见 `$PRIVATE_DIR/d7-agent-run/` | 模型提案质量与 GUI 渲染不在此列；N3.gate 在本次证据下不适用 |

### M2 数据库、API 与跨源对齐

| 编号 | 场景 | 已有证据 | 通过条件及待补验证 |
| --- | --- | --- | --- |
| M2-01 | SQLite 有界读取 | 已验证。sources 阶段复合主键、名称冲突、NULL、范围与锚点同金标一致；T50 C-02 已看来源定位 | GUI 来源定位归 T51（C-01/C-02 待验） |
| M2-02 | PostgreSQL 实库 | 临时 PostgreSQL 只读角色读取复合主键、Decimal 与日期，数据已进入跨源发布 | 在 Mint 双端复核来源定位；PostgreSQL 不在 M1 范围 |
| M2-03 | REST 嵌套与分页 | 已验证。sources 阶段逐页响应、JSON Pointer、分页覆盖与期望一致；T50 C-02 已看来源定位 | GUI 来源定位归 T51（C-01/C-02 待验） |
| M2-04 | REST 中断、恢复与漂移 | 部分通过。已验证范围限于 429 续跑：sources 阶段第 2 页 429 后续跑完成，第 1 页只请求一次，已保存锚点保留 | 游标范围变化、版本变化后的重新探查未验证 |
| M2-05 | 多源身份与冲突 | 已验证。sources 阶段 13 个对象（10 有键 + 3 缺键）、5 个冲突字段落在 4 个对象上，保存被拦；T50 C-02 同路径 | 跨业务域身份与真实混排 PDF 同对象样例留作后续 |
| M2-06 | 来源权限和用户入口 | 部分通过。远端使用宿主连接 ID，拒绝工具参数改写范围；浏览器工作台列出连接名和类型；TUI 发起 SQLite + REST，哨兵 0 命中 | 从 Mint GUI 发起数据库/API 归 T51 待验（非 Kernel `mint gui` 工具可见；打包版 IF-13） |
| M2-07 | 陌生 SQLite 本体发现 | 部分通过。ontology 阶段脚本化提案、人工发布、映射与查询全链通过；TUI 真实模型发现走通；单测覆盖两个等价客户表的歧义 | GUI 从同一证据生成草案归 T51 待验 |

### M3 API 环境探查与持久工作流

| 编号 | 场景 | 已有证据 | 通过条件及待补验证 |
| --- | --- | --- | --- |
| M3-01 | 测试系统基线 | 13 项通过。业务 API、浏览器建单上传提交、审批状态及超时后的独立查询 | 加入独立业务变体 |
| M3-02 | 只读环境探查 | 离线包从 OpenAPI 和读取探针识别当前动作，测试系统业务记录数量保持原值 | Mint Agent 依据观测结果形成候选 |
| M3-03 | 提交报销 | 离线包接受结构化候选并真实执行。独立查询到待审批单据与两条动作回执 | 由 Mint Agent 从自然语言目标生成候选 |
| M3-04 | 远端提交成功但响应丢失 | 本地真实 HTTP 测试覆盖已生效、可靠未生效、部分生效及仍未知。安装后对账确认提交仅派发一次 | 在独立变体复验 |
| M3-05 | 等待、重启与权限撤回 | Operations 测试覆盖重启恢复等待、真实审批结果和撤权阻止下一步 | 在 Mint 会话复验运行恢复 |
| M3-06 | 草案校验与局部修订 | Operations 测试覆盖候选失效、固定目标和保留已执行回执 | 根据用户补充信息和新观察由 Agent 生成新修订 |

### M4 Computer Use、交换与本地交付

| 编号 | 场景 | 已有证据 | 通过条件及待补验证 |
| --- | --- | --- | --- |
| M4-01 | GUI 观察与动作 | 真实 Chrome 可读取已配置表单控件、截图和页面版本。测试系统的独立浏览器用例可建单、上传与提交 | 在工作流中绑定并执行观察驱动的浏览器写步骤 |
| M4-02 | API/UI 混合与未知对账 | 已安装包在 API 查询暂不可用时用只读页面确认同一业务键，提交派发次数为 1 | 扩展到包含浏览器写节点的混合工作流 |
| M4-03 | 页面、接口和登录变化 | 真实浏览器探查能区分必填控件变化的观察修订，API schema 漂移使候选失效 | 登录过期、控件失效及只重规划受影响步骤 |
| M4-04 | 两领域通用性 | 报销通过安装后执行，订单覆盖完整审批等待、重启和受控修订 | 独立未见过变体及 Agent 形成候选 |
| M4-05 | Ossie 往返与扩展 | 固定提交的三份 schema，6 项交换用例通过，sidecar 保留精确值、来源断言和扩展 | 上游转换器和更多外部工具互操作 |
| M4-06 | 独立制品与完整交付 | 全新工作区已通过 bootstrap、files、sources、api-workflow 和 mixed-workflow | Mint GUI、Node 与 Playwright 的跨机安装及完整变体矩阵 |

## 证据入口

| 证据 | 位置 |
| --- | --- |
| 本地安装、Mint 版本和包文件 digest | [bootstrap.json](../../../../.superpowers/sdd/16-local-ingestion-workflow-build-plan/acceptance/bootstrap.json) |
| 真实 Mint Agent 业务结果 | [mint-agent-result.json](../../../../.superpowers/sdd/16-local-ingestion-workflow-build-plan/acceptance/mint-agent-result.json) |
| 实际浏览器映射界面 | [mapping-live.png](../../../../.superpowers/sdd/16-local-ingestion-workflow-build-plan/acceptance/mapping-live.png) |
| 本地 RapidOCR 固定及验证 | [ocr-install-result.json](../../../../.superpowers/sdd/16-local-ingestion-workflow-build-plan/acceptance/ocr-install-result.json)、[ocr-verification.json](../../../../.superpowers/sdd/16-local-ingestion-workflow-build-plan/acceptance/ocr-verification.json) |
| TUI 保存及终态回退 | [tui-state-audit.json](../../../../.superpowers/sdd/16-local-ingestion-workflow-build-plan/acceptance/tui-state-audit.json) |
| T50 复跑与裁定 | `$PRIVATE_DIR/t50-rerun/run2/`：C-01-1、C-01-4 接受为已知限制；C-01-2 安排交互式 TUI 补测；C-01-3、C-03-1 关闭；C-03-2 转 RU1（`0e16b094`）；见 [r1-review](r1-review.md) §7.1 |
| 收口前真实 Agent 查询抽查 | `$PRIVATE_DIR/m1-query-check/`：两问答对；同口径合并问法 23 秒 / 8 步 / 72.6 万 input token；20 行约 21 KB 内联；L1–L4 见 [r1-review](r1-review.md) §4.3 |
| 本地检查入口 | [verify_local.sh](../../../../scripts/verify_local.sh)、[verify_browser.py](../../../../scripts/verify_browser.py) |

内核基线为 `agent-kernel@4c6e4fdb1970059b6911fd69ea143e63faa3fad8`。Mint TUI 复验使用 Core 0.1.47。各入口的实际结果和可复跑命令见 [离线安装与链路验收](implementation-2026-11-11.md)。
