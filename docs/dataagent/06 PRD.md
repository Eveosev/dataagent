---
doc_id: prd
title: 06 PRD
answers: P1（多源数据接入）与 P2（本体的实现、打通、可视化）改什么、为什么改；每个目标怎么验收
status: 草稿 v0.1（P1、P2 细到验收命令；P3–P6 见 05；待拍 Q1–Q11）
---

# 06 PRD

> 输入：[00 术语与总览](<00 术语与总览.md>)、[01 iface 依赖与分工](<01 多源接入与本体的 iface 依赖与分工.md>)、[02 借鉴 Palantir Ontology 与 Databricks Genie](<02 借鉴 Palantir Ontology 与 Databricks Genie.md>)、[03 平台方案与 iface 共建](<03 平台方案与 iface 共建.md>)、[04 验收方法与数据](<04 验收方法与数据.md>)、[05 分期路线与 MVP 范围](<05 分期路线与 MVP 范围.md>)；方案 16 与 `test-inventory.md`（`codex/16-local-intake@87d5e8e`）。
> 命令默认在 DataAgent 仓库根目录执行；`verify_local.sh` 指 `scripts/verify_local.sh`（现有阶段：bootstrap、files、sources、discovery、api-workflow、mixed-workflow）；09-benchmark 命令在 `docs/research/dataagent-2026-11-03/09-benchmark/` 下执行。标「新增」的命令、阶段或测试在本期内建。
> 任务拆分见 [07 MVP 实施文档](<07 MVP 实施文档.md>)。

## 1 背景与问题

1. 方案 16 在 11-11 至 11-12 写完接入、本体、工作台、工作流的主体代码（10 个提交，新增约 2.8 万行，其中代码约 1.3 万行），但截至 11-16 没有一个里程碑通过验收：GUI 没跑通，Excel 与文本 PDF 没在安装产物上接入，没有独立评审。代码在本机未推送的分支上。
2. 本体只有单实体、包内固定一个；本体草案转不成正式修订；发布后的对象没有查询入口；应用层与本体完全断开（[02](<02 借鉴 Palantir Ontology 与 Databricks Genie.md>) §4）。
3. 平台事各包各做一套（[03](<03 平台方案与 iface 共建.md>) §3）；默认审批、凭据、宿主超时三处直接挡住 Mint 双端验收（[01](<01 多源接入与本体的 iface 依赖与分工.md>) §1）。
4. 真实业务数据拿不到，审核场景没有对错真值；09-benchmark 有 3217 条用例但没有一轮正式跑分（[04](<04 验收方法与数据.md>) §7）。
5. 11-16 已拍：多源接入是刚需（P1），P2 做本体的实现、打通、可视化；我们承担完善 iface 的职责；不只锚定令才（[00](<00 术语与总览.md>) §13）。

## 2 目标与非目标

### 2.1 目标

| # | 目标（可验收的一句话） | 对应 §6 | 期 |
|---|---|---|---|
| G1.1 | 8 类文件在安装产物上接入，展示值都能定位来源 | V1.1 | P1 |
| G1.2 | 数据库与 API 在安装产物上接入，可续跑 | V1.2 | P1 |
| G1.3 | 跨源对齐正确，冲突不静默覆盖 | V1.3 | P1 |
| G1.4 | Mint TUI、GUI 各完成一次文件接入和一次数据库或 API 接入 | V1.4 | P1 |
| G1.5 | 默认审批策略下可用 | V1.5 | P1 |
| G1.6 | 凭据不外泄 | V1.6 | P1 |
| G1.7 | 中断可恢复，结构相同可复用，单次调用不超宿主时限 | V1.7 | P1 |
| G1.8 | 安装干净，`doctor` 能定位缺失的引擎与模型 | V1.8 | P1 |
| G1.9 | 目标用户无提示可完成接入，体验达标 | V1.9 | P1 |
| G1.10 | 平台收敛到位（R0、R1、R2 与 R3 的凭据部分），核心与领域包分界 | V1.10 | P1 |
| G1.11 | 独立评审结论为「可验收」 | V1.11 | P1 |
| G1.12 | 通用接入能力有正式基线（L1） | V1.12 | P1 |
| G1.13 | 令才真实报文接入并映射到规则字段目录，可判定率提升（L2） | V1.13 | P1 |
| G1.14 | 冻结版本可回归（L2） | V1.14 | P1 |
| G1.15 | 变异用例能检出（L3） | V1.15 | P1 |
| G1.16 | P1 需要的 iface PR 已提交并有 DataAgent 调用证据 | V1.16 | P1 |
| G2.1 | 多概念本体模型可用 | V2.1 | P2 |
| G2.2 | 本体修订有影响分析、发布门禁与回退 | V2.2 | P2 |
| G2.3 | 本体发现能转成正式修订 | V2.3 | P2 |
| G2.4 | 多源数据进同一本体 | V2.4 | P2 |
| G2.5 | Agent 与下游能按本体查询 | V2.5 | P2 |
| G2.6 | 令才规则接通报销本体 | V2.6 | P2 |
| G2.7 | Ossie 多实体往返 | V2.7 | P2 |
| G2.8 | 本体与数据可视化 | V2.8 | P2 |
| G2.9 | 平台收敛到位（R4–R5） | V2.9 | P2 |
| G2.10 | 定义页可用 | V2.10 | P2 |
| G2.11 | 破坏性变更有门禁 | V2.11 | P2 |
| G2.12 | Skills 包可用（Q7 选 A 时纳入退出条件） | V2.12 | P2 |
| G2.13 | 关系与本体发现有正式基线（B18） | V2.13 | P2 |

### 2.2 非目标

1. P1 不做：多实体本体与本体修订发布（P2）；新来源类型（MySQL、Hive、对象存储、飞书表格等，P2 起按需）；增量与定时（P5）；质量规则（P3）；令才审核结论的对错验收（需专家金标，P3）；食品安全场景（等数据）；写回源系统与 MintHub 分发（P6）；平台层改名与存储、打包收敛（P2）。
2. P2 不做：指标与规则的计算语义（P4）；质量规则执行（P3）；本体推理（OWL 推理机）与外部本体平台对接（Q4）；多租户共享本体（P6）；跨工作区的知识登记（Q5）；令才审核结论的业务验收（P4）；GUI 内嵌视图（P6）。

## 3 方案判定

### 3.1 判定标准

1. 用户可见：每期结束用户能做一件之前做不了的事，在安装产物上验收。
2. 可追溯：展示给用户或下游的每个值都能追到来源锚点与修订。
3. 可证明：没有真值的场景用 [04](<04 验收方法与数据.md>) 的三层数据、五种方法分别报数，不合成一个准确率。
4. 不过拟合：核心与领域包按三条硬规则分界（[04](<04 验收方法与数据.md>) §5）。
5. 协议共建：平台缺口在平台层先绕行，同时向 agent-kernel 提 PR（[03](<03 平台方案与 iface 共建.md>) §8）。

### 3.2 推荐与理由

1. **P1 收口已有实现，不再扩写**：方案 16 的接入能力已写完，缺的是安装后验收、双端、平台阻断和可复核的数。P1 只补这些。
2. **P1 就引入令才真实报文**：令才现状的瓶颈是取数与字段映射（可判定率 11.8%），正是多源接入要解决的问题；但只做接入与映射，不判对错。
3. **P2 的本体按 Palantir 的结构补齐，保留我们的证据链**：值类型、二元链接加关系对象、动作化审核与日志、破坏性变更门禁、定义页；逐字段锚点与多来源断言是两家都弱的地方，保留（[02](<02 借鉴 Palantir Ontology 与 Databricks Genie.md>) §1）。

## 4 改动清单

| # | 改动 | 文件或模块 | 现状 | 期 |
|---|---|---|---|---|
| FR1.1 | 识别 8 类文件并探查：结构、样本、字段统计、页类型、表块；扫描页走本地 OCR；失败页不影响成功页 | `dataagent-data/.../observation/` | 已实现；Excel、JSON、混排 PDF 未在安装产物上验收 | P1 |
| FR1.2 | SQLite、PostgreSQL、REST 有界读取；主键、唯一键、外键；分页与续跑；不接受用户 SQL | `dataagent-data/.../adapters/sources/`、`observation/` | 已实现；双端发起未验收 | P1 |
| FR1.3 | 每次读取存不可变快照；每个字段带锚点；报告抽样、缺口、未完成分区 | 同上 | 已实现 | P1 |
| FR1.4 | 推断请求只含获准字段；默认最小披露（Q3）；Agent 回交映射提案，组件校验试算；只问影响结果的歧义 | `dataagent-workbench/.../inference_requests.py` | 默认无白名单时全部字段、前 5 行样本和 PDF 前 5 页文字摘录（每页 2000 字）进模型 | P1 |
| FR1.5 | 跨源同一业务键对齐；复合键不拼字符串；冲突保留两条断言并阻止保存 | `dataagent-ontology` | 已实现 | P1 |
| FR1.6 | 网页：来源预览、映射详情、对象页、当前值纠正、映射修订、草稿自动保存、刷新恢复 | `dataagent-workbench/web`、`view_service.py` | 对象页 `ObjectPage`、`view_service.py` 与两份 e2e 缺 | P1 |
| FR1.7 | 连接按名字选；凭据按逻辑名由宿主或钥匙串解析，只进探查子进程（R3） | 平台层 `policy/secrets`；`wb/adapters/source_connections.py` | 现为环境变量 | P1 |
| FR1.8 | 单次工具调用在宿主超时前返回，长探查分段续跑；所有工具带效果注解；一个 MCP 服务框架（R2） | 平台层 `tool/`；`wb`、`ops` 的 MCP 入口 | 未做 | P1 |
| FR1.9 | 同结构二次接入复用已验证映射，多来源也复用 | `wb/intake_service.py` | 单来源已实现 | P1 |
| FR1.10 | 全新工作区从 preset 安装；OCR 作为显式依赖；`dataagent setup/doctor` 检查 Python、uv、OCR 引擎与模型版本 | `dataagent-cli/bin/dataagent`、`dataagent-workbench/tools/build_bundle.py` | 装包与 setup/doctor 已实现；OCR 按目录是否存在静默打包，doctor 不查 OCR | P1 |
| FR1.11 | 评测运行入口 `dataagent run --case <用例> --out <目录> --config <配置>`，在安装产物上跑一条 09-benchmark 用例，写 `result.json` | `dataagent-cli/bin/dataagent`；`dataagent_runtime/interfaces/bench.py` | 不存在（探索轮 `x003` 记 failed） | P1 |
| FR1.12 | 目标字段目录接入：把外部规则字段目录作为领域包导入，用通用映射能力把来源字段映射上去；令才 ql-audit 规则字段目录为第一例 | 领域包 `lingcai-expense`（新增）；`scripts/verify_local.py` 新阶段 `lingcai-payloads` | 不存在 | P1 |
| FR1.13 | 评测任务 B16 多源对齐、B17 字段映射（含令才私有子集）、B19 令才变异集：数据、转换器、判分器 | `docs/research/dataagent-2026-11-03/09-benchmark/` | 只在计划里 | P1 |
| FR1.14 | 领域包与领域词检查：采购本体移出工作台核心；核心包源码领域词 CI 检查 | `wb/bootstrap.py:35`、`wb/ontologies/`；新增检查脚本 | 采购本体写死在核心 | P1 |
| FR1.15 | 向 agent-kernel 提 PR-1 至 PR-4 | agent-kernel（独立 clone） | 未提 | P1 |
| FR1.16 | R0：代码入库、导入守卫、iface 基线、干净检出测试修复 | 全仓；`packaging/iface-baseline.toml` | 分支未推送；data 1 项、CLI 1 项测试失败 | P1 |
| FR1.17 | R1：调用上下文唯一解析，主体与用途不由调用方自报 | 平台层 `types/`、`policy/context.py`；10 处调用点 | 至少 10 处来源 | P1 |
| FR1.18 | R3：外发闸门覆盖 MCP、CLI、推断请求三个出口；HTTP 客户端统一；工作台探查经注册表与访问复检（不进 P1 退出条件，可顺延 W3） | 平台层 `policy/egress`、`env/http` | 3 套闸门、3 套客户端；`candidate_spans` 未过闸 | P1 |
| FR2.1 | `OntologyRevision` 扩为多概念：概念、属性（类型、必填、单位、枚举）、身份字段、关系（有序角色、基数）、约束、状态机；兼容读取现有单实体格式 | `dataagent-contracts/.../ontology.py`、`dataagent-ontology` | 单实体 | P2 |
| FR2.2 | 修订流程：草案来源 4 种（网页编辑、本体发现、Ossie 导入、Agent 提案）；校验；有权限的人审核；发布；回退；数据发布补当前发布指针和未决、排除清单 | `dataagent-ontology/.../service.py` | 本体范围的审核只存草案；`DatasetRelease` 只有 id、修订、预览引用、摘要 | P2 |
| FR2.3 | 兼容性分类与影响清单：新增、改名、删除、类型或单位变化、约束变化；受影响的映射、实例、已发布批次 | `dataagent-ontology` | 无 | P2 |
| FR2.4 | 本体发现扩到文件（Excel 多表、JSON 嵌套）和 REST；发现草案一键生成正式修订草案 | `wb/ontology_discovery.py`、`discovery_catalog.py` | 只有 SQLite，确认后只存草案 | P2 |
| FR2.5 | 领域本体包：采购、报销，各自含定义、说明、示例映射；工作台从已装包和工作区修订中选择目标本体 | 领域包；`wb/bootstrap.py` | 包内固定一个 | P2 |
| FR2.6 | 映射支持多概念：一个来源映射到多个概念并生成关系事实 | `dataagent-ontology/.../mapping.py` | 单概念 | P2 |
| FR2.7 | 查询工具：`ontology_describe`、`object_query`、`relation_query`、`fact_trace`，只读、带发布修订、分页 | `wb` MCP 与 CLI | 无 | P2 |
| FR2.8 | 令才对接：读取 ql-audit 规则集，Agent 提出规则到本体属性的绑定提案，人审核；在测试数据上运行，结论引用本体对象 | 领域包 `lingcai-expense` | 无 | P2 |
| FR2.9 | Ossie 交换扩到多实体和关系，附损失报告 | `dataagent-ontology/.../adapters/ossie.py` | 单实体 | P2 |
| FR2.10 | 网页 6 个视图：本体结构图、对象页、关系图、映射视图、血缘视图、修订差异视图；大图分页与折叠 | `dataagent-workbench/web` | 只有映射与来源视图 | P2 |
| FR2.11 | 值类型：可复用的带约束语义类型（正则、范围、枚举、单位），用于映射校验和 P3 质量规则 | `dataagent-contracts`、`dataagent-ontology` | 无 | P2 |
| FR2.12 | 链接与关系对象：二元链接标明基数（1:1、1:N、M:N）；多元事实建成关系对象，再用二元链接连到各角色（Q9） | 同上 | 只有多元有序角色，无基数 | P2 |
| FR2.13 | 审核动作化：当前值纠正、映射修订、本体修订、发布都是带参数和提交条件的动作；成功提交记日志，日志可按对象查询 | `dataagent-ontology/.../service.py` | 审核记录不可查询 | P2 |
| FR2.14 | 破坏性变更门禁：换主键、改类型或单位、删已有编辑的属性等，未定义迁移不能保存 | 同上 | 无 | P2 |
| FR2.15 | 定义页：术语、缩写、业务概念的权威定义（负责人、同义词、相关对象与指标、依据锚点）；草稿 → 发布 → 认证或弃用；查询工具引用（Q8） | 同上 | 无 | P2 |
| FR2.16 | 对象引用：工具结果与回答用「对象类型 + 主键 + 发布修订」引用对象，点开到对象页，再追到来源锚点 | `wb` | 无 | P2 |
| FR2.17 | R4–R5：存储、环境与扩展收敛；平台层改名 `dataagent-platform`；抽出 Python 组件 SDK | 全仓 | — | P2 |
| FR2.18 | 评测任务 B18 关系与本体发现 | 09-benchmark | 只在计划里 | P2 |

## 5 接口变更

| 接口 | 变化 | 期 |
|---|---|---|
| MCP 工具 | 所有工具带 `readOnlyHint` / `destructiveHint` / `idempotentHint`；工具 schema 里 `context` 改为可选，调用参数里的上下文只作提示；长调用超时前返回 `retry_probe` 与续跑句柄 | P1 |
| CLI | 新增 `dataagent run --case/--out/--config`；`dataagent doctor` 输出 OCR 引擎与模型版本 | P1 |
| 验收脚本 | `verify_local.sh` 新增 `lingcai-payloads` 阶段；`files` 阶段扩到 8 类样本；`sources` 阶段加哨兵凭据 | P1 |
| 连接配置 | 连接清单只存逻辑名；凭据按 `env:`、`keychain:`、`file:` 逻辑名解析；PR-3 合入后改为宿主注入 | P1 |
| agent-kernel | PR-1 `ToolSpec` 效果等级；PR-2 MCP `_meta` 调用元数据；PR-3 bundle `capabilities.secrets`；PR-4 打包桌面版 bundle 工具可见 | P1 |
| MCP 工具 | 新增 `ontology_describe`、`object_query`、`relation_query`、`fact_trace`；审核与发布工具改为动作形式（参数 + 提交条件 + 日志） | P2 |
| 契约 | `OntologyRevision` 多概念、值类型、链接与关系对象、定义页；`DatasetRelease` 加发布指针与未决、排除清单 | P2 |
| 包 | `dataagent-runtime` 改名 `dataagent-platform`（保留一个版本的再导出）；新增 Python 组件 SDK | P2 |

## 6 验收指标

| # | 命令或操作 | 期望结果 | 期次 |
|---|---|---|---|
| V1.1 | 全新工作区：`bash scripts/verify_local.sh --phase files --ocr-root <OCR 目录>`（files 阶段扩到 8 类样本与独立期望文件，新增） | 退出码 0；每个样本的 `coverage` 与独立编写的期望文件一致（混排样本为 `partial` 且缺口页号一致）；每条记录的每个字段都有锚点；test-inventory 的 M1-04、M1-05、M1-06 在安装产物上为「已验证」 | P1 |
| V1.2 | `bash scripts/verify_local.sh --phase sources --postgres-locator <只读库>` | 退出码 0；REST 第 1 页请求次数 = 1，第 2 页 429 后续跑完成；M2-01 至 M2-04 在安装产物上为「已验证」 | P1 |
| V1.3 | `bash scripts/prepare_acceptance.sh && bash scripts/verify_local.sh --phase sources --postgres-locator "$PG_LOCATOR"`（跨源样本组与金标见 07 的 T25） | 对象数、冲突数与独立金标一致；冲突对象保存返回阻断问题；M2-05 为「已验证」 | P1 |
| V1.4 | TUI、GUI 各做一次 C-01 与 C-02（05 §4.2），证据摘要写入 `16-local-ingestion-workflow-build/evidence-{tui,gui}.md`（07 的 T50、T51） | 证据包含发起、网页纠正、返回聊天保存、发布引用、所用审批策略；M1-09、M1-10、M2-06 为「已验证」 | P1 |
| V1.5 | 默认审批配置下做一次 C-01，确认次数记入 `evidence-tui.md` | 全流程人工确认不超过 3 次，只读类工具不弹确认；依赖 PR-1，未合入时登记外部阻断 | P1 |
| V1.6 | sources 阶段的连接加哨兵凭据（新增），再从 Mint TUI 跑一次同样的接入；然后 `grep -r <哨兵值>` 工作区（除 `.dataagent/secrets/`）、`~/.mint` 会话日志、工具结果文件 | 0 命中；`intake_status`、`intake_inference` 输出不含凭据字段；GUI 部分依赖 PR-3 | P1 |
| V1.7 | 二次接入（单来源、多来源各一例）；30 MB 级样本接入；M1-08、M2-04 复跑 | 预览里 `mapping_reused=true`；单次 `intake_advance` 墙钟小于 55 秒且分段完成；M1-08、M2-04 为「已验证」 | P1 |
| V1.8 | `bash scripts/verify_local.sh --phase bootstrap`；`dataagent doctor`；在安装目录 grep 开发仓绝对路径 | 退出码 0；doctor 输出 OCR 引擎与模型版本；grep 0 命中；M1-01 为「已验证」 | P1 |
| V1.9 | 一次目标用户无提示操作观察（方案 16 §10），记录写入 `ux-observation.md`（07 的 T52） | 记录首次预览时间、完成时间、主动操作、澄清轮次、重做次数；10 MB 以内文件首次预览不超过 60 秒，澄清不超过 2 轮（Q2） | P1 |
| V1.10 | `bash scripts/test_all.sh`；`python3 scripts/check_layering.py --baseline scripts/layering-baseline.json`；`python3 scripts/check_domain_words.py`；`python3 scripts/check_tool_annotations.py --servers data,application,governance,workbench,operations`（均为本期新增） | 干净检出后各包测试无失败；业务包不导入适配器；代码里只剩一个 `resolve_context()`；所有工具 `tools/list` 带效果注解；S0 评审 r41 的 X1–X3 复现脚本全部被拒；核心包领域词 0 命中 | P1 |
| V1.11 | `16-local-ingestion-workflow-build/r1-review.md`（本期产出，07 的 T53） | 结论为「可验收」，区分已修复、部分修复、新缺陷，附复现输入与 `file:line` | P1 |
| V1.12 | `python3 tools/new_round.py --label p1-intake --model <模型> --kernel agent-kernel@<sha>`；对 B02、B03、B16、B17 各跑 `python3 -I harness/run.py --task <任务> --adapter dataagent-cli --round-id <r001 轮次号> --config harness/config.local.json`；`python3 tools/set_baseline.py`；`python3 tools/check.py`（07 的 T37） | 校验通过；四个任务的主指标（`text_ned`、`value_f1`、实体对 F1、映射 top-1 准确率）都有分数并写入基线；门槛按 Q10 | P1 |
| V1.13 | `bash scripts/verify_local.sh --phase lingcai-payloads --dataset "$LINGCAI_DATASET" --ql-audit "$QL_AUDIT" --version <规则包版本> --scenes common,8.5,8.8 --mapping <Mint 会话导出的映射>`（新增，07 的 T34b、T35） | 29 份报文全部接入，每个字段有 JSON Pointer 锚点；按前置与后置 QL 计算的静态可判定率从 11.8%（3683 次中 435 次）提升到门槛（Q11）；新补字段证据可核验率 100%；映射不上的字段逐项分类（报文缺失、空数组、目录未注册、名称不一致） | P1 |
| V1.14 | V1.13 的命令加 `--repeat 2`；引擎重跑结果写入 `$PRIVATE_DIR/lingcai/baseline/`，仓库存摘要（07 的 T36） | 两次的快照摘要、映射结果、可判定规则集合逐项一致；引擎重跑记录规则版本、引擎版本与结果快照（缺地址与凭据时登记外部阻断） | P1 |
| V1.15 | B19：`python3 -I harness/run.py --task B19 --adapter dataagent-cli --round-id <轮次号> --config harness/config.local.json`（07 的 T33） | 6 类变异（超标金额、日期越界、跨单重复发票号、购方名称不符、税号不符、缺必需附件）各正反成对；检出率与干净单误报率达到门槛（Q11）；漏检逐条归因到接入、映射或规则 | P1 |
| V1.16 | 在 03 §8.3 的 PR 表登记 PR-1 至 PR-4 的提交链接与合入状态（07 的 T40–T42） | 已在 agent-kernel 提交（或按 03 的 Q5 提交设计笔），附一致性测试与 DataAgent 调用证据；合入状态登记在 03 §8.3 | P1 |
| V2.1 | `uv run --frozen --extra dev --project packages/capabilities/dataagent-ontology pytest`（含新增 `tests/test_ontology_model.py`） | 全部通过；报销本体至少 5 个概念、4 条关系并通过校验；旧单实体 `procurement.json` 仍可读 | P2 |
| V2.2 | 新增 `tests/test_revision_impact.py`；网页操作一次录屏 | 把采购本体「金额」单位从元改为分后，影响报告的映射数、实例数与金标一致；重验前发布返回阻断问题；回退后发布指针等于上一修订，审核历史条数不减 | P2 |
| V2.3 | `bash scripts/verify_local.sh --phase discovery`（新增断言）；文件与 REST 发现样本 | 确认草案后生成本体修订草案、审核后发布成功；文件与 REST 发现各一组通过；M2-07 在 TUI、GUI 各由真实模型生成草案（本机模型不可用时登记外部阻断） | P2 |
| V2.4 | 接入报销样本组（制度 PDF、票据 PDF、行程 REST、历史报销 SQLite、员工 Excel） | 各概念对象数、关系事实数与金标一致；任取 20 个属性值，`fact_trace` 都能追到来源锚点 | P2 |
| V2.5 | 20 道独立编写的查询金标，分别经 MCP 与 CLI 执行 | 两个入口结果一致，准确率不低于 95%，每条带发布修订；TUI 一次真实会话证据包 | P2 |
| V2.6 | 令才规则绑定与运行 | 引擎可判规则绑定到报销本体属性的比例达到门槛（Q6）；未绑定规则逐条列原因；测试数据上的每条结论引用对象 ID 与来源锚点 | P2 |
| V2.7 | M4-05 的交换用例扩到多实体与关系 | 全部通过；损失报告列出不可移植项 | P2 |
| V2.8 | `npm --prefix packages/capabilities/dataagent-workbench/web run test:e2e`（新增 `ontology-schema`、`object`、`graph`、`lineage`、`revision-diff` 五个用例） | 全部通过；1000 个节点的关系图首屏不超过 2 秒（Q2）；TUI、GUI 各一次「打开同一任务 → 看图 → 点到原件」录屏 | P2 |
| V2.9 | 旧工作区迁移读取测试；统计 SQLite 文件；`git ls-files packaging/bundle/src`；安装目录 grep 开发仓路径 | 迁移测试通过；SQLite 文件不超过 3 个；git 中没有副本；grep 0 命中 | P2 |
| V2.10 | 定义页检查；复用 V2.5 的查询金标 | 采购、报销各至少 20 个定义页，均有负责人、同义词、依据锚点；草稿未发布前查询工具不返回；命中术语的题目回答引用了对应定义页 | P2 |
| V2.11 | 新增 `tests/test_breaking_change.py` | 换主键、改类型、删已有纠正的属性三种变更，未定义迁移时保存被拒；定义迁移后保存成功且旧纠正按迁移落到新属性 | P2 |
| V2.12 | 安装接入、本体审核两个 skill 包，跑各自的标准答案用例 | skill 只引用本体与定义页条目 ID，不复写定义；各至少 5 个用例在 Mint TUI 跑通 | P2 |
| V2.13 | B18 正式轮次 | 关系召回与精度、身份键选择准确率有分数并写入基线 | P2 |

## 7 风险、依赖与退出条件

### 7.1 依赖与绕行

| 依赖 | 谁 | 没到位时 |
|---|---|---|
| 代码入库（T00） | payne（本机） | 无绕行；crew 无法派工 |
| PR-1 工具效果注解 | 李奕杉、李鹏越 | V1.5 登记外部阻断；验收记录所用审批策略 |
| PR-3 bundle 凭据 | 李鹏越 | 连接清单路径写包内 `.mcp.json` 字面值；凭据用钥匙串逻辑名；GUI 下仍不通则登记外部阻断 |
| GUI 工具通道（PR-4） | Mint GUI 负责人 | 11-18 核实；不通则登记外部阻断并升级，TUI 先验收 |
| PR-2 调用元数据 | 李奕杉 | 本机 `local-owner` 作为唯一主体，fail-closed |
| agent-kernel 写权限 | kernel 组 | 先提设计笔与需求，由对方实现（03 的 Q5） |
| 令才引擎地址与凭据 | payne | V1.14 的引擎重跑部分登记外部阻断；V1.13、V1.15 用本地确定性检查 |
| B16、B17 公开数据的许可 | 我们 | 换候选集，在 manifest 里如实记缺口 |
| ql-audit 规则集与报销测试数据 | ql-audit 子项目 | P2 的 G2.6 顺延 |
| 本机模型 | payne | G2.3 的真实模型部分登记外部阻断 |

### 7.2 核心包需求排期

| PR（缺口编号） | 最晚需要 | 用在 | 没到位时 |
|---|---|---|---|
| PR-1（B1） | P1（W2） | G1.5 | 登记外部阻断 |
| PR-2（A1） | P1（W2） | G1.10、G3.3 | 本机单用户 fail-closed |
| PR-3（B2） | P1（W2） | G1.6、G1.4 | 钥匙串逻辑名绕行 |
| PR-4（GUI 通道） | P1（W1 核实） | G1.4 | 登记外部阻断 |
| PR-5（A2） | P2 | 本体审核、令才澄清 | 返回 → 网页操作 → 再调用 |
| PR-6（B4） | P3 | G3.4 | 本地事件日志 |
| PR-7（B3、A5） | P5 | G5.3、G5.4 | 本机常驻进程 |
| PR-8（B7、B8） | P6 | G6.4、G6.5 | 单用户；目录约定定位 |
| A6 审计 | P3 | G3.4 | 本地审计日志 |
| A4 逐请求出网 | P3 | G3.3、远程 OCR | 组件自带白名单；远程 OCR 停用；评估 `agentcpm/net-proxy` |
| A3 文件与进程围栏 | P6 | 多人使用 | 组件自查路径 |
| A7 知识登记 | 看 Q5 | 跨应用复用本体 | 查询工具（FR2.7） |
| B5 组件侧模型调用 | P5 | 后台任务里的语义判断 | 挂起等 Agent |
| B6 GUI 内嵌视图 | P6 | G6.5 | 外部浏览器 |

### 7.3 积木选择

MintHub 上的候选与判断见 [03](<03 平台方案与 iface 共建.md>) §11。P1 不引入新积木：OCR 继续用 `dataagent-ocr`（03 的 Q4），出网代理 `agentcpm/net-proxy@0.1.0` 等 A4 排期时再评估。

### 7.4 非功能需求

| 类别 | 要求 |
|---|---|
| 安全 | 凭据不进模型、日志、结果、截图；来源内容不当指令；外发只经一个闸门；本机服务只听 127.0.0.1，校验 Origin 与一次性令牌 |
| 可追溯 | 所有展示值可追到锚点与修订；所有写入带期望修订和主体 |
| 可恢复 | 进程重启、宿主超时、限流、部分失败都能从断点续跑，不重复建对象、不重复提交 |
| 性能 | 单次工具调用小于 55 秒；10 MB 文件首次预览不超过 60 秒；1000 节点图首屏不超过 2 秒（Q2） |
| 兼容 | 旧工作区数据可读；旧单实体本体可读；接口改名保留一个版本 |
| 隐私 | 令才等私有数据不进 Git；报告与飞书只出现聚合计数 |
| 证据 | CI 通过不等于人工验收；源码通过不等于装包通过；每期验收附证据包 |

### 7.5 退出条件

1. **P1**：G1.1–G1.3、G1.6–G1.8、G1.10–G1.13、G1.15、G1.16 全部通过（G1.10 不含 FR1.18）；G1.14 的组件回归部分通过，引擎重跑部分通过或登记外部阻断；G1.4 的 TUI 部分通过；G1.4 的 GUI 部分、G1.5、G1.9 通过，或登记为外部阻断且有升级记录。分支合入 main，宿主指针更新。
2. **P2**：G2.1–G2.11、G2.13 全部通过（G2.12 看 Q7），或 G2.3 的真实模型部分登记为外部阻断；独立评审「可验收」。

## 8 待拍决策

| | 决策 | 选项 A | 选项 B | 推荐 | 影响 |
|---|---|---|---|---|---|
| Q1 | P1「接入完成」的口径 | 来源观测 + 映射到预设本体 + 用户确认保存发布（沿用方案 16 M1、M2） | 只到来源观测（快照、锚点、完整性），映射放 P2 | A | B 让 P1 更快，但 P1 交付物对用户没有可用对象 |
| Q2 | 体验与性能门槛 | 首次预览 ≤ 60 秒（10 MB 内）、澄清 ≤ 2 轮、关系图 1000 节点首屏 ≤ 2 秒 | 先只记录不设门槛，P3 定 | A，P1 观察后可调 | 无门槛则 G1.9、G2.8 不可判 |
| Q3 | 模型可见范围的默认值 | 默认最小披露：没有白名单时只给字段名和统计，样本需显式允许 | 维持现状：没有白名单时全部字段、前 5 行样本和 PDF 页文字摘录进模型 | A | A 对映射准确率有影响，需在 V1.9 观察 |
| Q4 | 是否对接外部本体平台或标准 | P2 只做 Ossie 交换 | P2 同时对接 OWL / RDF 导入导出 | A；有明确客户需求再做 B | B 增加 P2 范围约 1 周 |
| Q5 | 本体是否登记到 OS 知识层 | 只在 DataAgent 内，下游用查询工具 | 发布指针登记到 `KnowledgeContract` | A | B 依赖 Mint 接入知识契约；知识契约是键值形态，不承载类型化查询 |
| Q6 | 令才规则绑定率门槛（G2.6） | 引擎可判规则中 ≥ 80% 绑定到本体属性 | 只报告比例，不设门槛 | A | 门槛过高会把本体做成为令才定制 |
| Q7 | Skills 包线（G2.12） | 接入、本体审核、问数、规则审计各一个 Mint skill 包，随对应期发布，带标准答案测试 | 只出问数一个 | A | 每期多一个交付物 |
| Q8 | 定义页放哪 | 本体的一类资产，随本体发布出版本，可导出 Markdown | 单独做成 Mint skill / 文档包 | A（FR2.15 已按 A 写） | B 更易分发，但与本体版本脱钩 |
| Q9 | 关系建模 | 保留多元有序角色，对外投影为「关系对象 + 二元链接」 | 只支持二元链接 | A（FR2.12 已按 A 写） | B 简单，但多元事实要拆开，丢掉「同一事实」 |
| Q10 | P1 首轮 benchmark 门槛（G1.12） | 首轮只建基线，门槛取基线值，之后只升不降 | 现在按公开榜单水平预设门槛 | A：现在没有任何基线 | B 若门槛定高，P1 可能卡在公开集上而不是真实问题上 |
| Q11 | 真实流程与变异集的门槛（G1.13、G1.15） | 可判定率 ≥ 40%；变异检出率 ≥ 95%、干净单误报率 ≤ 5% | 只报数不设门槛，P1 结束时定 | A；可判定率目标在第一次跑出现状后校准 | 可判定率上限受报文本身缺字段限制，40% 是否可达要先看缺口分布 |

## 9 参考资料

1. 方案 16：`docs/research/dataagent-2026-11-03/16-local-ingestion-workflow-build-plan.md`；验收矩阵 `16-local-ingestion-workflow-build/test-inventory.md`（`codex/16-local-intake@87d5e8e`）
2. 设计 14、15：`docs/research/dataagent-2026-11-03/design/`（worktree 未提交）
3. 09-benchmark 计划：`docs/research/dataagent-2026-11-03/09-benchmark-plan.md` v0.3
4. 令才数据集评估：盘点材料 `令才CU数据集-验收可用性评估.md`
5. DataAgent 实现与 iface 契约对照：`~/Vibe/AgentOS/docs/architecture/2026-11-16-DataAgent与iface契约对照.md`
