---
version: 1
date: 2026-11-10
status: 实施中
type: implementation-plan
dataagent_commit: c40a0305497ba3143c4391e290ce7273574698e2
kernel_commit: 41c2ab5fe88f22b8c89e0cbd1fcc52fce33bd1f2
mint_cli: 0.1.30
specs:
  - design/14-ontology-workbench-plan.md
  - design/15-ontology-mapping-experience-plan.md
execution_skills:
  - executing-plans
  - test-driven-development
  - verification-before-completion
execution: 分阶段顺序实施，阶段内按任务提交与验收
---

# 多源接入与环境驱动工作流落地方案

**目标：** 本地安装组件后，用户从 Mint TUI/GUI 提供材料或业务系统入口，通过 Agent 自动识别、探查、Ontology 映射和可视化纠正完成接入；随后在实际系统环境中发现动作并形成可执行、可恢复、可复用的工作流。

**架构：** 现有数据、应用、治理包保留，新增本体服务、工作台和工作流运行包。Mint Agent 提出识别、映射和重规划候选；组件负责实际取数、转换、验证、持久化和受控执行。聊天、工作台和运行实例共享一个业务任务及其精确修订。

**技术栈：** Python ≥3.11,<3.14、Pydantic、SQLite 与内容寻址存储；FastAPI/Uvicorn 提供本地服务；React/TypeScript 构建静态工作台；Web Computer Use 首个后端采用 Playwright，版本由实现时的 lock 固定。继续使用现有 MCP/CLI 端口及 Mint bundle/preset 形态。

**设计依据：** [本体工作台与环境工作流](design/14-ontology-workbench-plan.md)、[映射展示与全流程体验](design/15-ontology-mapping-experience-plan.md)、[共享契约](05-contracts.md)、[OCR 组件](13-ocr-component-plan.md)。任务执行者同时读取设计和本计划。

## 1. 交付范围与约束

1. 当前以本地组件安装和功能验收为主，MintHub 后续分发。模型、数据库和 API 按测试环境连接；“本地落地”不额外要求断网部署。
2. 用户使用自然语言、文件/路径、连接配置和来源选择器；普通用户不手工编排原子调用。
3. 本体预设且有版本；未覆盖字段有明确去向：扩展、未决、不接入。必需目标属性缺失保持可见。
4. 对象、关系、事件、业务动作和工作流控制分别建模；所有转换结果可追溯到来源版本和实际执行。
5. 当前值纠正、来源映射修改、本体定义修订是三个操作范围。正式目标、验收标准和授权边界保持显式版本。
6. 已完成的读取、预览、用户编辑和流程断点持久保存。重试、补证或局部修订复用不受影响的结果。
7. 真实写入首次引入时，同时交付动作账本、幂等、未知对账和执行后验证；这些能力属于同一任务的退出条件。
8. 本地工作台从 TUI/GUI 打开同一任务；GUI 内嵌视图按客户端接口单独适配。首批可使用本地浏览器窗口。
9. 数据、应用、治理包保持各自 Python 进程与依赖环境。工作台经公开端口调用；不把现有运行时合并到一个解释器。
10. `00–04` 和 Catalog 为生成物。新增服务端口先登记到独立服务 schema；需要新的原子编号时修改生成源并重建，不手改生成结果。
11. 每个里程碑都在安装后的包上运行验收，并保留工作区、模型/组件版本、输入、任务和结果引用；源码环境通过不等同装包通过。

## 2. 基线与复用

| 现状证据 | 复用决定 |
| --- | --- |
| 数据包已有 Excel/CSV/JSON/PDF 解析、表画像、字段抽取、来源锚点和 CLI/MCP | 复用实际处理器及返回引用；增加统一 SourceProfile 和文档级探查 |
| `dataagent-ocr/adapter.py` 提供固定引擎适配入口 | 扫描页接入该组件；缺引擎时返回可定位缺口，保留可解析页 |
| runtime 已有内容存储、版本库、访问决策、推理端口与调用封套 | 扩充共享持久提交和业务任务记录，不重写已有封套 |
| `dataagent-cli/bin/dataagent` 当前只分发 data/app/gov | 增加 workbench 分发及安装后运行检查；保留已有命令语义 |
| 现有应用与治理依赖的 duckdb/sqlglot 范围不同 | 使用 LayerClientPort 调用隔离子进程，避免将三层同时导入工作台 |
| 现有 preset 使用本地 path 依赖 | 新增本地接入 preset，打包时物化其安装闭包，校验安装后不引用开发仓路径 |
| CapabilityResult 的 pending 要求 continuation.job_ref | 工作台所有异步处理对应真实 JobRecord；流程等待点引用真实运行作业，不伪造作业号 |

内核已 fetch 并从干净工作区快进到文首提交。旧 `sync-iface-packages.sh --check` 返回停用提示，不代表执行了分发一致性校验。已核对本机 `mint init/add/chat/pack --help` 的本地安装、TUI/GUI 和打包参数；本计划没有进行产品安装或运行验收。

## 3. 里程碑

| 里程碑 | 用户实际可做的事 | 任务 | 退出条件 |
| --- | --- | --- | --- |
| M1：文件接入与映射 | 本地装包；在 Mint 提供 PDF/表格；查看探查、映射、原文和对象；纠正并复用 | T1–T6 | 文本/扫描 PDF、CSV、Excel 真输入走通；TUI/GUI 各有一次完整记录 |
| M2：数据库与 API | 连接 SQLite/PostgreSQL、REST API；探查结构、键和样本；与文档对齐到同一对象 | T7 | 分页/范围/身份/冲突可核对；中断恢复不重复建对象；已有映射能复用 |
| M3：API 业务流程 | 探查测试 OA/CRM 的对象与动作；生成、执行并跟踪提交报销流程 | T8–T9 | 真实提交与状态查询；结果未知先对账；等待、撤权和重启恢复通过 |
| M4：Computer Use 与环境适应 | 在 Web GUI 探查并操作，组合 API/UI；页面或必填项改变后修订局部工作流 | T10–T11 | 不预置整条业务脚本；变化能定位、修订、重验；API/UI 切换不重复提交 |

顺序：`T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8 → T9 → T10 → T11`。每个里程碑结束即可由用户使用，下一里程碑沿用已有任务、存储、视图和交付入口。

M1 默认演示采购资料接入，M3 默认演示报销流程；业务词表、规则与字段来自领域配置。两个领域用于验证通用协议，通用服务不硬编码采购或报销字段名。

## 4. 包与文件职责

下表新路径为实施时创建，已有路径为修改或复用；均相对于 DataAgent 仓库根。

| 包 | 变化与责任 | 交付方式 |
| --- | --- | --- |
| `packages/capabilities/dataagent-contracts` | 新增 intake/ontology/environment/workflow 类型命名空间；core 已有含义保持兼容 | 库与 schema，纳入 bundle 的版本锁 |
| `packages/capabilities/dataagent-runtime` | 共享任务/事件、事务提交、持久作业、进程调用和推理挂起恢复 | 库；各发行包按同一锁定版本物化 |
| `packages/capabilities/dataagent-data` | 统一来源观察、文件/文档探查、数据库/API 读取适配；复用已实现原子 | 现有 data-layer bundle |
| `packages/capabilities/dataagent-ontology` | 本体定义、身份、实例/断言、映射、验证、查询和 Ossie 交换 | 新 Python 库，随 workbench 发行闭包交付 |
| `packages/capabilities/dataagent-workbench` | 组合根、接入协调、任务 API/MCP、浏览器视图、配置与启动 | 新 `dataagent/workbench` bundle |
| `packages/capabilities/dataagent-operations` | 能力观察、动作绑定、工作流候选、真实运行、API/UI 执行与对账 | 新 `dataagent/operations` bundle，M3 接入 |
| `packages/capabilities/dataagent-cli` | workbench/ops 命令分发、setup/doctor、本地启动 | 现有 cli bundle |
| `packages/capabilities/dataagent-intake` | 仅包含组合清单、接入引导 Skill 与样例配置；无第二套运行时 | 新 `dataagent/preset-intake` preset |
| `packages/capabilities/dataagent-scenarios` | 安装后验收、独立样本、测试 OA/CRM、故障与 UX 记录 | 仅测试，不进入用户默认安装 |

工作台中主要文件：

```text
src/dataagent_workbench/
  bootstrap.py                  依赖装配，可信主体与工作区绑定
  session_service.py            接入任务、阶段和用户修改
  intake_service.py             探查、推理提案、映射预览的协调
  view_service.py               来源、字段、对象和流程视图组装
  interfaces/cli.py             workbench 子命令
  interfaces/mcp_server.py      Mint Agent 使用的服务工具
  interfaces/http_api.py        本地 UI 同源 API 与事件流
  adapters/layer_client.py      调用隔离的既有层进程
  static/                      前端构建产物，随发行包携带
web/src/
  pages/IntakePage.tsx           提供来源与持续进度
  pages/MappingPage.tsx          来源、目标字段、实例联动
  pages/ObjectPage.tsx           字段证据与审核
  pages/WorkflowPage.tsx         能力、流程和运行轨迹
  components/SourceViewer.tsx    PDF/表格/JSON/UI 证据预览
  components/MappingDetail.tsx   转换、候选与前后对照
  client.ts                     使用生成类型访问同源 API
```

后端可直接服务打包后的静态文件，参考 [FastAPI StaticFiles](https://fastapi.tiangolo.com/tutorial/static-files/)。前端依赖在开发期锁定，用户安装后无需 Node 构建。Web 控制后端将浏览器依赖和浏览器二进制作为可选运行前提检查，参考 [Playwright 安装与库接口](https://playwright.dev/python/docs/library)。

## 5. 统一协议与调用边界

### 5.1 共享类型

| 文件：`dataagent_contracts/` | 类型 | 必需字段与不变量 |
| --- | --- | --- |
| `intake.py` | SourceSelection | source_id、kind(file/sqlite/postgres/rest/web_ui)、locator_ref、credential_binding_ref?、requested_scope、options；凭据只用引用 |
| `intake.py` | WorkSpec | id、revision、goal、acceptance_criteria、constraints、authorization_ref、domain_config_ref；目标修订独立于实施方法，调用参数不能自授权限 |
| `intake.py` | SourceObservation / SourceProfile | 来源精确引用、内容类型、结构/样本/键、文档页与表块引用、观察时间、Completeness、问题；原值保留 |
| `intake.py` | IntakeSession / JobHandle | id、revision、goal_ref、sources、selected_versions、phase、job_ref、issues、next_actions；异步作业真实持久存在 |
| `ontology.py` | OntologyRevision / MappingSpec | 概念/关系/角色/约束；来源结构指纹、目标本体引用、绑定/转换、身份策略、适用范围、版本及校验引用 |
| `ontology.py` | EntityInstance / Assertion / RelationFact | scope、稳定对象标识、role_bindings 类型化有序角色元组、source_anchors、ontology_revision、mapping_revision、extractor_version、业务/观察时间、证据与未决项 |
| `ontology.py` | MappingPreview / ReviewDecision / DatasetRelease | 目标修订/digest、样本范围、差异、当前对象/映射/定义三种范围、实际主体、验证和保存/发布回执 |
| `environment.py` | EnvironmentSnapshot / CapabilityObservation / ActionBinding | 环境及主体范围、API/UI 观测、参数、限制、前后状态、业务动作语义引用、执行与查询绑定、验证证据 |
| `workflow.py` | WorkflowSpec / WorkflowRun | 引用 WorkSpec 精确修订；步骤/分支/数据绑定/等待/失败策略、动作与环境版本、控制点、已执行回执、未决副作用及恢复条件 |

GUI 锚点通过新增带判别字段的选择器表达，绑定截图、控件/步骤、观察版本和视口；保持旧选择器可读。对 Decimal、复合键、角色顺序、未知状态、extensions 命名空间和来源修订建立序列化测试。

### 5.2 服务端口

以下是拟实施的稳定签名。`ctx` 复用 CallContext，主体由组合根或可信传输固定；引用本身不授予权限。服务内部返回类型由 CapabilityResult 包装。

```python
SessionService.start(sources: list[SourceSelection], goal: WorkSpec, ctx: CallContext) -> JobHandle
SessionService.get(session_id: str, ctx: CallContext) -> IntakeSession
SessionService.events(session_id: str, after: int, ctx: CallContext) -> EventPage
IntakeService.advance(session_id: str, ctx: CallContext) -> IntakeSession
IntakeService.submit_proposal(session_id: str, proposal: MappingSpec, expected_revision: str, ctx: CallContext) -> MappingPreview
OntologyService.preview(mapping: MappingSpec, observations: list[SourceObservation], ctx: CallContext) -> MappingPreview
OntologyService.review(decision: ReviewDecision, expected_revision: str, ctx: CallContext) -> ReviewReceipt
OntologyService.publish(candidate_ref: VersionedRef, expected_revision: str, ctx: CallContext) -> DatasetRelease
EnvironmentService.observe(source: SourceSelection, ctx: CallContext) -> EnvironmentSnapshot
WorkflowService.draft(goal: WorkSpec, environment: EnvironmentSnapshot, ctx: CallContext) -> WorkflowSpec
WorkflowService.submit_proposal(proposal: WorkflowSpec, expected_revision: str, ctx: CallContext) -> WorkflowValidationReport
WorkflowService.start(spec_ref: VersionedRef, expected_revision: str, ctx: CallContext) -> WorkflowRun
WorkflowService.advance(run_id: str, ctx: CallContext) -> WorkflowRun
```

EventPage 为持久事件的 `items/cursor/has_more`；ReviewReceipt 为实际保存的决定引用、产生的修订与需重验集合；WorkflowValidationReport 包含目标/环境/动作修订、结构/参数/授权/前后置检查、问题、允许启动的精确 spec 引用与验证有效范围。读写服务使用同一任务修订，冲突统一返回 version_conflict 及可展示差异。

Mint 工具入口为 `intake_start/intake_status/intake_propose/mapping_preview/mapping_apply/workbench_view`；M3 再增加 `environment_observe/workflow_draft/workflow_propose/workflow_start/workflow_advance/workflow_status`。这些是聚合服务工具，不冒用新的 DA 原子编号。`workflow_draft` 保存候选及推理请求，Agent 经 `workflow_propose` 提交候选，组件验证后才能启动；重规划复用同一提案入口。

### 5.3 推理与组件的协作

1. 组件执行解析和有界探查，固定 SourceProfile 与来源引用。
2. 需要语义判断时，返回 needs_input 与结构化 inference_request，包括本体允许目标、获准使用的样本、未决项和约束。
3. Mint Agent 返回 MappingSpec 或工作流修订提案；组件校验、试算并保存，返回真实预览与问题。
4. Agent 根据问题继续探查、修方法或请用户补充；用户在网页的修改通过相同端口写入任务，Agent 读取新修订继续。
5. 相同本体版本、来源结构和适用范围命中的已验证映射直接复用；来源变化触发局部重验。

仅把允许进入模型上下文的片段交给 Agent；工作台查看原件仍走独立访问检查。工具 stdout 延续摘要与结果引用约定，大内容留在工作区或受控端口。

## 6. 存储与持久任务

```text
<workspace>/.dataagent/
  content/                 已有原件、页面、抽取与样本的内容寻址对象
  db/decisions.sqlite3     已有访问/外发决策
  db/workbench.sqlite3    新任务、修订、断言、事件、决定和发布清单
  results/                 CLI/MCP 全文结果引用
  runtime/workbench.json   当前服务进程、loopback 地址和工作区绑定
  runtime/browser/         受控浏览器会话引用和恢复信息
  exports/                 用户明确导出的定义、映射和结果
```

`dataagent_runtime/ports/workbench_store.py` 定义 WorkbenchStore；`adapters/workbench_sqlite.py` 实现。基本操作为 `get(kind,id,revision)`、`current(kind,id)`、`query(kind,scope,selector,cursor)`、`events(session,after)`、`commit(change_set)`。ChangeSet 包含条件修订、对象写入、追加事件及 outbox；CommitReceipt 返回实际修订和事件游标。

提交使用同一连接的 `BEGIN IMMEDIATE`；检查 expected_revision/推进权，在一个事务里保存事实与待执行请求，提交后再派发副作用或更新查询投影。已有数据层私有数据库保存不可变输入引用，新服务不跨这些文件宣称原子事务。

任务阶段、资产生命周期、业务对象状态分别保存。恢复时查询已有结果、已消费事件、真实动作回执与未决副作用；不能仅重放聊天历史恢复执行。

本地 HTTP 服务只监听 loopback，校验工作区身份、Origin 和访问权限；启动凭据受控保存，普通工具输出不回显。UI 直接访问的来源预览同样检查读取和披露范围。

## 7. 重点评审条件

| 条件 | 用户应获得的行为 | 负责测试 |
| --- | --- | --- |
| PDF 混合文本/扫描页，表格跨页，部分页无法识别 | 已识别结果保留，页级缺口可定位，不能显示全量已完成 | T3、T6 |
| 同名对象、复合键、不同来源单位或业务时间不同 | 不错合并、不静默覆盖，冲突和候选可对照 | T4、T7 |
| 网页修改、Agent 修订和旧预览同时存在 | 保存有并发检查，旧预览不能确认新映射，编辑草稿保留 | T2、T5、T6 |
| 远端提交成功但回执丢失、API/UI 切换、运行进程退出 | 查询对账后续跑，不能重复提交或伪称已撤销 | T9、T10 |
| 客户环境新增必填项、布局/接口变化、权限撤销 | 定位失效步骤，补充信息或局部修订；已完成结果可复用 | T7、T10、T11 |

## 8. 任务分解

任务按实际交付边界划分。每项实施先写列出的失败用例，运行确认失败，再实现对应文件与最小语义，运行定向测试和依赖回归，最后提交。下列测试命令在创建对应包、锁文件及测试后执行；本次编制计划未运行它们。

### T1：冻结最小共享类型与样例

**文件：** 新增 `packages/capabilities/dataagent-contracts/src/dataagent_contracts/intake.py`、`ontology.py`；扩展 `core/refs.py` 的 GUI 选择器；新增 `tests/test_intake_ontology_contracts.py` 和 `examples/intake/` 样例。WorkSpec 在本任务定义，environment/workflow 在 T9 追加。

**接口：** 产出 §5.1 的 M1 类型，导出 JSON Schema；保留 core 引用与状态含义，所有后续任务依赖这一份类型。

- [ ] 写入固定的输入/期望样例：文档分区覆盖、Decimal 金额、跨源复合键、未映射必需字段、命名空间扩展、多元角色关系与过期来源。
- [ ] 写 `test_decimal_and_role_tuple_survive_roundtrip`、`test_partial_document_preserves_page_gaps`、`test_old_source_anchors_remain_readable`，先运行确认新类型不存在时失败。
- [ ] 实现类型和字段约束；将“必需字段未映射”保留为问题，不把扩展项当作已完成绑定。生成 schema，编写前端类型生成输入清单。
- [ ] 对照 [Ossie 源码证据](design/14-ontology-workbench/ossie-evidence.md) 中固定提交 `d700cdeac41d15a7004eb2f9b0b38a2b1d517a18` 核对身份、关系角色顺序、多元事实和集合语义。建立本地测试样例；实例证据、审核与扩展存储在 DataAgent 结构中，交换适配在 T11 实现。
- [ ] 运行 `uv run --frozen --project packages/capabilities/dataagent-contracts pytest tests/test_intake_ontology_contracts.py`，再运行该包全部测试，提交 `feat(16-contracts): add intake and ontology contracts`。

**最小回归样例：**

```python
def test_decimal_and_role_tuple_survive_roundtrip(assertion_case):
    from dataagent_contracts.ontology import Assertion
    result = Assertion.model_validate_json(assertion_case.model_dump_json())
    assert result.role_bindings == assertion_case.role_bindings
    assert result.source_anchors == assertion_case.source_anchors
    assert result.ontology_revision == assertion_case.ontology_revision
```

`assertion_case` 在本任务 conftest 中由固定 JSON 创建，包含采购单、币种、十进制金额和业务日期四个角色，金额使用字符串形式的十进制定点编码。

### T2：持久任务、真实本地装包和最小服务

**文件：** 新增 runtime 的 `ports/workbench_store.py`、`adapters/workbench_sqlite.py`、`jobs.py`；新增 workbench 的 `pyproject.toml/uv.lock`、§4 中的 bootstrap/session_service、CLI/MCP/HTTP 入口；新增 `dataagent-intake/mint.toml` 及接入 Skill；修改 cli 分发器；新增 `scripts/verify_local.sh`。

**接口：** 实现 SessionService、WorkbenchStore 和真实 JobRecord；CLI 子命令 `dataagent workbench serve/intake/view`；MCP 首先提供 intake_start/intake_status/workbench_view。服务先可受理任务并保存来源引用，处理器由后续任务接入。

- [ ] 编写 `test_restart_retains_session`、`test_concurrent_edit_returns_version_conflict`、`test_pending_points_to_persisted_job`、`test_untrusted_browser_cannot_read_source`，以及本地包清单和 setup/doctor 测试。
- [ ] 实现条件提交和任务事件，事务核心按以下顺序执行；失败回滚全部本地更改。

```sql
BEGIN IMMEDIATE;
-- 在事务内比较目标修订及推进权。
-- 保存新对象修订、追加事件、写入唯一请求键和待派发记录。
-- 任一比较失败即 ROLLBACK，成功才 COMMIT。
COMMIT;
```

- [ ] 实现服务启动、工作区绑定、真实任务状态及事件游标；新增工作台包、聚合 preset、本地依赖闭包构建工具 `packages/capabilities/dataagent-workbench/tools/build_bundle.py`，由锁文件物化 shared 库和静态资源。
- [ ] 构建工具提供 `--out build/local`，输出 `build/local/preset-intake/mint.toml` 和其中相对路径依赖的完整包目录；为闭包内每个目录记录 digest。发布到 Hub 时替换为版本化依赖，服务接口保持相同。
- [ ] 扩展 `dataagent setup/doctor`，只准备已安装的包，原有 data/app/gov 分发保持兼容；新工具 schema 单独注册。包启动路径不能指向开发仓库。
- [ ] 在临时工作区运行 `mint init --no-preset`，以构建输出中 `build/local/preset-intake` 的绝对路径作为 `mint add path:` 参数，然后运行已安装 CLI 的 setup/doctor、服务 health 与任务重启检查。`verify_local.sh --phase bootstrap` 自动建立临时目录、解析唯一已安装 CLI 路径和实际任务 ID，不要求手填。
- [ ] 运行 `uv run --frozen --project packages/capabilities/dataagent-runtime pytest tests/test_workbench_store.py`、`uv run --frozen --project packages/capabilities/dataagent-workbench pytest tests/test_session_service.py` 和 cli 现有测试，提交 `feat(16-runtime): persist local intake sessions`。

本地安装工具保存临时工作区、安装清单、版本/哈希与输出。新服务尚未接入解析器时返回明确的未配置处理阶段，不伪造接入结果。

### T3：文件识别与 PDF/表格探查

**文件：** 新增 data 包 `observation/files.py`、`observation/documents.py`；复用 `ingestion/files.py`、`preparation/profiles.py`、`preparation/documents.py`；按 OCR 方案接入固定引擎；新增 workbench `adapters/layer_client.py`；测试 `dataagent-data/tests/observation/test_file_profiles.py`。

**接口：** `probe_file(selection, ctx) -> SourceProfile`；LayerClientPort 调用既有包的公开 MCP 工具与固定上下文，返回原始 CapabilityResult 和精确引用。不同层的解释器保持隔离。

- [ ] 在 scenarios 的 `fixtures/intake/` 生成文本 PDF、文本/扫描混合 PDF、跨页表、规整/不规则 Excel、CSV、JSON，以及逐字段原文锚点与预期问题；用独立期望文件验证，不由同一抽取程序生成金标。
- [ ] 写 `test_mixed_pdf_retains_successful_pages`、`test_scanned_page_without_engine_is_not_empty_success`、`test_cross_page_table_has_anchors`、`test_sampled_table_is_not_full_coverage`，先运行失败。
- [ ] 识别文件类型后分别调用已有解析/画像能力。增加文档级探查：页类型、章节/表块、候选字段、业务内容候选与完整性；扫描页交固定 OCR，引擎缺失转 needs_input 或部分完成。
- [ ] 保存原件、分区结果及每步实现版本；失败页/表不影响已有成功结果。LayerClientPort 处理程序失败、超时、部分结果和推理请求，不吞成空数组。
- [ ] 运行 `uv run --frozen --project packages/capabilities/dataagent-data pytest tests/observation/test_file_profiles.py`，并运行 OCR 接缝和既有解析相关测试，提交 `feat(16-ingestion): profile files with source evidence`。

### T4：本体、断言、映射执行与身份解析

**文件：** 新增 `dataagent-ontology/pyproject.toml/uv.lock`、`src/dataagent_ontology/{registry,mapping,facts,identity,validation,ports}.py`、`adapters/store.py`；新增工作台 `ontologies/procurement.json`；测试 `dataagent-ontology/tests/test_mapping_semantics.py`。

**接口：** OntologyService.preview/review/publish；候选定义与实例、来源断言与解析事实分别保存，调用 WorkbenchStore 提交。

- [ ] 写 `test_missing_required_binding_is_reported`、`test_minor_units_use_decimal`、`test_same_name_does_not_merge_tenants`、`test_composite_identity_keeps_all_parts`、`test_nary_relation_preserves_roles`、`test_conflicting_sources_keep_both_assertions`。
- [ ] 实现固定本体加载、类型与引用检查、映射绑定和转换。首批转换支持字段选择、十进制单位、日期/时区、枚举、字段组合与受限条件选择；未知函数/方言返回不可执行问题。
- [ ] 身份键由 scope、概念、身份策略和规范化键元组组成；缺关键身份信息时保留候选。相同事实的多来源断言分开保存，发布事实按类型化角色元组去重。
- [ ] 实现字段证据、当前对象纠正、映射修订和发布指针；同一事务保存决定、修订及事件。UI 单值字段从关系投影生成，多元事实保留共同事实标识。
- [ ] 运行 `uv run --frozen --project packages/capabilities/dataagent-ontology pytest tests/test_mapping_semantics.py`，再运行 T1 的协议回归，提交 `feat(16-ontology): materialize versioned evidence-backed facts`。

**核心数值语义：**

```python
from decimal import Decimal

def minor_to_major(raw: str) -> Decimal:
    return Decimal(raw) / Decimal("100")

assert minor_to_major("126000") == Decimal("1260")
```

金额值与币种分别绑定，不能根据数字大小猜单位；转换依据来自映射草案及其验证。

### T5：Mint Agent 的自动映射与纠正闭环

**文件：** 实现 workbench `intake_service.py`、`inference_requests.py`；新增 MCP `intake_propose/mapping_preview/mapping_apply`；更新 preset 的 `skills/dataagent-intake/SKILL.md`；测试 `tests/test_proposal_loop.py`。

**接口：** IntakeService.advance/submit_proposal；复用 InferencePort 与现有 needs_input。Agent 返回 MappingSpec，组件产出固定修订的预览和问题。

- [ ] 写 `test_agent_proposal_is_validated_before_apply`、`test_expired_preview_cannot_confirm_changed_mapping`、`test_ui_correction_is_visible_to_agent`、`test_known_source_reuses_mapping`、`test_disallowed_context_is_not_in_inference_request`。
- [ ] 构造任务级推理请求：已授权且有覆盖说明的样本、允许目标、候选、正式约束与未决项。结果仅接受结构化提案，不能由自由文本直接改正式资产。
- [ ] 实现草案版本、试算、问题反馈与局部重跑。用户自然语言纠正与网页编辑写入同一任务；若对象或范围不明确，只询问影响本次结果的关键歧义。
- [ ] 增加已验证映射的检索和适用检查，命中时按 schema/语义指纹复用，记录重验和失效原因。
- [ ] 运行 `uv run --frozen --project packages/capabilities/dataagent-workbench pytest tests/test_proposal_loop.py`；在真实 Mint 会话完成一次提案—预览—纠正—复用，记录原始会话和任务引用，提交 `feat(16-intake): connect agent proposals to verified mappings`。

### T6：实现工作台与 M1 安装后验收

**文件：** 实现 §4 的 web 页面/组件、HTTP API、view_service 和事件流；新增 `web/package.json`、`package-lock.json`、`tsconfig.json`、`vite.config.ts`、`playwright.config.ts` 以及 `web/tests/intake.spec.ts`、`mapping.spec.ts`、`source-preview.spec.ts`；更新 bundle 构建工具与 `scripts/verify_local.sh`。

**接口：** UI 使用生成的类型和同源 API，原文读取、对象/映射查询、审核和发布均经公开服务；Mint 和页面共享 session_id。

- [ ] 写浏览器验收：打开任务、显示未映射必需字段、选择金额来源、查看前后样本、定位 PDF 原文、保存指定范围、重载恢复、并发修订提示及键盘操作。
- [ ] 实现[映射主页面和字段详情](design/15-ontology-mapping-experience-plan.md)：来源/目标/实例联动，原值与转换值对照，问题过滤、自由说明、草稿自动保存和局部重算。
- [ ] 将未覆盖字段的扩展/未决/不接入状态、当前值纠正和映射修订分别展示；本体定义修改只形成单独草案，经有权限主体审核后产生新修订，不静默改变正式本体。
- [ ] 实现接入进度与恢复：立即显示受理与真实阶段；未知总量不用伪百分比；部分失败显示已保留范围和恢复入口。刷新后恢复筛选、当前样本及未提交编辑。
- [ ] 构建静态资源入包；工作台打开动作返回可访问视图和任务引用；普通用户不执行开发构建。新增环境检查和示例入口，凭据、授权及模型缺失定位到实际配置项。
- [ ] 运行 `npm --prefix packages/capabilities/dataagent-workbench/web run test:e2e`、该目录 `run build`，以及 `bash scripts/verify_local.sh --phase files`。
- [ ] 在 Mint TUI、GUI 分别完成 PDF 与表格接入；由用户或测试者在页面纠正，返回聊天继续并保存接入。保留视频/截图、安装版本、会话、任务、来源和发布清单，提交 `feat(16-workbench): ship file intake and mapping experience`。

M1 退出：文本/扫描 PDF、CSV、Excel 各一个真实解析样本通过；未知布局样本允许明确缺口；错误映射可纠正，二次接入能复用，所有展示值可定位来源。模型提案替身只用于单测，不能代替真实 Mint 会话验收。

### T7：数据库与 REST API 自动接入

**文件：** data 包新增 `observation/database.py`、`observation/http.py`、`ports/source.py`、`adapters/sources/{sqlite,postgres,rest}.py`；工作台新增连接配置与凭据绑定；测试 `tests/observation/test_database_rest.py`。

**接口：** SourcePort 的 `describe/read/changes` 按提供方声明能力返回 SourceObservation；不支持 changes 时明确返回 unsupported。SourceProfile 继续使用 T1 类型。

- [ ] 写包含复合键/同名异物/时态/NULL 的数据库 fixtures；REST 测试提供有限分页、游标分页、嵌套数组、429、部分失败、源版本变化和响应不完整。
- [ ] 对数据库读取 schema、键、统计与有界样本；首次支持 SQLite 和 PostgreSQL 的只读读取。REST 从用户提供/获准读取的描述或样本发现结构，保留端点、响应引用、分页和读取范围。
- [ ] 将字段、文档和 API 对齐到同一对象；保存转换与关联依据。复合键不拼成无类型字符串，采样统计和全量唯一性分别报告。
- [ ] 实现分区/游标的持久提交，范围变化后重验映射；失败页重试沿用请求/来源版本，已完成记录不重复创建。
- [ ] 运行 `uv run --frozen --project packages/capabilities/dataagent-data pytest tests/observation/test_database_rest.py` 和 `bash scripts/verify_local.sh --phase sources`；在 Mint 两端各发起一次数据库/API 接入，提交 `feat(16-sources): add database and REST observations`。

M2 退出：SQLite/PostgreSQL、REST 与 PDF 的同一业务对象能对齐；完整性和冲突可核对；凭据不会出现在任务摘要、普通日志和截图中。

### T8：搭建可变化的本地业务测试环境

**文件：** 新增 scenarios `fixtures/business-system/`、`src/dataagent_scenarios/business_system/{server,state,schemas}.py`、对应 GUI 静态页面；测试 `tests/test_business_system_fixture.py`。

**接口：** 测试系统提供 API 文档、记录查询、草稿、附件、提交、状态查询和审批事件，GUI 操作同一业务状态。测试管理端用于注入环境变化，Agent 不接触该管理端。

- [ ] 写测试保证 API 建立的草稿可由 GUI 读取，GUI 提交的记录可由 API 查询；相同幂等键得到同一业务单据；未知请求可按业务键查询。
- [ ] 实现订单/报销两套领域配置和统一业务状态；单据生命周期为 draft/submitted/waiting_approval/approved/rejected，保存 native 状态与观察时间。
- [ ] 添加三种环境配置：新增必填组织字段、控件/页面布局变化、API 字段或分页变化；注入“远端成功但客户端未收到响应”和审批迟到事件。
- [ ] 提供用户演示记录和没有演示记录两种入口。隐藏的评测样本包含不同字段名与布局，通用 Agent 只获得目标、授权范围和实际环境观察。
- [ ] 运行 `uv run --frozen --project packages/capabilities/dataagent-scenarios pytest tests/test_business_system_fixture.py`，提交 `test(16-environment): add mutable API and GUI business fixture`。

### T9：API 环境探查与持久工作流

**文件：** 新增 contracts `environment.py/workflow.py`；新增 operations `discovery.py`、`bindings.py`、`planner.py`、`runner.py`、`action_gateway.py`、`reconciliation.py`、`waits.py`、`adapters/api.py`；新增 operations bundle；工作台增加环境与流程工具/视图。

**接口：** 实现 EnvironmentService 和 WorkflowService 的 draft/submit_proposal/start/advance；复用 T1 的 WorkSpec。WorkflowSpec 支持 observe/transform/decide/act/wait/human/verify 节点，显式绑定输入输出和条件；WorkflowRun 引用真实动作账本和作业。工作台通过 operations 的公开 MCP 端口调用，不把该包导入工作台进程。

- [ ] 写 `test_discovery_does_not_execute_write_actions`、`test_approval_wait_survives_restart`、`test_success_without_receipt_is_reconciled`、`test_revoked_authority_blocks_next_action`、`test_completed_steps_are_not_replayed`。
- [ ] 根据接口描述、实际读取与用户业务目标生成 EnvironmentSnapshot、CapabilityObservation 和动作候选，区分发现、验证和当前授权；采用业务类型配置，不固定整条提交脚本。
- [ ] 将动作语义绑定到 API，工作流候选通过结构、参数和前后置校验后执行。业务目标固定；运行中的补证或方法变化形成显式修订。
- [ ] 为自然语言流程生成与重规划建立结构化推理请求；Agent 提交候选，组件保存验证报告，start 只接受仍有效的精确候选。新增 `test_unvalidated_workflow_cannot_start` 和 `test_replan_keeps_goal_and_completed_receipts`。
- [ ] 持久预留业务动作键与参数 digest，派发前检查当前推进权和授权，执行后保存回执并查询业务状态。结果未知只查询；补偿作为独立动作。暂停、等待、取消与撤销分别记录。
- [ ] ActionGateway 是唯一写出入口，消费已提交 outbox，校验运行修订、推进令牌和请求唯一键。连接器声明远端幂等/围栏/查询能力；旧进程已经发出的请求在完成或对账前保持 in_flight/unknown，租约到期不自动判为未执行，不以本地事务宣称远端恰好执行一次。新增 `test_expired_worker_cannot_dispatch_new_request` 和 `test_lease_expiry_does_not_clear_unknown_effect`。
- [ ] 原子消费等待事件、更新控制点和下一请求；执行者易主后旧推进者不能发新动作。作业/等待引用真实记录，复用当前 CapabilityResult 语义。
- [ ] 运行 `uv run --frozen --project packages/capabilities/dataagent-operations pytest tests/test_api_workflow.py tests/test_recovery.py` 和 `bash scripts/verify_local.sh --phase api-workflow`，提交 `feat(16-workflow): discover and run durable API workflows`。

**副作用判定表必须落入测试：**

| 对账结果 | 允许后续行为 |
| --- | --- |
| applied | 记录原回执，核验后续状态 |
| not_applied 且依据可靠 | 在有效授权下恢复原动作实例 |
| partial | 按项继续对账或提出独立补偿 |
| unknown | 保持待处理，等待或交人工接管 |

M3 退出：在 Mint 发起“根据发票提交报销并确认进入审批”，系统基于发现的环境形成并运行流程，保存真实单据及待审批状态；退出后可恢复。业务审批通过不作为提交完成的同义结果。

### T10：Computer Use、混合通道与局部重规划

**文件：** operations 新增 `ports/computer_use.py`、`adapters/playwright_browser.py`、`ui_observation.py`、`adapters/ui_action.py`、`drift.py`；工作台增加来源中的 UI 证据与 WorkflowPage；测试 `tests/test_gui_workflow.py/test_channel_switch.py`。

**接口：** `ComputerUsePort.observe(session_ref) -> UIObservation`、`act(request) -> UIReceipt`。观察包含截图、可访问控件/可用 DOM、前后页面版本；动作绑定输入引用、观察版本、控件定位与后置查询。

- [ ] 写 GUI 首次探查、必填项变更、控件失效、登录过期、API 提交未知后切换 UI 查询的用例。通过浏览器执行真实点击和填写，评测器独立查询测试系统状态。
- [ ] 实现 Web Computer Use 后端并保存观察、动作和回执引用。Agent 依据实际页面提出局部步骤，组件检查过期观察和执行条件；不将一条固定页面操作脚本作为能力发现结果。
- [ ] API/UI 绑定引用相同业务动作实例与成功判据；可组合不同步骤。API 提交未知时，UI 路径仅用于查询对账，直到已知是否生效才决定后续。
- [ ] 漂移使受影响绑定和验证失效；只重探查该部分，保留材料、已完成步骤和未受影响映射。新增必填字段向用户询问必要业务信息，随后生成流程新修订。
- [ ] 运行 `uv run --frozen --project packages/capabilities/dataagent-operations pytest tests/test_gui_workflow.py tests/test_channel_switch.py`、工作台流程页面测试和 `bash scripts/verify_local.sh --phase mixed-workflow`，提交 `feat(16-computer-use): ground workflows in observed Web environments`。

M4 的首批边界为 Web 业务系统；原生桌面应用后端沿同一 ComputerUsePort 追加，拥有独立能力和兼容测试，不把浏览器验收外推为所有桌面系统已支持。

### T11：复用、交换、体验与完整交付验收

**文件：** ontology 新增 `adapters/ossie.py` 与固定 schema/依赖锁；operations 增加验证报告与复用条件；scenarios 新增 `tests/test_ossie_roundtrip.py/test_saved_ingestion.py/test_acceptance_matrix.py`；完善 preset 和 `scripts/verify_local.sh`，新增 `scripts/verify_packaged.sh`。

**接口：** 导出定义、逻辑模型、映射与 DataAgent sidecar；返回支持子集及逐项损失。已保存接入/工作流绑定本体、来源结构、环境和验证范围。

- [ ] 写 schema 与语义往返、多元关系、未知表达式、实例扩展 sidecar、重新接入和配置迁移测试；固定 Ossie 提交，schema 的外部引用解析到本地快照。
- [ ] 以两套领域运行同一组件：采购数据接入与报销业务流程；只替换领域资产、目标和系统绑定，通用代码不增加客户字段特判。
- [ ] 在干净临时工作区安装本地产物，在隔离测试进程中屏蔽开发仓路径后运行全部验收，不改动开发仓目录或权限。每个包清单记录共享契约/schema 和静态资源 hash；setup/doctor 给出实际依赖缺口。
- [ ] 录制 TUI 和 GUI 的端到端使用：提供输入、查看探查、改金额映射、补缺失信息、查看对象、保存复用、发起流程、暂停恢复及环境变化后续跑。
- [ ] 运行 `bash scripts/verify_local.sh --phase all` 与 `bash scripts/verify_packaged.sh`；比较新实现影响到的现有 S0 包回归，提交 `test(16-delivery): verify local packages and user workflows`。

## 9. 用户验收脚本与证据

验收脚本创建并使用临时工作区，默认不发布远程制品、不写真实客户业务系统。项目目录内保留结果与回执，测试秘密和原件按环境要求存储，不新增到代码仓。

| 测试入口 | 必须产出的证据 |
| --- | --- |
| `verify_local.sh --phase bootstrap` | 本地安装清单、服务启动、真实任务及重启恢复 |
| `verify_local.sh --phase files` | PDF/扫描页/表格探查、映射、来源锚点、纠正和复用 |
| `verify_local.sh --phase sources` | 数据库/API 读取覆盖、分页、身份与文档对齐 |
| `verify_local.sh --phase api-workflow` | 环境与能力观察、WorkflowSpec、动作回执、等待及对账 |
| `verify_local.sh --phase mixed-workflow` | 浏览器实际观察/动作、API/UI 关联、漂移与局部重规划 |
| `verify_packaged.sh` | 从本地产物安装运行，无开发目录依赖；包版本/哈希与可复跑说明 |

每次真实 Mint 验收保留：Mint/组件版本、工作区与数据范围、业务任务、映射/工作流修订、来源与执行回执、截图/视频、通过/未通过/未验证项。没有实际打开 TUI 或 GUI 的轮次不能登记为该端验收通过。

## 10. 用户体验验收

| 任务 | 观察点与通过条件 |
| --- | --- |
| 首次接入 | 用户只需提供输入与目标；Agent 自动识别、探查并出现可核对预览 |
| 有歧义 | 提供少量有依据的候选与自由输入，不逐字段机械提问 |
| 修改错映射 | 从目标字段定位来源，查看转换和前后差异，一次保存到明确范围 |
| 处理失败 | 错误指出位置、影响、已保留结果和下一步；修复后只重做失败部分 |
| 恢复任务 | 重启会话/服务后保留进度、编辑、材料、回执和未解决项 |
| 复用接入 | 新输入复用符合条件的配置；变化只定位到受影响映射 |
| 运行流程 | 用户能理解当前步骤、业务状态、等待对象及接管入口 |
| 真实通用性 | 两个领域共享实现，不靠固定金标、硬编码字段或整条页面脚本通过 |

每阶段至少完成一次目标用户的未提示操作观察，记录任务成功率、首次预览时间、完成时间、主动操作、澄清轮次和重做次数。容量与时延门槛以实际运行基线确定；已知环境失败、替身测试和未完成分支单列。

## 11. 验证、提交与下一阶段入口

各任务只跑直接相关测试及依赖回归；阶段出口运行端到端和安装后验收。测试失败先定位数据、协议或实现原因，不通过放宽正式判据关闭问题。

本仓已有未提交 OCR 与文档改动，实施先识别并保留；功能代码在执行阶段使用仓库约定的隔离工作区。提交只包含本任务改动，新增公共类型同步 schema 和消费端。子仓推送后再更新宿主 gitlink，指向已推送提交。

实施记录保存在 [16-local-ingestion-workflow-build/](16-local-ingestion-workflow-build/README.md)，每轮登记修改、验证、评审与剩余问题。首个执行范围是 T1–T2，再完成 T3–T6 达到 M1；不把后续 Hub 发布或所有系统适配器作为 M1 的前置条件。

| 记录 | 内容 |
| --- | --- |
| [计划自检](16-local-ingestion-workflow-build/plan-review.md) | 设计覆盖、接口与依赖修正、验证边界 |
| [测试数据与验收场景清单](16-local-ingestion-workflow-build/test-inventory.md) | 样例、已验证证据、已发现问题和待验收矩阵 |
| [离线安装与链路验收](16-local-ingestion-workflow-build/implementation-2026-11-11.md) | 可复跑命令、真实运行引用、评审修复与待验收场景 |
