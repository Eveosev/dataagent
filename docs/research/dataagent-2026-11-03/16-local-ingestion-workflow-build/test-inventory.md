---
version: 1
date: 2026-11-11
status: 验收盘点
---

# 测试数据与验收场景清单

| 里程碑 | 已有证据 | 当前验收状态 |
| --- | --- | --- |
| M1 文件接入 | 离线装包、真实 Mint Agent、Mint TUI 首次接入与复用、Chrome 文件映射、RapidOCR 扫描 PDF | Mint GUI、真实混排 PDF 和 Excel 安装后验收待完成 |
| M2 数据库和 API | CSV、SQLite、PostgreSQL 和分页 REST 对齐并保存，429 断点续跑 | Mint TUI/GUI 分别从配置连接入口发起待验收 |
| M3 API 工作流 | API 环境探查、候选校验、合成报销提交、审批等待和重启恢复 | Mint Agent 根据自然语言形成候选待验收 |
| M4 Computer Use 与交付 | 实际浏览器读取控件、必填项变化、API 结果未知后的只读浏览器对账、Ossie 交换 | 浏览器写入绑定、登录失效后的局部重规划和独立变体验收待完成 |

「已验证」对应本栏所写的入口与范围。「部分通过」表示有正向证据，仍缺验收步骤或存在已发现的问题。「待验证」涵盖已写用例待运行、已有数据待走通和待准备的数据。

## 测试入口

| 入口 | 覆盖范围 |
| --- | --- |
| 各能力包的 `tests/` | 契约、读写边界、规则计算、治理、包内容一致性和各组件行为 |
| [S0 跨层场景](../../../../packages/capabilities/dataagent-scenarios/README.md) | 授权复检、判定、计算和验收报告 |
| [本地装包验收](../../../../scripts/verify_local.sh) 与 [浏览器验收](../../../../scripts/verify_browser.py) | 多源接入、Ontology 映射审核、工作流和浏览器对账 |
| [Benchmark 自测](../09-benchmark/harness/README.md) | 评分口径、金标回填、扰动和评分报告 |

已删除 4 个引用迁移前路径的历史探针、3 个重复正式用例和 1 条恒真断言。无授权拒绝、SQL 正向执行、治理守恒判定和包内容一致性的断言继续由现有用例覆盖。历史探针及其输出可从原评审记录和提交 `fbe24d8` 查阅。

清理后复跑 Runtime 115 项、应用层 201 项、治理层 123 项和 S0 跨层 12 项，全部通过。三个既有 bundle 已同步 `environment.py` 与 `workflow.py`，打包契约与源码逐文件一致。

## 测试数据

### 文件样例

可直接拷贝到临时 Mint 工作区的材料都在 [接入样例目录](../../../../packages/capabilities/dataagent-scenarios/fixtures/intake)。文件和服务样例使用合成业务数据。

| 输入 | 数据内容 | 核对点 |
| --- | --- | --- |
| [invoices.csv](../../../../packages/capabilities/dataagent-scenarios/fixtures/intake/invoices.csv) | INV-001 / 126000 分 / CNY，INV-002 / 90000 分 / CNY | 两个对象金额分别为 1260、900 元，金额能定位到来源记录。已用于浏览器、真实 Mint Agent 和 TUI |
| [invoice.pdf](../../../../packages/capabilities/dataagent-scenarios/fixtures/intake/invoice.pdf) | 文本 PDF，INV-001 / 126000 分 / CNY | 单据编号、金额、币种和第 1 页定位。HTTP 已实际渲染页图，Chrome 已验证定位和保存 |
| [mixed.pdf](../../../../packages/capabilities/dataagent-scenarios/fixtures/intake/mixed.pdf) | 第 1 页单据编号和金额，第 2 页无文本层，第 3 页币种 | 保留第 1、3 页，报告第 2 页缺口。另需真正混排文本与扫描图像的样本验证 OCR 路由 |
| [scan.pdf](../../../../packages/capabilities/dataagent-scenarios/fixtures/intake/scan.pdf) | 纯图片 PDF，INV-003，1260.00 CNY | 实际 OCR、页与文本证据、映射金额。RapidOCR 已在装包后完成识别、原文引用、映射和保存 |
| [invoices.xlsx](../../../../packages/capabilities/dataagent-scenarios/fixtures/intake/invoices.xlsx) | 单 sheet，2 条记录，中间空行 | 第二条金额定位到 B4。稀疏行定位已有数据层测试，安装后接入待验证 |
| [invoices.json](../../../../packages/capabilities/dataagent-scenarios/fixtures/intake/invoices.json) | 一条 INV-001，金额字段为字符串 | 保留原值，建立 JSON Pointer。另有根对象、嵌套数组动态样例。安装后接入待验证 |
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
| M1-01 | 本地装包与任务恢复 | 已验证。Mint 0.1.30 在新工作区安装、setup/doctor、创建真实作业并由新进程读取 | 完整组件再按同一路径复跑，记录包 digest、任务和实际安装目录 |
| M1-02 | 真实 Mint Agent 首次接入 | 已验证。会话 `s_890c7bb91b02` 调用探查、提案、预览和保存，数据库最新任务为 `saved`，两条金额为 1260 和 900 元 | 后续版本以同一结果核对工具轨迹与持久发布记录 |
| M1-03 | CSV 浏览器闭环 | 已验证。Chrome 完成上传、字段选择、分转元、预览 1260、刷新恢复和保存 | 在安装后的成品中复跑，并记录首次预览时间、完成时间、主动操作和澄清次数 |
| M1-04 | 文本 PDF 来源对照 | Chrome 已验证第 1 页原图和高亮、原值 126000、转换值 1260、保存后只读 | 在官方 Mint GUI 的同一任务复跑 |
| M1-05 | 扫描 PDF 和混合 PDF | 离线安装后实际 RapidOCR 识别 INV-003、1260.00、CNY，原文证据完整并保存 | 真实混排、多页部分失败、低置信度数字和扫描框在浏览器中复核 |
| M1-06 | Excel/JSON 来源接入 | 部分通过。数据层已测稀疏 Excel 单元格与 JSON 根对象/选定数组定位 | 安装后分别接入 Excel 和 JSON，复核 B4、JSON Pointer、采样范围、必需字段与扩展 |
| M1-07 | 审核与三种修改范围 | 部分通过。当前值纠正与人工证据、映射预览校验、过期预览拦截已有测试 | 从页面分别完成当前值纠正、修改映射、本体草案，核对对应修订和生效范围 |
| M1-08 | 并发、刷新和重启 | 部分通过。草稿、修订冲突、真实作业、事务回滚和刷新恢复有测试 | 同一任务在聊天与页面并发修改。保留用户编辑，拒绝过期决定。服务重启后恢复材料、草稿及未解决项 |
| M1-09 | Mint TUI 复用与保存 | 真实会话 `s_269164af7922` 两次保存，其中一次复用。用最新修订重提案被拒绝，两次发布引用保持有效 | 复跑时核对任务、发布及工具轨迹 |
| M1-10 | Mint GUI | 已安装并尝试打开，桌面应用停在历史工作区 | 切换合成工作区，完成发起接入、同任务来源核对、纠正、保存并返回聊天 |
| M1-11 | 本地认证与模型披露 | 已验证到组件边界。一次性浏览器入口、跨站请求拦截、任务成员检查、获准字段过滤有测试 | 初次真实测试曾把临时工作台令牌带入模型上下文。该令牌已废止，本地验收日志已脱敏，修复后真实会话没有文件或 Shell 读取。验收持续检查安装工作区无令牌文件 |

### M2 数据库、API 与跨源对齐

| 编号 | 场景 | 已有证据 | 通过条件及待补验证 |
| --- | --- | --- | --- |
| M2-01 | SQLite 有界读取 | 离线安装后已接入并发布。适配器覆盖复合键、名称冲突、NULL、范围与锚点 | 在 Mint 双端复核来源定位 |
| M2-02 | PostgreSQL 实库 | 临时 PostgreSQL 只读角色读取复合主键、Decimal 与日期，数据已进入跨源发布 | 在 Mint 双端复核来源定位 |
| M2-03 | REST 嵌套与分页 | 真实本机 HTTP 已验证逐页响应及 JSON Pointer。安装后分页 REST 已接入并发布 | 在 Mint 双端复核分页覆盖和证据 |
| M2-04 | REST 中断、恢复与漂移 | 安装后第二页 429 可继续。第一页只请求一次，已保存锚点保留。版本冲突和缺少全局版本的分页保留缺口 | 更大范围的游标继续及版本变化后重新探查 |
| M2-05 | 多源身份与冲突 | 同一 INV-003 四种来源合并一个对象。金额冲突保留两份断言并阻止保存。Chrome 已验证跨源顺序变化时的正确行定位 | 补充跨业务域身份和真实混排 PDF 同对象样例 |
| M2-06 | 来源权限和用户入口 | 远端使用宿主连接 ID，拒绝工具参数改写范围。浏览器工作台列出连接名和类型 | 从 Mint 双端发起数据库和 API 接入 |

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
| 本地检查入口 | [verify_local.sh](../../../../scripts/verify_local.sh)、[verify_browser.py](../../../../scripts/verify_browser.py) |

内核基线为 `agent-kernel@4c6e4fdb1970059b6911fd69ea143e63faa3fad8`。Mint TUI 复验使用 Core 0.1.47。各入口的实际结果和可复跑命令见 [离线安装与链路验收](implementation-2026-11-11.md)。
