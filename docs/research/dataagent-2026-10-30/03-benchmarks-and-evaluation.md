# DataAgent Benchmarks 与 MintHub 分层评测建议

调研日期：2026-10-30，Asia/Shanghai。
范围：文件/API/MCP 数据探查、版本化 ontology、关系发现、表字段值召回、NL2SQL、BI/表格分析与预测。
证据口径：本次实际读取官方仓库 README、评估器源码、项目页及 arXiv 摘要/HTML；没有运行 benchmark，没有取得私有数据或读取凭据。
下文“建议”均为待实施方案，不代表 MintHub 已具备相应能力或已经通过测试。

## 1. 结论与选型

1. 没有一个已核验 benchmark 覆盖“陌生文件/API -> ontology -> join -> 召回 -> SQL -> BI/预测”的完整产品链路。
2. 企业 SQL 优先参考 Spider 2.0 与 BEAVER；值理解参考 BIRD；业务知识与规则变更参考 LiveSQLBench。
3. 多轮澄清应单列 BIRD-Interact；SQL 修复应单列 BIRD-CRITIC，不能当作普通一次 NL2SQL。
4. 文件分析组合 InfiAgent-DABench、DSBench、SpreadsheetBench；复杂分析与开放结论参考 DataSciBench、DiscoveryBench。
5. 预测采用时间序列专用 backtest；GIFT-Eval/Monash 检验预测函数，产品端还需检验目标、粒度、时间窗口、未来协变量选择。
6. ontology 正确性、join cardinality、权限、API 分页一致性与版本迁移必须补充 MintHub 自有测试集。

本报告不列模型排行榜：不同数据版本、oracle schema、交互预算、scaffold 与指标的成绩不能直接混比。

## 2. 已核验 Benchmark 概览

| 项目 | 任务单位与核验规模 | 主要覆盖 | 应保留的设置区别 |
| --- | --- | --- | --- |
| Spider 2.0 | 当前 README：Lite 547，Snow 547，DBT 68 | 企业 SQL 工作流、长 schema、多方言 | Lite/Snow/DBT；SQL 或 CSV；oracle tables |
| BIRD | 12,751 问题-SQL 对，95 库，37 领域，33.4 GB | 值理解、外部知识、脏数据、SQL 效率 | 原始 SQLite 与后续多方言 Mini-Dev；有无 evidence |
| LiveSQLBench | Base-Lite 270/18库；Base-Full-v1 600/22库；Large-v1 480/18库 | HKB、SELECT 与管理操作、规则漂移 | 具体 release、库大小、知识格式与 SQL 范围 |
| BIRD-Interact | Full 600；Lite README 270、最新论文摘要 300 | 歧义澄清、跟进需求、主动探索 | c-Interact/a-Interact、预算、simulator 版本 |
| BEAVER | 2026-05-13 摘要：9,128 对、812 表、19 领域 | 私有企业来源 schema、隐式 join、细粒度诊断 | 真实/合成组成、四种数据配置、oracle hints |
| BIRD-CRITIC | Open 570/4方言；PG 530；Flash 200；SQLite 500 | 用户 SQL issue 诊断与修复、DBA、优化 | 不把总览 600+200 OOD 与公开配置混为一套 |
| DSBench | 466 分析任务、74 建模任务 | 大文件、多表、长背景、多模态、建模 | ModelOff 分析与 Kaggle 建模不同评分 |
| InfiAgent-DABench | 257 问题、52 CSV | 执行环境中的闭式数据分析 | DAEval 数据与 InfiAgent 框架不是两个 benchmark |
| SpreadsheetBench | 912 指令、2,729 测例；Verified 400 子集 | 真实 Excel 操作、多 sheet、非规范布局 | 完整集/Verified；单轮/多轮；重算后评分 |
| DataSciBench | 论文 v1：222 prompts、519 GT 测例、6类任务、25种聚合函数 | 清洗、探索、绘图、建模、解释报告 | prompt 成功率与子任务完成率、代码/VLM评价 |
| DiscoveryBench | 264 真实任务/6领域，903 合成任务 | 从数据发现并验证关系/假设 | Real/Synth、facet score、oracle feedback |
| GIFT-Eval / Monash | GIFT 当前提交97种配置；Monash 30数据集/58变体 | 跨领域、频率、预测跨度与概率预测 | 预训练/zero-shot/fine-tuned、数据泄漏、horizon |

规模只引用本次读到的对应版本。任务数、数据库数、表数、测例数不是可互换的分母。[S1-S19]

## 3. 企业 SQL 与交互评测

### 3.1 Spider 2.0

- 论文首次发布于 2024-11，摘要描述 632 个企业工作流问题；这不是当前各变体任务数的加总。
- 当前 README：Lite 547，包含 BigQuery 214、Snowflake 198、SQLite 135；Snow 547 全部在 Snowflake；DBT 68 使用 DuckDB/dbt。
- 2025-05 官方以 DBT 设置替换原始 Spider2 设置，DBT 测的是仓库级代码修改；Lite/Snow 是 SQL 工作流。
- 输入包含问题、数据库环境与元数据，复杂题可能需要检索文档、探索数据、生成多条 SQL；并非提供全量 schema 的一次补全题。
- Lite 评估套件支持预测 SQL 执行或直接提交 CSV，与 gold 结果比较；配置包含 `condition_cols`、`ignore_order`。
- 本次静态读取的比较器采用逐列向量匹配、`1e-2` 数值容差，且存在多 gold 结果路径；它的通过不等于所有行关联和业务约束均正确。
- 官方另发 gold tables；使用它们必须报告 `oracle tables`，否则会掩盖 MintHub 的表召回问题。
- 2025-10 官方修复过评估器，2025-07 修订过 Snow 问题；复现必须冻结任务与 scorer 版本。
- 2026-08-12 README 公告 Snowflake 评测账号发生 suspension；这是可用性风险记录，本次没有登录验证是否恢复。
- 适用：长 schema、方言、文档搜索、工具探索、工作流成本；盲点：原始 Excel 结构识别、ontology 生成、企业权限与跨系统 join。
- 启动建议：先跑可取得数据的本地子集，云端作为独立阶段；不能把本地子集成绩标为完整 Spider 2.0。[S1-S3]

### 3.2 BIRD

- 2023 年论文与官方 README 均说明：12,751 问题-SQL 对、95 库、37 领域、33.4 GB。
- 单位是给定数据库的问题；数据有 schema/value 描述、专家外部知识 `evidence` 与 gold SQL，原始发布环境为 SQLite。
- 特点是值理解、脏值、NL 与编码值之间的映射及效率，对 MintHub 的值召回与编码字典很有参考价值。
- 主要评估 EX；VES 在正确性约束下评估执行效率。它受硬件、缓存、超时和重复运行策略影响，不能当作模型独立常数。
- 本次读取原始官方 `evaluation.py`：`set(predicted_res) == set(ground_truth_res)`，会忽略行序与重复行。
- 因此财务明细、Top-N 排序与重复计费任务需额外检验；某个固定实例同结果也不能证明 SQL 对所有数据等价。
- 有无 evidence、完整 schema/检索 schema、是否执行反馈与候选采样必须分别报告。
- 官网 2026-10-28 公告 Mini-Dev SQLite/MySQL/PostgreSQL 标注修订；不要沿用旧缓存后宣称是最新 Mini-Dev。
- 官网 2026-10-09 将 BIRD 2.0 与 LiveSQLBench 2.0 标记为开发中，并提到 semantic modeling；不能把路线图计为可用 ontology 测试集。
- 适用：低成本 SQL 回归与值映射；盲点：陌生数据接入、交互、权限、长期语义模型。公开训练/开发集也存在污染风险。[S4-S6]

### 3.3 LiveSQLBench

- 官方定位为持续更新、降低污染风险的 SQL benchmark；“contamination-free”是项目设计目标，不是任意模型天然无污染的证明。
- 2025-05 Base-Lite：18 库270任务，其中180 SELECT、90管理任务；当前 README仍明确该 release。
- 2025-09 Base-Full-v1：22 库600任务；2026-03 Large-v1：18 库480任务，约千列/库，含 Business Rule Drift。
- README旧 comparison 表仍出现 Large-Full 600任务/22库等规划数字；本报告采用明确标注已发布的 Large-v1 数字。
- 输入结合 schema、值与 hierarchical knowledge base（HKB）；知识有依赖关系，SQL需利用业务规则而非仅匹配列名。
- SELECT 用 Soft EX，管理操作用定制 test cases；PostgreSQL 环境与 SQLite Lite 派生版需分开报告。
- DB 管理任务必须隔离初始快照，记录最终数据库状态；不能只看返回行或“执行无错”。
- 动态发布/隐藏测试机制有助于降低记忆优势；每次发布还需记录知识版本与发布日期，避免旧规则混入新结果。
- 适用：ontology/业务文档作为上下文后能否被正确使用、规则变更回归、大 schema 压力；盲点：并未直接证明从任意原始源创建正确 ontology。
- 建议借其 HKB 设计构造“规则 v1 -> v2 -> 相同问题不同正确答案”测试，并保留源码/API证据。[S7]

### 3.4 BIRD-Interact

- 首次论文 2025-10；本次 arXiv 摘要元数据更新于2026-03-24。Full均为600任务。
- 版本冲突必须保留：仓库 README Lite为270，最新摘要 Lite为300；未下载逐项 manifest，本报告不自行断言二者相同。
- 每任务含歧义初始问题和跟进问题；系统可探索数据库、取知识并与 function-driven user simulator 交互。
- `c-Interact` 是预定义的被动对话协议；`a-Interact` 由 agent决定何时提问、查库、提交，不能合并成一种“多轮准确率”。
- agent README：两阶段奖励0.7/0.3；预算由 starting、ambiguity resolution和user patience构成；baseline starting=6、patience=6。
- 因此 normalized reward、整任务通过率、阶段通过率不是同一指标；同模型不同预算也不是同一实验。
- 2026-03新增 ADK实现；agent文档标明 Lite论文用simulator prompt v1、Full用v2，单样例旧代码维护不足。
- 可执行 test cases作为主要监督；GT/test cases部分需邮件申请，不能把公开输入误当作完整可复现套件。
- 仓库警告数据库初始化可能静默失败而得到空库；评测前需库表/行数/约束健康检查。
- 适用：提问时机、信息增益、需求追踪、交互成本；盲点：simulator语言与耐心假设不等于真实业务用户，仍需人工复核对话样本。[S8-S9]

### 3.5 BEAVER

- 论文最早2024-09；本次最新摘要日期2026-05-13，规模已为9,128问-SQL对、812表、19领域，不应引用早期小规模数字。
- 来自三套匿名企业仓库的真实query logs/生产报表，并以 Structural Template Recomposition 扩展，经专家验证。
- 因而“来自私有企业环境”与“全部自然发生、未经合成的9,128条查询”不是同一事实；真实/扩展组成应分组。
- schema可能含难懂命名、隐含join与领域知识，和企业API落成表后的MintHub情形较接近。
- 五项诊断：多表召回、join key detection、column mapping、domain knowledge extraction、query decomposition。
- repo提供 `dw`、`dw_real`、`nova`、`neutron` 配置；数据在gated Hugging Face，评估使用MySQL环境。
- `setting=0` 检索表；`setting=1` 提供gold表/列映射/join key；`setting=2` 再给领域知识/分解提示。
- 粗粒度为执行结果准确率；细粒度从SQL提取信息后对照标注，分解还使用LLM judge，需要冻结judge与rubric并人工校准。
- 适用：定位“召回错/关联错/语义错/SQL结构错”；盲点：只标join key仍不等于验证many-to-many fanout、时间有效性和指标可加性。
- 其源码与gated数据须各自核对使用条款；论文许可不能推定为可随商业bundle分发的数据许可。[S10-S11]

### 3.6 BIRD-CRITIC / SWE-SQL

- 2025-06论文名SWE-SQL；任务是给出用户issue、buggy SQL与环境，诊断修复，不是从零回答业务问题。
- 当前repo：Open 570跨MySQL/PostgreSQL/SQL Server/Oracle；PG 530；Flash 200；2026-03新增SQLite 500。
- 总览还写开发600、OOD200，不能与上述公开配置直接相加；BigQuery表述为100-200，本次不采用不确定分母。
- 数据包括preprocess/cleanup、gold SQL、test cases、效率标签及可能的external JSON，适合测试SQL修复工具链。
- SELECT用Soft EX，特定需求可加parsing；CRUD用定制状态测试；优化题可用Query Execution Plan检验算法层面成本。
- QEP不是完整实际运行时延，环境、统计信息和引擎版本仍需固定。
- 2026-01官方修订`remove_distinct`；GT/test cases部分经邮件提供。需保存实际取得的版本和许可。
- 适用：执行失败恢复、约束/触发器、方言修复；盲点：有buggy SQL通常已给出了相关表，不能用此成绩证明表召回能力。
- MintHub若首版只读，先选只读修复子集；管理任务作为隔离的扩展能力测试。[S12]

## 4. 文件、表格与分析评测

### 4.1 DSBench 与 InfiAgent-DABench

- DSBench（2024-09）：466分析任务来自ModelOff相关竞赛资料，74建模任务来自Kaggle，覆盖长背景、多模态、大文件及多表。
- 分析侧参考最终答案判断；本次读取`compute_answer.py`，其中以`gpt-4o-2024-05-13`作为答案judge，而非纯确定性数值比较。
- 建模侧按各竞赛指标评分，论文使用Relative Performance Gap；不同竞赛原始accuracy/RMSE不能直接平均。
- 适用：从文件到分析/预测产物的完整流程；盲点：Kaggle已整理的数据与业务API取数不同，且公开竞赛答案/解题代码可能污染。
- 官方README明确数据仅限教育/研究、商业需许可；可借鉴评测方法，不应直接打进商业preset。[S13]
- InfiAgent-DABench（2024-01，ICML2024）：DAEval为52个CSV上的257个分析问题；InfiAgent/DA-Agent是框架/基线。
- 以constraints与format把开放问题改成闭式答案，自动比对答案标签；README提供LLM reformat步骤，需独立记录其成本与错误。
- 本次读取`eval_closed_form.py`：答案支持字符串相等或`1e-6`数值容差；无response的题未加入结果列表。内部复用时须固定全任务分母、漏答计失败。
- 适用：文件读取、统计、过滤、聚合的快速回归；盲点：闭式提示降低真实歧义，CSV不能覆盖Excel布局/公式，也不充分覆盖跨源join。
- 数据许可显示CC BY-NC4.0；不把代码Apache2.0许可误认为数据可商业再分发。[S14]

### 4.2 SpreadsheetBench 与 SpreadsheetLLM

- SpreadsheetBench（2024-06/07，NeurIPS2024）：真实Excel论坛912指令、2,729测例，平均约3个输入变体/指令。
- 包含多sheet、单sheet多表、非规范关系布局和非文本元素；OJ式评价要求同一方案处理变值输入。
- 2025-12新增专家标注Verified400子集；它与完整912应分开报告，不能仅写“SpreadsheetBench分数”。
- 评测读取输出位置/文件；公式必须经Excel或LibreOffice重算并缓存，`openpyxl`读到公式字符串不等于计算正确。
- 单轮与ReAct/执行反馈多轮设置不同；还应冻结工作簿引擎、locale、日期系统与数值容差。
- 适用：文件结构探查、范围操作、公式与导出；盲点：通过目标格不必然证明其他单元格/格式/公式引用未受损。[S15]
- SpreadsheetLLM是编码方法论文，首次2024-07，本次读v2（2025-04），不是与SpreadsheetBench等价的产品评测套件。
- SheetCompressor用结构锚点、逆索引、数据格式聚合；CoS先定位相关表范围，再把该范围输入模型回答。
- v2表检测测试为188工作簿/311表，EoB-0要求四边界精确匹配；这是结构识别指标，不能当作复杂Excel编辑成功率。
- 适用：检验“压缩前后保留了什么”与表边界识别；任何token节省需与范围召回/漏值/业务正确率一起测。[S16]

### 4.3 DataSciBench 与 DiscoveryBench

- DataSciBench（2025-02）论文v1：222 prompts、519个GT测例、6种任务、25种聚合函数；不要把测例数当成独立用户任务数。
- 来源包含真实平台请求、BigCodeBench改写、人工与LLM合成；覆盖清洗、探索统计、可视化、建模、模式发现、解释报告。
- Task-Function-Code（TFC）把任务拆成可评价函数/代码；GT由LLM self-consistency与人工核验构建。
- 同时看全部TFC通过的success与部分completion；图表使用VLM judge，代码执行无错、文件存在不能代替结论正确。
- 适用：为MintHub分析函数设计逐产物评分；盲点：预定义TFC未覆盖的正确答案可能被漏评，judge与GT也需误差抽检。[S17]
- DiscoveryBench（2024-07）：264真实任务、6领域，另有903合成任务；输入为数据、元数据与发现目标。
- 输出是数据支持的假设；facet评价区分context、variables、relationships，组合为Hypothesis Matching Score。
- 论文含NoDataGuess检查仅凭背景记忆猜结论，并将oracle反馈反思单列；这两种对照值得复用。
- 适用：解释和洞察是否指向正确人群/时间/变量/关系；盲点：与已发表假设匹配不是因果证明，也可能漏掉另一条有效发现。
- 业务BI应额外检查效应量、样本量、不确定性、多重检验与数据证据，避免把相关性写成因果。[S18]

## 5. 预测函数的独立评价

- Monash官方页：30数据集、58频率/缺失值变体；主要报告MASE，另有RMSSE等。MAE/RMSE跨单位不可直接总体平均。
- GIFT-Eval（2024-10）覆盖7领域、秒至年、单/多变量与短/长跨度、概率预测；当前README要求提交97种dataset/frequency/term配置。
- 论文摘要另给23数据集、超过144,000条序列、177百万数据点；这是数据规模，不是97种预测任务配置的替代分母。
- GIFT区分pretrained、zero-shot、fine-tuned；zero-shot不仅不得泄漏test，也不使用该数据池的train split。
- GIFT另标testdata_leakage和复现代码；必须同时报告checkpoint、训练语料可知范围和已知重叠，不能仅称“零样本”。
- Chronos是预测模型家族，当前含Chronos/Chronos-Bolt/Chronos-2；Chronos-2于2025-10支持单/多变量及协变量任务，不是完整DataAgent benchmark。
- 对MintHub先测“取对序列/聚合频率/目标/未来已知信息”，再测预测器误差；这两层应能独立替换。
- 使用rolling-origin backtest，训练/验证/测试按时间隔离；填补、缩放、异常处理、特征工程只在训练窗口fit。
- 未来协变量必须在预测时真实可知；库存盘点、结算后状态、最终促销效果不能作为过去可用特征。
- 至少保留naive、seasonal-naive、简单统计模型及一个可用预训练模型；比较MASE/RMSSE、业务加权误差和分位损失/覆盖率。
- 时间序列冷启动、节假日、结构变化、缺失、不规则间隔、零销量与层级一致性需分组；不确定性与运行成本也须报告。[S19-S21]

## 6. MintHub 应自建的分层评测

| 层 | 离线单位/标注 | 指标与必须覆盖的反例 | 端到端验收证据 |
| --- | --- | --- | --- |
| 接入与探查 | 源快照、文件/分页响应、schema/profile真值 | 表范围/类型/空值/唯一性；分页丢重、JSON嵌套、locale、API限流 | 可重放源摘要、行数/页数、来源/采样范围 |
| ontology | 实体、粒度、指标口径、维度、单位、证据、版本 | 语义precision/recall、证据覆盖、置信校准、冲突/未知识别 | 每个业务术语能定位源字段、规则与审核状态 |
| join/cardinality | gold可接受join图/键/谓词/基数/有效期 | edge P/R、fanout、覆盖率；复合键、桥表、同名异义、慢变维 | 关联前后行数、聚合守恒、时态谓词证据 |
| 表字段值召回 | 问题与允许的table/column/value集合 | recall@k/MRR、必要集合全召回率、token预算；编码/别名/桥接表 | 实际传入规划器的上下文及漏召回归因 |
| SQL与业务正确 | 接受的结果/业务约束/多数据变体 | 解析/执行率、严格结果正确率、口径正确率、查询成本 | SQL、dialect、参数、数据/ontology版本、结果hash |
| 多轮交互 | 歧义槽位、可回答澄清、跟进依赖 | 澄清命中/无谓提问、任务完成、轮数、矛盾恢复 | 信息来源、采纳约束和最终回答可审计 |
| 权限与隔离 | principal/tenant/role/row/column策略矩阵 | 越权读取/推断/导出/写入；缓存、采样、检索、日志 | 每次工具调用授权结果，禁止内容未进入模型上下文 |
| BI/表格 | 指标、过滤、图形/透视表/工作簿约束 | 数值、单位、轴/排序/分母、公式重算、无关区域完整性 | 可复算数据与文件，图表追溯至查询/源 |
| 预测 | as-of数据、窗口、目标、horizon、baseline | 防泄漏、backtest误差/覆盖率、业务损失 | 训练截止、特征可知性、模型与预处理版本 |
| 运行与版本 | trace、组件/工具/数据/策略版本 | 成本、p50/p95、失败/重试、取消、更新失效 | 对同一固定快照重放，展示新增/退化案例 |

join正确性不能只用列名相似、值交集或LLM评分；自然存在多个有效join路径时，标注应允许等价实现并限定业务粒度。
无声明外键不等于不能关联；相同ID值也不证明语义可关联。负例应包括重用编码、不同租户与不同日期的相同键。
小样本profile应输出采样范围与不确定性；低置信关系应允许待审核/拒绝合并，不能为追求recall自动发布。
ontology版本测试应含改名、类型变化、枚举新增、单位/币种切换、指标定义变化、表拆并、删除与权限撤回。
版本变更后同时测增量发现、旧引用兼容、受影响查询失效/迁移、回滚与lineage，防止继续使用陈旧缓存。

建议保留三条独立轨道：冷启动从原始源生成ontology、已审核ontology上的问答、逐项提供gold表/列/join/口径的诊断轨道。
三条轨道共用下游任务，但分别报分；诊断轨道用于估计瓶颈，不可当作冷启动产品成功率。
ontology与关系标注由了解业务的两人独立审阅并仲裁，接受等价命名/图结构；不以生成该ontology的同一模型自评作为唯一真值。

## 7. 结果等价、污染与可比性规则

- SQL字符串exact match仅作诊断；有序结果比row tuples，无序结果按bag/multiset比，保留重复行及列间关系。
- 明确NULL/NaN、时区、decimal精度、舍入、排序tie、Top-N和空集规则；财务用单位相关容差，不统一套`1e-2`。
- 用变值测例/反例数据区分错join、错误DISTINCT、漏条件、偶然空集同值；不能简单把“返回相同数字”当作业务正确。
- SQL执行前后数据状态分开；权限、写入和危险动作测试必须有独立策略判定，业务答案正确不能抵消越权。
- gold答案与测试断言不能进入agent可见的工具返回、索引、示例或memory；simulator按协议提供澄清/反馈，评估工具与agent工具分权限运行。
- 公开数据仅作可比研究轨道，另留企业授权、近期生成、盲测的私有任务；按source/schema/template切分，防止近重复泄漏。
- 记录model精确版本、prompt/scaffold、temperature、预算、重试、候选数、schema/知识/evidence、工具权限、缓存冷热及scorer版本。
- 全部请求保留在固定分母；漏答、超时、预算耗尽与工具失败分类记录，不能静默删除失败任务后算正确率。
- 任务成功报pass@1及固定预算多次运行分布；不能将多候选oracle选择的pass@k作为用户一次会话成功率。
- 以源/任务簇进行bootstrap或置信区间并报告分层分母；几十条样本上的小幅涨分通常不足以宣称稳定提升。

## 8. 可启动测试集与 Gates（建议，尚未构建/运行）

建议首轮自建24个固定数据包，覆盖零售、制造、金融运营、医疗运营、物流、SaaS六类，每类4包。
每包3-12个文件/逻辑表，横跨Excel/JSON与API/MCP fixture；至少一半包含跨源join和模糊/缺失业务说明。
先做360条业务任务：60探查/ontology、60join/召回、120SQL/BI、40多轮、40表格、40预测；同源任务相关性通过分包切分/统计处理。
另叠加120个权限/隔离对抗用例和不少于12组ontology/data版本变化；这些变体不冒充新增独立业务问题。
建议按数据包拆为12开发、6冻结回归、6最终盲测；盲测按行业和复杂度分层，项目早期结果只作方向判断。
公开集研究轨道可先选BIRD/Spider本地各50、SpreadsheetBench Verified40、DABench40、Interact20；这些是拟抽样数，不是官方规模。
BEAVER与需GT邮件授权的数据集在取得可用artifact后加入；当前调研不代表已经完成授权或能立即全量运行。

| 建议 Gate | 初期门槛 | 解释 |
| --- | --- | --- |
| 数据/评测健康 | 缺失artifact、空库误载、label可见为0 | 先判环境有效，再计算能力分 |
| 权限隔离 | 120例中越权读取/泄漏/写入为0 | 有一例即阻断；0次观测不等于已证明零风险 |
| ontology/关系发布 | 高置信自动发布precision>=95%；来源证据覆盖100% | 对未证实项允许待审核；recall另报，防止全拒绝获高precision |
| 召回 | 必需表集合与必需字段集合全召回率各>=90% | 固定上下文预算，并单报桥表与值召回 |
| 业务任务 | 冻结集严格结果+口径通过率>=80%；每行业>=70% | 属建议试点门槛，不是行业标准或公开榜单结论 |
| 多轮/表格 | 各类别整任务通过率>=75% | 固定轮数/工具预算；公式重算及无关区域检查必须通过 |
| 预测 | 全部无泄漏；macro MASE不劣于seasonal-naive，另报关键序列退化 | 不强迫每条序列改善；基础数据/目标选错直接失败 |
| 版本与性能 | 关键回归零新增失败；其余退化逐案审查 | 以配对差异和置信区间定夺，避免小样本机械涨跌 |

延迟/成本先收集同环境baseline，再由产品SLO定gate；建议分开记录交互响应、完整分析、离线建模，禁止用平均值隐藏超时。
每次只替换一个主要组件并配对重跑：例如ontology、reranker、SQL agent、预测函数；再跑完整接入到产物的端到端轨道。
端到端成功必须同时满足业务结果、权限、来源证据与产物约束；可展示分层得分，不能用平均总分抵消权限失败。

## 9. 本次已读一手来源

以下均于2026-10-30实际抓取；`main`是可变引用，尚未将数据与评估器固定为可复现release/commit。

- [S1 Spider2 官方README](https://github.com/xlang-ai/Spider2/blob/main/README.md)，含变体、任务数、账号与scorer公告。
- [S2 Spider2 论文摘要](https://arxiv.org/abs/2411.07763)，原始632工作流口径。
- [S3 Lite evaluation README与实现](https://github.com/xlang-ai/Spider2/tree/main/spider2-lite/evaluation_suite)，读取README及`evaluate.py`。
- [S4 BIRD 官方项目页](https://bird-bench.github.io/)，含2026-10更新与开发中项目公告。
- [S5 BIRD 官方代码README及EX](https://github.com/AlibabaResearch/DAMO-ConvAI/tree/main/bird)，读取README、`llm/src/evaluation.py`。
- [S6 BIRD 论文摘要](https://arxiv.org/abs/2305.03111)，数据规模与任务定位。
- [S7 LiveSQLBench 官方README](https://github.com/bird-bench/LiveSQLBench/blob/main/README.md)，读取release、HKB、Soft EX与changelog。
- [S8 BIRD-Interact 官方README与agent设置](https://github.com/bird-bench/BIRD-Interact)，读取根README及`bird_interact_agent/README.md`。
- [S9 BIRD-Interact 最新摘要](https://arxiv.org/abs/2510.05318)，元数据更新2026-03-24。
- [S10 BEAVER 官方README](https://github.com/beaverbench/beaver/blob/main/README.md)，gated数据、四配置、三hint设置及五子任务。
- [S11 BEAVER 最新摘要与HTML](https://arxiv.org/html/2409.02038)，结合[摘要元数据](https://arxiv.org/abs/2409.02038)核对2026-05-13与真实/合成来源。
- [S12 BIRD-CRITIC 官方README](https://github.com/bird-bench/BIRD-CRITIC-1/blob/main/README.md)，配置数、数据字段、评分、许可与更新。
- [S13 DSBench 官方仓库](https://github.com/LiqiangJing/DSBench)与[摘要](https://arxiv.org/abs/2409.07703)，读取分析/建模README及`compute_answer.py`。
- [S14 InfiAgent-DABench 官方说明](https://github.com/InfiAgent/InfiAgent/tree/main/examples/DA-Agent)、`eval_closed_form.py`与[摘要](https://arxiv.org/abs/2401.05507)。
- [S15 SpreadsheetBench 官方README](https://github.com/RUCKBReasoning/SpreadsheetBench/blob/main/README.md)，完整/Verified规模、OJ式评分与公式重算。
- [S16 SpreadsheetLLM v2全文](https://arxiv.org/html/2407.09025v2)与[摘要元数据](https://arxiv.org/abs/2407.09025)，编码模块、CoS、188/311边界评价。
- [S17 DataSciBench 论文v1全文](https://arxiv.org/html/2502.13897v1)、[项目页](https://datascibench.github.io/)及[官方README](https://github.com/THUDM/DataSciBench)。
- [S18 DiscoveryBench 论文v1全文](https://arxiv.org/html/2407.01725v1)、[摘要](https://arxiv.org/abs/2407.01725)及[AllenAI官方README](https://github.com/allenai/discoverybench)。
- [S19 GIFT-Eval 官方README](https://github.com/SalesforceAIResearch/gift-eval/blob/main/README.md)与[论文摘要](https://arxiv.org/abs/2410.10393)，读取规模、97配置、split、zero-shot/泄漏定义与提交约束。
- [S20 Monash 官方项目页](https://forecastingdata.org/)，规模、频率变体、MASE/RMSSE与跨单位评价限制。
- [S21 Chronos 官方README](https://github.com/amazon-science/chronos-forecasting/blob/main/README.md)，模型家族与Chronos-2协变量支持。
