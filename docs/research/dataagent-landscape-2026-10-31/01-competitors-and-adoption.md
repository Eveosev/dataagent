# DataAgent 竞品、应用落地与证据边界

研究截止与访问日：2026-10-31，Asia/Shanghai。本文先把 DataAgent 视为“围绕数据完成可检查工作的智能体”，不预设某个平台、模块划分或安装形态。
复核基础：[2026-10-30 商业报告](../dataagent-2026-10-30/01-commercial-landscape.md)；复用其来源线索，并重新获取关键官方正文。旧报告中将 DataAgent 先定义为某平台 bundle 的前提不沿用。

**补充修订：** 原十产品表遗漏了 dbt 的 AI 产品线，只在语义技术层研究 dbt 不足以覆盖其产品。现补入第十一项，并新增 [dbt AI 专题](05-dbt-ai-addendum.md)。竞品与可集成基础设施是两个可交叠的维度。

## 1. 范围、方法与结论

- **D：厂商技术文档**，支持入口、配置、行为契约和公开限制；不等于租户实测。**M：营销页**，支持厂商定位和承诺。**U：使用方自述**，支持该组织的经历；仍可能有选择性披露和供应商关系。**I：研究判断**。
- 未登录商业租户、执行第三方产品代码、测 SQL 正确率或核验合同。没有统一测试集，不制作准确率排行榜，不把采用量当质量提升。
- 本环境没有专用 web search 工具。使用公开 Google/Bing 页面与官方导航发现资料，再以 urllib 读取实际正文；搜索页部分返回挑战页、泛化结果或连接中断，因此发现范围不完整，搜索摘要和搜索 AI 总结均不作为能力证据。
- 正文、提取文本及访问记录保存在 [sources](sources/) 的 `competitors-*` 文件；[访问索引](sources/competitors-source-index.json) 包括失败与重试。持续更新文档的“更新时间”不等于功能上线日期；未标日期一律明示。

**最重要的判断（I）**：目前可靠的落地点是有边界的数据任务：围绕已准备的业务语义问数、对授权数据进行探索、把分析变成可检查的代码/图表/报告。公开证据尚不足以证明“任意脏数据、任意业务问题、无人准备、无人验收”的通用自主分析已经成熟。

**更具体地说**：平台正在从“自然语言生成 SQL”扩展到文件、文档检索、Python、多步任务和报告交付；与此同时，指标定义、数据选择、来源认证、权限和反馈修复仍由组织负责。竞争焦点已经包含“谁维护业务事实、怎样纠错、怎样交付与复用”，而不只是对话界面。[S1–S3][D1–D5][L1][F1][H1–H5][U1]

## 2. 先看应用形态，再看产品

| 应用形态 | 用户实际上希望完成的工作 | 典型产品 | 可靠落地的前提与交付 |
| --- | --- | --- | --- |
| 企业自助问数 | 查询销售额、漏斗、留存、分组变化，追问明细 | Cortex Analyst、Genie、Looker、FineChatBI | 已授权且语义清晰的数据；输出查询、表格、图表与定义 |
| 业务调查与诊断 | 解释变化、拆解贡献、结合客户记录和文档找线索 | Cortex Agents、Spotter、Hex | 多步取证、可信来源、限定分析方法；输出过程和可复核证据，不能把相关/贡献直接称为因果 |
| 文件即席分析 | 清洗导出表、合并文件、统计与可视化 | Julius、ChatGPT、Hex、Genie | 用户提供文件、问题与口径；输出清洗副本、计算与图表；个人文件授权不自动变成企业共享资产 |
| 分析工程协作 | 写/改 SQL、Python，建立可继续维护的分析项目 | Hex Notebook Agent、dbt Wizard/Copilot | 编辑权限、代码与数据上下文、逐项审阅；输出项目/cells 或 dbt 变更，可继续编辑与复跑 |
| 周期业务交付 | 汇报、简报、仪表板、监控与通知 | Quick BI 小Q、ChatGPT Work、Looker 部分 Preview 工作流 | 明确数据更新、定时运行环境、收件/分享授权与验收；交付物和任务执行分开治理 |

这些形态会组合，但不能仅因产品都叫“agent”就视为同一种能力。例如 Fabric data agent 明确只读取数，不能因为同平台有 notebook 就推断它能触发训练或异常检测任务。[F1]

## 3. 十一个代表产品的入口、准备与交付

| 产品与定位 | 用户入口、数据与语义准备 | 公开任务范围与交付 | 权限、验收与边界 |
| --- | --- | --- | --- |
| **Snowflake Cortex Analyst / Agents** | Analyst 为 API 优先；可接自建聊天/Streamlit/Slack/Teams。Agents 可在 Snowsight 配置，经 API、自有应用及 Snowflake 界面使用。先定义 Semantic Views 的实体、维度、指标、关系和例题 | Analyst 生成结构化数据 SQL；Agents 编排 Analyst、Search、Python、图表、自定义工具与 MCP，返回回答及工具过程 | Analyst 遵循 Snowflake 角色/对象权限；Agents 还取决于每个工具的执行上下文，不能把所有工具都写成终端用户身份。VQ 评测见下文 [S1–S3] |
| **Databricks Genie Agents** | 领域聊天、外嵌应用/API；现名，原 Genie Spaces。作者选择 UC 表/view/metric view（最多 50 个），配置 SQL、业务表达式、join 与说明 | 返回 SQL、结果表、图表；Agent mode 处理多步探索；CSV/Excel/PDF 可与 UC 数据同会话分析 | 数据按终端用户 UC 身份，计算使用配置作者嵌入的 warehouse 凭据。可编辑 SQL、反馈、benchmarks；verified answer 有特定受信资产条件 [D1–D5] |
| **Looker Conversational Analytics** | Explore 对话、最多五个 Explore 的 data agent、dashboard agent、嵌入/API。开发者维护 LookML；agent 可附术语表、指令与 verified queries | agent 选择字段/过滤/排序/limit，由 Looker 编译执行；可生成表图。Explore 路径的 Advanced Analytics 可执行 Python；dashboard agent 不支持它 | 查询遵循 LookML 的 join、聚合和数据权限；分享 agent 不授予底层数据访问。普通问数限制与 Python 路径不同；触发/定时工作流仍有 Preview 标识 [L1] |
| **Microsoft Fabric data agent** | Fabric 发布/分享的配置项；可接 Microsoft 365 Copilot、Teams、Foundry 等。选最多五个来源与相关表，添加说明/例题 | 为 lakehouse/warehouse、Power BI 语义模型、KQL 等选择查询工具，生成/校验/执行 SQL、DAX、KQL；输出对话洞察 | 文档明确 GA，但 Purview 部分能力 Preview。按请求者身份，只读；不直接读取裸文件/非结构化文档；对话最多 25 行×25 列、英语、跨区域限制 [F1] |
| **ThoughtSpot Spotter** | 聊天、Liveboard、嵌入及连接器；先准备 TML 数据模型、业务定义、instructions、memory 与外部上下文 | 简单问题走 tokens；复杂查询可走 AgentQL→QGen→SQL；Python 保留用于预测/回归与跨 model 结果拼接；提供 Show work 与回答卡 | AgentQL 继承模型 RLS/CLS；不是直接对裸表自由 SQL。部分路径尚不能 pin 到 Liveboard；不同 Spotter 版本能力不同，不能拿 Spotter 3 覆盖旧版本 [T1–T6] |
| **Hex** | Threads、Notebook、Slack、CLI/MCP 等；仓库、语义模型、文件、已有项目；数据团队维护 guides、endorsements、models | Notebook Agent 生成/修改 SQL、Python、pivot、chart 等 cells，能整理/发布 app；交付可编辑的分析工程与应用 | Notebook Agent 需编辑角色/项目权限，逐 cell Confirm/Undo，且自身不运行在 published app 内。Governed mode 是来源引导，安全靠真实连接权限；有 eval suites [H1–H5] |
| **Julius** | 文件/聊天起步，也可配置数据库、仓库与广告连接器；连接级 instructions、filtered schemas 与 learned information | 执行 Python/R、SQL、schema 检索，产出图表、报告、演示/网页等；代码步骤可展开查看，生成文件可下载 | 连接器可团队共享；过滤按连接器统一生效，未选时默认 ALL；共享 schema 学习可查看/冻结/删改，未核到正式发布审批/回归门禁。数据使用须按隐私条款核对 [J1–J7] |
| **ChatGPT 数据分析 / Work** | 本次官方可取得材料是现行 ChatGPT Work 文件、Sites 和工作流文档；通过附件/源链接与授权 app 提供数据 | 清理 CSV/表格副本、附质量说明；从电子表格制作私有交互 dashboard，配置定时检查；可交付表格/文档/演示/PDF | 官方示例要求检查变更、缺失行、匹配和分享权限；连接以授权账户为边界，共享/agent-owned 账户不等于请求者本人权限。未将这些文档外推为所有传统 ChatGPT 套餐同样可用 [O1–O4] |
| **Quick BI 智能小Q** | BI 统一入口路由问数/报告/解读/搭建等；数据集字段、聚合、知识、维值先准备；另有 Excel 即席入口 | 企业问数、仪表板解读、报告编辑与分享、业务分析模板；官方指南展示“Excel分析→加入报告”流程 | 问数配置权限与数据授权分别管理；字段质量建议需接纳并重新学习；可看业务逻辑 SQL/执行 SQL与反馈处理状态。多 Agent 模块需相应增购/权限 [A1–A3] |
| **FineChatBI** | 依托 FineBI 指标中心；管理员建指标并预加载，业务用户对话 | 意图/口径调整、模糊值确认、异常与波动贡献分析、明细下钻、多轮、折线预测、组件保存为 dashboard | 可查看问答思路与确认歧义；本次概述不足以证实全链路权限传播、原生回归评测或预测方法。不能称任意裸库即开即用 [R1] |
| **dbt AI：Wizard / Copilot / MCP** | Wizard 平台、CLI/Desktop；Explore 供只读用户问生产数据；Copilot Insights；MCP 向外部 client 提供项目 metadata、指标、血缘和动作 | 开发/排障/验证与审阅；自然语言问数及多步查询；模型、指标、维度值和 lineage 工具 | Wizard 平台 Preview、CLI/Desktop Beta，Insights Beta；依赖已有项目与授权。Explore 可回落共享 analytics credential；MCP execute_sql 不阻止写语句。详细来源与差异见 [dbt 补充 B1–B9](05-dbt-ai-addendum.md) |

## 4. 技术证据与产品宣称之间的距离

### 4.1 语义准备仍是主要投入，但也出现自动辅助

- **D** Snowflake Semantic Views 显式定义业务实体、度量与预定 join；Looker 把 LookML 当 source of truth；FineChatBI 以指标中心为基础；Quick BI 要设置字段、聚合、维值和知识。这些不是“只接数据库就能理解企业业务”的证据。[S1][L1][R1][A2]
- **D** Genie 不是全手工：会查相关热门查询，自动保存 UC 已声明的主外键为 join，分析作者点赞/下载行为并提出表达式和关系建议。局部 knowledge store 不回写整个 UC；文档仍要求消除冲突、审阅候选和修复错误。[D2][D3][D4]
- **D / M 分离** Julius 确有可见的 Learned Information，能刷新、冻结、增删，且共享 connector 汇总团队交互的 schema 知识；这是具体产品行为。其“10 人约 10 倍学习速度”表格没有公开方法和实测样本，属于效果宣称，不作为效率定律。[J4]
- **I** 自动发现的关系和高频 SQL 是候选证据；源表主外键声明、实际数据基数、业务粒度和时间有效性仍可能不一致。查询能运行不证明口径正确。

### 4.2 “确定性”需要定位到具体一层

- **M** Spotter 产品页称把问题编译成每次相同的 governed SQL。[T1]
- **D** AgentQL 技术页更具体：agent 自主选择 tokens、AgentQL 或 Python；AgentQL 是 TML 模型之上的语义查询，QGen 对这个中间查询进行确定性翻译，支持多步 CTE、排名、累计和跨实体指标。[T2]
- **I** 已明确的是“给定语义查询的编译”确定；没有证据证明自然语言每次必然选择同一模型、同一业务解释、同一分析路线。确定性编译也不能修复错误指标定义。
- **D** AgentQL 页同时写了逐步 rollout、早期/未来阶段说明；初期回答为总结/表，图表、pinning 和参数有未完成项。不能将路线图条目写为全面可用。[T2]
- **D** Looker 标准路径同样避免自由拼整个 SQL：模型选择字段与过滤，Looker 处理 join/aggregation/access grants；Python 进一步分析查询结果。这支持“受约束取数＋开放分析”共存。[L1]

### 4.3 查询校验、结果验收与业务验收是三件事

| 产品 | 已有验收机制（D） | 不应外推的结论 |
| --- | --- | --- |
| Snowflake Analyst | 从 VQ 选择题集；评测时移除被测 VQ；执行生成与参考 SQL，并由版本化 SQL correctness judge 评分；观察回归与延迟 | 不是严格 SQL 文本相等，也不是无模型的精确结果集判等。只评单 semantic view、独立单轮；VQ 需人工准备，judge 版本不同分数不可直接比较 [S3] |
| Genie | Chat mode 对照参考 SQL 结果；Agent mode 用 LLM judge，可提供 evaluation note；无 SQL answer 的 Chat 题需人工评；benchmarks 最多 500 题 | 同产品不同模式的“准确率”也非同一口径。benchmark 以新会话运行，不证明多轮上下文可靠；Chat 结果最多比 5,000 行可能引入截断误判 [D4] |
| Hex | YAML suite，可检查完整轨迹/最终回答，也可用数值容差或 SQL ground truth；可 preview 上下文后评测、发布及定时运行 | 拥有工具不代表每家客户已经建立合适题集与门禁；LLM rubric 判过不等于所有数字、因果和建议真实 [H4][U1] |
| Fabric | 查询生成工具做格式、安全及 RAI 验证；可用诊断、日志、Git 与 deployment pipelines 管理配置 | “validated query”不等于满足业务口径；产品团队内部 benchmark 没有在本次概述公开可复算题集 [F1] |
| Quick BI / FineChatBI | 查看 SQL/分析思路、点赞点踩、处理用例、口径纠偏和歧义确认 | 反馈入口和人工纠错不等于已有自动回归门禁或端到端正确性证明 [A2][A3][R1] |

### 4.4 反馈会不会自动改变共享事实，产品间差别很大

- Genie 原文：`behavior does not change based on user feedback alone`。普通反馈可触发再生成和审阅流程；作者的特定行为可产生知识候选，不能把“所有用户点赞都会训练全局事实”写成结论。[D2][D4]
- Julius 明确存在共享 connector 的自动 schema 学习，同时提供 freeze/delete/manual additions；文档说共享的是结构和关系，不是实际值。未核到按角色审批、证据保留、冲突解决和版本回滚细节。[J4]
- Hex 管理面允许观察话题/警告、维护 guides/endorsements/models，并在发布前测试；LangChain 的部署实践仍以观察和人工审阅为主，正式 evals 是待加入项。[H3][H4][U1]
- **I** 应分别询问“个人偏好是否记住”“团队上下文是否更新”“认证指标是否改变”“是否需要审阅与回归”，不能用一个“会学习”覆盖四种机制。

### 4.5 权限也不是一句“继承企业权限”就结束

- Genie 将 warehouse 计算授权与 UC 数据授权分开；分享 agent 不扩大用户数据权限。但上传文件又有独立存储/保留/LLM 数据路径：仅上传者能读，文件留到用户移除或会话/agent 删除，部分内容发给外部模型。[D3][D5]
- Hex 明确写 `Governed mode isn't a security control`。它强引导可信来源，真实隔离依赖 connection permissions；同一项目的 Notebook、published app 与 scheduled run 文件持久化也不同。[H2][H5]
- Spotter 文档说明会向 LLM 发送问题、模型元数据和样本值；Spotter 3 也使用查询结果，默认高级分析缓存及保存会话另有保留期。营销的“zero copy / data stays where it is”不能理解为没有样本/结果外发或缓存。[T1][T5]
- Julius 的 filtered schemas 默认未选择任何项即暴露全部表列，且过滤对共享连接的所有使用者一致；不同权限集建议建不同 connector。本次没有证据证明共享连接自动透传每位终端用户的数据库身份。[J2]
- Julius 隐私说明明确应按适用协议判断数据使用，公开描述允许向 AI provider 分享内容以及 opt-out 途径；它与连接器页的概括性“data never leaves your control”需要联合阅读。本文未取得受限审计报告或客户合同，不能认证实际合规状态。[J1][J5]
- ChatGPT Work 官方区分个人与共享/agent-owned 连接：后者按连接账户权限，可能超出请求人的个人权限。可访问 agent 不是已获得所有数据的逐人授权。[O4]

## 5. 真实采用：LangChain 使用 Hex 的客户自述

**U** Emily Hawkins 于 2026-07-27 在 LangChain 自家博客公开其数据栈迁移，属于使用方的一手叙述；LangChain 同时为 agent 生态供应商，文中提到与 Hex 的合作互动，不是独立对照实验。[U1]

| 主题 | 文章实际说明 | 能支持的判断与限制 |
| --- | --- | --- |
| 原始问题 | 三人数据团队接收一次性查询，找模型、写 SQL、校验和回传成为瓶颈；不同用户分别需要 dashboard、notebook、SQL、聊天 | 需求是多入口的数据消费和首轮分析，不止“替业务人写 SQL” |
| 选择与进入 | 选择 Hex 统一 dashboard、notebook、聊天；通过 Hex UI、Slack、CLI、MCP、LangSmith Fleet 使用 | 用户愿意采用与工作流入口有关，单一聊天页不覆盖全部人群 |
| 实际任务 | 营销周度 pipeline、产品使用趋势、销售/部署客户健康、客户工程 churn/expansion/account 分析 | 是业务即席探索的实际采用自述；没有逐题结果、错误率与业务收益审计 |
| 使用量 | 最近 30 天约 2,200 conversations；约三分之一员工开通 agent；已开通者近 100% 使用，平均约 23 次/月；自报约 40 倍原团队可处理请求量 | 分母是 provisioned agent users；不能写“100%员工都使用agent”。对话量≠成功答案量，40 倍不是经过配对验证的效率或准确率倍数 |
| 人的工作 | 业务先做 first pass；数据团队继续验证、更深分析和严谨决策；只有数据团队可 endorse，认证 dashboard 修改需审阅 | 自助扩大与专家验收共存，人员角色从响应请求转向维护语义与信任 |
| 上下文投入 | dbt SQL/定义、semantic models、GitHub 同步 workspace guides、认证资产、历史项目与 GitHub 逻辑 | 高使用量发生在持续上下文治理之后，不支持“零准备连接裸库即可复制” |
| 质量闭环现状 | 观察 usage、warnings 和 qualitative feedback；原文 `Next, we want to start leveraging evals` | **不能宣称 LangChain 已建立成熟自动 eval 回归闭环**，即使 Hex 产品本身已提供 evals |

**I** 这个案例有价值的地方是揭示落地工作量和组织分工。其采用量和迁移速度是可引用的客户自报；缺少失败样本、成功任务口径、成本、延迟和对照组，不能作为替代分析师或证明产品优于其他产品的依据。
本专题未找到足够可核验的独立负向用户样本来估计普遍失败率；厂商案例与文档中记录的限制不能替代这样的抽样。负面反馈与更多客户自述应另行交叉核查。

## 6. 当前较成熟的能力与仍难落地的部分（I）

| 能力/问题 | 本次证据下的成熟度判断 | 现场验收应观察什么 |
| --- | --- | --- |
| 已建模数据的常见问数、图表、追问 | 多家产品有具体配置、运行和权限文档，可开展受控试点；不是保证全部问题正确 | 指标口径、时间范围、去重、join 粒度、过滤值、可复现查询与业务验收 |
| SQL/Python 辅助与文件清洗 | 已有明确执行及交付形态，尤其适合分析师和提供明确目标的文件任务 | 原始行保留、合并覆盖率、代码/中间结果、清洗前后核对、环境与数据版本 |
| 复杂多步/结构化与文档混合分析 | 平台能力已出现，工具路径和产品版本差异明显 | 来源是否完整、检索遗漏、不同工具的权限身份、失败重试、成本及证据引用 |
| 周期报告、dashboard 与通知 | 可配置交付链存在；部分产品路径 Preview，运行条件与分享规则各异 | 刷新时间、任务真正执行地、断连/过期、数据截断、内容审阅和分发授权 |
| 任意未知数据的全自动语义理解 | 未证实；自动提议、schema 学习和关系声明已有进展，但人工定义/维护仍普遍 | 候选关系与实际数据是否一致、业务歧义、专家投入、发布前受影响题集 |
| 预测、归因、决策建议 | 入口存在≠统计可靠：Python、预测组件、贡献拆解是不同能力；未见统一回测证据 | 回测切分、基线、泄漏、误差/区间、外部冲击；贡献/相关/因果须区分 |
| 自动学习与共享知识治理 | 有局部成熟机制，没有统一解决；产品反馈、候选知识、自动学习、认证事实不能混用 | 知识作用域、来源、权限、冲突、错误传播、冻结/回滚与回归结果 |
| 安全与质量的全链路验收 | SQL RLS/CLS 只是其中一段，文件、采样、LLM、缓存、导出和共享账户各有边界 | 不同角色对 schema/样本/结果/历史会话/文件/下载做同一组越权用例 |

**落地难点的主次**：先明确哪类用户、哪类任务、哪份业务事实和哪种交付物可验收；再评价模型和工具。数据团队的语义准备/运维成本、业务用户表达与理解错误的成本、试错计算成本，都会决定“能演示”是否变成“愿意日常使用”。LangChain 的案例支持这一组织变化方向，不证明所有企业都能获得相同收益。[U1]

## 7. 本次来源账本

下面均为**实际读取的官方/客户正文**；访问日期统一为 2026-10-31 Asia/Shanghai。`未标`意指本次取得的正文未见发布日期；更新时间单列，不冒充首发日期。URL 后的 ID 对应正文引文与缓存。

| ID | 原始来源与类型 | 发布/更新日期、可用性与本次支持的事实 |
| --- | --- | --- |
| S1 | [Cortex Analyst](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst)，D | 发布/更新未标；200；Semantic Views、API、权限、结构化取数 |
| S2 | [Cortex Agents](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents)，D | 未标；200；工具编排、执行上下文、Python、MCP、成本/预算 |
| S3 | [Analyst evaluations](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluations)，D | 未标；200；VQ、judge版本、单轮/单view限制与费用 |
| D1 | [Genie Agents overview](https://docs.databricks.com/aws/en/genie-agents/)，D | 更新 2026-10-07；200；现名、入口、产品分工 |
| D2 | [Tune quality](https://docs.databricks.com/aws/en/genie-agents/tune-quality)，D | 更新 2026-10-09；200；knowledge store、trusted assets、mining与join |
| D3 | [Create/manage](https://docs.databricks.com/aws/en/genie-agents/set-up)，D | 更新 2026-10-09；200；50来源、双凭据、UC逐人权限 |
| D4 | [Test/monitor](https://docs.databricks.com/aws/en/genie-agents/monitor)，D | 更新 2026-09-17；200；反馈不自动改行为、Chat/Agent评测、5000行限制 |
| D5 | [File upload](https://docs.databricks.com/aws/en/genie-agents/file-upload)，D | 更新 2026-10-16；首次 SSL EOF，重试200；文件类型、权限、外部模型与保留 |
| L1 | [Conversational Analytics overview](https://cloud.google.com/looker/docs/conversational-analytics-overview)，D | 更新 2026-10-26；200，转 docs.cloud.google.com 同路径；LookML编译、Python、入口差异、Preview |
| F1 | [Fabric data agent concepts](https://learn.microsoft.com/en-us/fabric/data-science/concept-data-agent)，D | 显示更新 2026-05-11，HTML另有 updated_at 2026-10-21；200；GA、只读、权限、25×25、ALM |
| T1 | [Spotter产品页](https://www.thoughtspot.com/product/spotter)，M | 发布未标；HTML修改 2026-10-14；200，转 `/product/agents/spotter`；定位/预测/确定性宣称 |
| T2 | [AgentQL 26.10](https://docs.thoughtspot.com/cloud/26.10.0.cl/agentql)，D | 发布未标；200；QGen、Python保留、rollout与阶段限制 |
| T3 | [Spotter 26.10](https://docs.thoughtspot.com/cloud/26.10.0.cl/spotter)，D | 未标；200；版本、入口与功能差异 |
| T4 | [Getting ready 26.10](https://docs.thoughtspot.com/cloud/26.10.0.cl/spotter-get-ready)，D | 未标；200；instructions/model/memory/external context |
| T5 | [Security 26.10](https://docs.thoughtspot.com/cloud/26.10.0.cl/spotter-security)，D | 未标；首次超时、重试200；LLM数据、缓存与保留 |
| T6 | [Limitations 26.10](https://docs.thoughtspot.com/cloud/26.10.0.cl/spotter-limitations)，D | 未标；200；版本、参数、chart和上下文限制 |
| T7 | [26.10 release notes](https://docs.thoughtspot.com/cloud/26.10.0.cl/notes)，官方发布说明 | 页面说 now available，未标日；200；不同GA/EA/Beta状态，不能把版本号当确切发布日期 |
| H1 | [Notebook Agent](https://learn.hex.tech/docs/explore-data/notebook-view/notebook-agent)，D | 未标；200；cells、Confirm/Undo、项目、权限与published app区别 |
| H2 | [Upload files](https://learn.hex.tech/docs/connect-to-data/upload-files)，D | 未标；200；100文件、2GB、Notebook/app/scheduled持久化差异 |
| H3 | [Context Studio](https://learn.hex.tech/docs/agent-management/context-studio)，D | 未标；200；角色、观察、guides/endorsements/models |
| H4 | [Evals](https://learn.hex.tech/docs/agent-management/evals)，D | 未标；200；rubrics、SQL/numeric、preview、发布和schedule |
| H5 | [Governed mode](https://learn.hex.tech/docs/agent-management/governed-mode)，D | 未标；首次连接关闭、重试200；`isn't a security control`原文 |
| J1 | [Data connectors](https://julius.ai/docs/data-connectors/overview.md)，D，含营销措辞 | 未标；200；连接/共享/SQL形态；不能单用其“数据控制”概括代替隐私条款 |
| J2 | [Filtered schemas](https://julius.ai/docs/data-connectors/filtered-schemas.md)，D | 未标；200；默认ALL、共享作用域与不同连接器权限集 |
| J3 | [Connector context](https://julius.ai/docs/data-connectors/customize-connections.md)，D | 未标；首次超时、重试200；表、join与业务条件说明 |
| J4 | [Learned information](https://julius.ai/docs/learning-subagent/viewing-learned-information.md) / [Team effects](https://julius.ai/docs/learning-subagent/team-network-effects.md)，D，后者效果属M | 未标；均200；刷新/冻结/删改、团队schema共享；学习速度未独立验证 |
| J5 | [Privacy/data security](https://julius.ai/docs/get-started/privacy-and-data-security.md)，D | 未标；正文有截至2026-10-08安全资料状态；200；AI provider内容使用/opt-out、保留和合同提示，未取得受限报告 |
| J6 | [Sharing/downloads](https://julius.ai/docs/get-started/sharing-and-downloads.md)，D | 未标；200；私有/公开replay、生成文件、全聊天导出已停 |
| J7 | [Tools/capabilities](https://julius.ai/docs/get-started/tools.md)，D | 未标；200；Python/R、SQL、schema检索与多种交付，随模型/计划变化 |
| O1 | [Analyze-data-export](https://learn.chatgpt.com/use-cases/analyze-data-export.md)，官方示例 | 未标；200；标题现为保持更新的私有dashboard，虚构数据示例，不能当真实客户成效 |
| O2 | [Clean messy data](https://learn.chatgpt.com/use-cases/clean-messy-data.md)，官方使用指南 | 未标；200；清洗副本、行ID/质量说明与复核 |
| O3 | [Work with files](https://learn.chatgpt.com/docs/artifacts-viewer.md)，D | 未标；200；文件交付、预览与复核；不同端功能各异 |
| O4 | [Work cloud security](https://learn.chatgpt.com/docs/enterprise/chatgpt-work-cloud-security.md)，D | 未标；200；云/本地、授权路径、个人/共享账户权限和数据边界 |
| A1 | [小Q操作指南](https://help.aliyun.com/zh/quick-bi/user-guide/smart-q-home-page)，D | HTML原始日期2025-08-27、修改2026-03-16；200；统一路由、增购、模板、Excel→报告示例 |
| A2 | [数据准备](https://help.aliyun.com/zh/quick-bi/user-guide/prepare-data)，D | HTML原始日期2024-07-29、修改2026-03-20；200；字段/维值/知识/聚合和授权 |
| A3 | [问数运营](https://help.aliyun.com/zh/quick-bi/user-guide/ask-the-number-of-operations)，D | HTML原始日期2024-10-23、修改2025-08-27；200；SQL追踪、反馈与处理标记 |
| R1 | [FineChatBI简介](https://help.fanruan.com/finebi7.0/doc-view-2572.html)，D | 更新2025-11-27；200，转finebi路径；指标准备、歧义、归因/预测/仪表板 |
| U1 | [LangChain: The agent data stack](https://www.langchain.com/blog/agent-data-stack)，U | Emily Hawkins，发布2026-07-27；200；使用量、组织准备与evals待建设；不是独立产品对照 |

## 8. 访问异常、时间边界与未验证项

- ThoughtSpot `cloud/latest/spotter` 成功但重定向到 `26.11.0.cl`；版本号不足以证明具体发布日期，且可能越过研究截止口径，**本报告不采用其新增能力**，改用成功取得的 `26.10.0.cl` 固定版。26.10 文档仍是访问时内容，不是历史网页快照。
- ThoughtSpot 旧候选 `sage-setup`、`spotter-training`、`sage-configure.html` 均404；`spotter-deploying`连接中断；`spotter-coaching-options`只给HTML迁移提示，已沿提示成功读取 `spotter-get-ready`。不把404等同能力不存在。
- Julius 首页与 `/docs` 本次均200，可通过 `/docs/llms.txt` 找到markdown正文；旧报告的Cloudflare访问失败不能继续当成当前资料不可得。文档自己提示在重建，页面间概括承诺不能凌驾于具体条款。
- 官方 OpenAI 搜索尝试包括 Google/Bing；Google挑战/JS页、Bing泛化结果未作为证据。`learn.chatgpt.com/search?q=data%20analysis`404；之后通过官方首页/文档索引和实际页面核实。API Code Interpreter 页面虽成功抓取，不用于证明ChatGPT套餐能力。
- 尚未验证：各产品具体地区/租户/套餐可用性、完整定价、私有网络与身份传播实测、模型升级回归、复杂跨源join完整性、预测可靠性、团队学习错误传播、合同与实际保留承诺，以及可代表总体用户的满意度/失败率。
- **优先复核三项主张**：① Spotter 的确定性只到哪一层、AgentQL各限制在目标租户是否仍存在；② Snowflake/Genie/Hex的评测判据、版本和多轮覆盖，能否支撑实际业务验收；③ LangChain的高采用量能否在保留人工验证成本、错误率和使用分母后仍证明收益。当前证据支持探索这些问题，尚不足以给出统一胜负。
