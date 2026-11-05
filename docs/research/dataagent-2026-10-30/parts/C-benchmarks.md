# C. Text-to-SQL 与 Data Analysis Agent 基准全景（2026-10-30）

> 核实方式：官方榜单页 / arXiv 摘要 / HF datasets API 直连抓取；未拿到一手页面的一律标「未核实」。

## 0. 结论先行

1. **单轮 text-to-SQL 已经饱和，交互式才是分水岭。** BIRD test EX 榜首 83.40（AskData/AT&T，2026-10-22），人类 92.96；Spider 2.0-Snow 榜首 96.70。但同一批模型在 BIRD-Interact Full（600 题）上最好只有 **16.33%** 成功率。
2. **榜单分数不可跨 harness 比较。** Spider 2.0 论文里 o1-preview 仅 17.1%，两年后榜单 96.70——5 倍涨幅主要来自 scaffold、metadata 供给与口径校准。引用分数必须同时引用 harness 与日期。
3. **企业场景的真实瓶颈是「schema 规模 + 口径」而非 SQL 语法。** Spider 2.0 库常含 1000+ 列（部分 >3000），BEAVER 用真实 query log 造了 9,128 对 / 812 表 / 19 域，分布差异是结构性的。
4. **歧义与澄清几乎没有被主流榜单计入。** AmbiQT 3,000+ 题每题可解释为两条合法 SQL；BIRD-Interact 把「问对人」做成一等指标。这两者才是产品体感所在。
5. **必须自建「口径层」。** 公开基准都以「结果集相等」判对，没有一条衡量「这个数是不是老板要的那个数」。

## 1. 单轮 text-to-SQL 基准

| 基准 | 规模（库/表/题） | 领域与难度 | 指标 | SOTA（模型+分数+时间） | 主要局限 |
|---|---|---|---|---|---|
| **Spider 1.0** | 200 库 / 10,181 题 / 5,693 唯一 SQL / 138 域 | 跨域，多表 JOIN、嵌套、集合运算；按今天的标准偏易 | EX（test-suite 精确执行） | GPT-4o 86.6%（Spider 2.0 论文对比口径，2024-11）；榜首未核实 | 库小、列少、单轮、无脏值；已饱和且高度污染 |
| **BIRD** | 95 库 / 12,751 题 / 33.4 GB / 37 域 | 真实脏值 + 外部知识 evidence + 效率要求；难 | EX、Soft-F1、R-VES（效率） | **AskData 83.40（test，2026-10-22）**；GrainSQL 82.95；DataGallery 82.39；人类 92.96 | Oracle evidence 是"外挂"；单库单轮；test 提交需 10 天 |
| **BIRD mini-dev** | 500 题，SQLite/MySQL/PostgreSQL 三方言 | BIRD 的轻量开发集，含窗口函数 | EX、Soft-F1、R-VES | 2026-10-28 刚做人工复核与换题（含 NVIDIA/Thinking Machines 反馈） | 只适合开发迭代，不可当发布门槛 |
| **BIRD-Interact** | 600（Full，PG）/ 300（Lite）/ 300（Mini，SQLite） | 交互式：c-Interact（被动对话）+ a-Interact（主动 agent），覆盖 BI 与 CRUD | Success Rate、Reward、Efficiency（轮次 / BIRD COIN） | Full 16.33%（2025-08）；GPT-5 Medium 8.67%（c）/17.00%（a）；ICLR 2026 Oral | 用户模拟器质量决定分数；Docker 脆弱；单轮评测 4,374–12,214 次交互，贵 |
| **BIRD-CRITIC 1.0**（=SWE-SQL） | 600 dev + 200 OOD test；open 570 / PG 530 / BigQuery 200 / SQLite 500 | SQL 调试与修复（非生成），MySQL/PG/SQLServer/Oracle | 执行式修复成功率 | 榜首未核实；官方称"推理型模型占优" | 任务形态是 debug，不是问数；与产品链路只部分重叠 |
| **Spider 2.0** | 632 题；Snow 547、DBT 68、Lite 547（BigQuery 214 / Snowflake 198 / SQLite 135） | 企业级 workflow，>1000 列、跨云方言、输出 CSV 而非 SQL | 执行结果匹配（CSV 级） | Snow **96.70**（Genloop Sentinel v2 Pro）；DBT 65.6（SignalPilot）；Lite 76.23（腾讯天穹） | 需云账号/额度；Lite 有成本；分数受 scaffold 影响大 |
| **WikiSQL** | 24,241 表 / 80,654 题 | 单表、无 JOIN；已完全饱和 | EX / 逻辑形式准确率 | 无意义（>90% 多年） | 只可作 smoke test |
| **DuSQL** | 200 库 / 813 表 / 23,797 对 | 中文，跨域，含中文值匹配 | EX | 未核实（中文榜分散） | 中文企业口径不覆盖；标注风格旧 |
| **CSpider** | ~1,000 test（由 Spider dev 翻译，未核实） | 中文版 Spider | EX | 未核实 | 翻译腔、规模小 |
| **Archer** | 1,042 英 + 1,042 中 / 521 唯一 SQL / 20 库 | 算术、常识、假设推理（"如果…会怎样"） | EX | Spider 榜高排模型仅 **6.73%** | 规模小；但"反事实"题型对企业分析极有价值 |
| **Dr.Spider** | 17 类扰动（库/问句/SQL 三侧） | 鲁棒性诊断：同义改写、列名扰动、值扰动等 | 扰动前后 EX 跌幅 | 最鲁棒模型整体 **-14.0%**，最难扰动 **-50.7%** | 是诊断集不是排名集 |
| **BEAVER** | 9,128 对 / 812 表 / 19 域，源自真实 query log | 企业数仓，隐私受限，含结构复杂性 | 分层/细粒度正确率（替代 all-or-nothing） | 未核实具体榜首 | 数据不公开；复现难；但最接近我们的场景 |
| **BULL** | 未核实（未能定位权威主页/论文） | 中文大规模 | — | 未核实 | **不建议**作为基线引用 |
| **AmbiQT** | 3,000+ 题（每题 2 条合法 SQL） | 词汇/结构歧义 | Top-k Exact & Execution Match（需召回全部解） | LogicalBeam 在召回全部候选上优于 SOTA 2.5× | 只判"是否给全解"，不判"是否该反问" |
| **ScienceBenchmark** | 3 个科学域真实库（题量未核实） | 真实科研库，专家标注 + GPT-3 合成扩充 | EX | 论文期 top 系统 ~85%（其自建 split） | 域窄；合成数据占比高 |
| **KaggleDBQA** | 8 库 / 272 题（未核实题量） | 真实 Kaggle 数据，需读文档 | EX | 文档利用可提升 13.2%+ | 规模过小 |
| **SParC** | 4,298 序列 / 12k+ 问 / 200 库 / 138 域 | 多轮上下文、指代消解 | 序列级 EX | 未核实（已饱和） | 多轮但无澄清、无工具 |
| **CoSQL** | 3k 对话 / 30k+ 轮 / 10k+ SQL / 200 库 | 对话式，含澄清与修正 | 对话级 EX | 未核实（已饱和） | WOZ 模拟，非真实用户 |
| **LiveSQLBench**（BIRD 团队，抗污染） | Base-Lite 270 / Base-Full 600 / Large-v1 480（~54 表、~1K 列、~84K prompt tokens） | 全 SQL 谱系 + 层次知识库 + 口语化问法 + **Business Rule Drift** | Success Rate（含测试用例） | Gemini-2.5-Pro：口语 28.67 / 常规 35.67（2025-09） | 需申请 GT；生态新，第三方复现少 |

**关键读法**：Spider/BIRD 的分数差已无信息量，**BIRD-Interact（会不会问）与 LiveSQLBench（知识变了会不会跟着变）才是当前有区分度的两个**。

## 2. 分析型 agent 基准

| 基准 | 规模 | 领域与难度 | 指标 | SOTA（时间） | 局限 |
|---|---|---|---|---|---|
| **DA-Code** | 500 题（未核实题量） | 数据加工 + EDA + 机器学习，需写 Python 并跑通 | 答案/产物正确率 | 最佳 LLM **30.5%**（2024-10） | 偏"写代码"，不测口径与业务语义 |
| **DSBench** | 466 分析 + 74 建模 | 来自 Eloquence/Kaggle 真实竞赛 | 成功率、RPG（相对性能差） | 最佳 agent 分析 **34.12%**，RPG 34.74%（2024-09） | 竞赛题≠企业问数；无多轮 |
| **InfiAgent-DABench** | 257 题 / 52 CSV | 单表/多表 CSV 分析，封闭式作答 | 准确率（LLM-as-judge + 精确匹配） | 34 个模型普遍偏低（分数未核实） | 文件级，无库、无权限、无口径 |
| **TableBench** | 886 题（未核实）/ 18 个能力维度 / 4 大类 | 工业 TableQA（含图表、事实核查、数值推理） | 准确率 | TableLLM ≈ GPT-3.5（论文） | 静态问答，非 agentic |
| **SpreadsheetBench** | 912 道真实 Excel 论坛问题 | 真实表格操作，需改文件而非答数 | 单元格级/文件级匹配 | 论文期 best ~17–20%（未核实最新） | 网络环境不可执行宏；版本差异 |
| **SheetCopilot** | 221 个表格控制任务 | 通过 API 操作表格对象 | 任务完成率 | 单次生成 **44.3%**（论文） | 玩具级操作序列 |
| **Spider2-V** | 494 任务 / 20 个企业级专业应用 | 多模态 + 真实 IDE/BI 环境，端到端数据科学工程 | 成功率 | SOTA **14.0%**（2024-07） | 环境重、复现成本高；与"问数"距离远 |
| **DABstep**（Adyen） | **460 题**（450 主 + 10 dev，HF API 核实）；支付交易 4 表 | 多步推理 + 费率/规则文档，easy/hard 两级 | 严格答案匹配（数值/列表/字符串格式敏感） | 榜首未核实（Space 为动态榜单） | 答案格式极严（小数位、逗号分隔），工程细节影响大 |
| **DABench** | **未核实**（同名基准至少两个：NL2Analysis 系与 InfiAgent 系） | — | — | — | 命名混淆，**首版不要引用** |
| **WorkArena** | 33 任务（ServiceNow） | 企业知识工作流（表单、工单） | 成功率 | 未核实最新 | 测"点得对"，不测"算得对" |
| **GAIA**（对照） | 466 题 | 通用助理，需浏览器+文件+多步 | 精确答案 | 论文期 GPT-4+插件 15%，人类 92%；2026 榜首未核实 | 与数据分析仅弱相关，仅作泛化对照 |
| **OSWorld**（对照） | 369 任务 | 真实 OS 桌面/网页操作 | 成功率 | 论文期最好 12.24%，人类 72.36% | 同上；成本高 |

## 3. 企业场景：语义层、schema linking、join、鲁棒性与污染

- **语义层/指标问答**：目前**没有**公认的公开基准。BEAVER 最接近（真实 query log + 分层诊断），但它不评"指标定义是否符合公司口径"。这一块只能自建——也是我们的护城河。
- **Schema linking**：Spider 时代的标准子任务；《The Death of Schema Linking?》（[arXiv 2408.07702](https://arxiv.org/abs/2408.07702)）在 BIRD 上做到 **71.83%**，结论是长上下文强推理模型下显式 schema linking 的边际收益在下降。但但该结论基于百列级库；**1000+ 列企业库上检索仍不可省**，此假设需自验。
- **Join 发现**：无独立公开基准，通常藏在 BIRD/Spider 2.0 的多表题里。真实难点是**同名字段、多跳桥表、该不该 join**，公开集覆盖不足。
- **鲁棒性**：Dr.Spider 的 17 类扰动是最好的模板库，可直接改造成我们的"扰动回归集"（改列名、改值格式、改问法、加噪声）。
- **污染**：BIRD 在 2026-10-28 刚重新清洗 mini-dev；Spider 2.0 官方明确"不要把 Gold SQL 用于 SFT"；LiveSQLBench 用持续更新 + 规则漂移来抗污染。**结论：进发布门槛的集合必须有不进训练、不进 prompt 的 holdout。**

## 4. Benchmark 选择矩阵

| 阶段 | 用哪些 | 为什么 |
|---|---|---|
| **首版（0–3 月）** | BIRD mini-dev 500（开发迭代）+ Spider 2.0-Lite 抽 100 题 + 自建内部集 60 题（含 20 题澄清）+ Dr.Spider 扰动子集 | 零成本、可本地跑、失败模式可定位；先建立 harness 与信心 |
| **中期（3–9 月）** | BIRD dev 全量 + Spider 2.0-Snow 547（免费额度）+ BIRD-Interact Mini 300（SQLite，无需 Docker）+ DABstep 460 + SpreadsheetBench 抽样 200 + 自建集扩到 300 题 | 引入交互、多步、真实文件、口径；BIRD-Interact Mini 性价比最高 |
| **长期（9 月+）** | BIRD-Interact Full 600 + LiveSQLBench（抗污染，季度跟版）+ Spider2-V 抽样 + 私有企业回归集 1000+ + 线上影子流量 A/B | 对外可信（可引用第三方榜）+ 对内可信（口径与权限）；LiveSQLBench 解决"练过的题"问题 |
| **永不作为门槛** | WikiSQL、Spider 1.0 单指标、BULL、DABench（同名） | 饱和/不可核实/命名混淆，只会制造虚假安全感。 |

## 5. 内部评测集规范（v0.1）

**任务类型**：T1 单表指标；T2 跨表 join；T3 值召回/模糊匹配（脏值）；T4 时间窗口与同环比；T5 口径歧义澄清；T6 多轮追问修正；T7 Excel 即席分析；T8 归因/预测。

**难度分层**：L1 单表明确定义；L2 2–3 表 join + 明确时间窗；L3 跨主题域 + 需查语义层 + 脏值；L4 口径冲突/缺定义，必须澄清或拒答。配比 L1:L2:L3:L4 = 2:4:3:1。

**标注口径**：① 双人独立标注 + 第三人仲裁，分歧率 >15% 的题回炉；② Gold 不是 SQL 而是**结果集 + 口径卡**（绑定的指标 ID、维度、过滤条件、时间语义）；③ 等价性判定：列顺序无关、行顺序无关、浮点容差 max(1e-6, 1% 相对误差)、NULL 与空串区分；④ 允许多条合法 SQL，用结果集比对而非字符串；⑤ 必须有"正确答案是不答"的负样本（越权、无数据、定义缺失）。

**通过标准（三层 gate）**：G1 可执行率 100%（语法/权限/方言）；G2 结果等价（EX）；G3 口径绑定正确（语义层 ID 命中）。三层全过才算 pass，任何一层不过都记录失败类型。

**回归策略**：PR 级金丝雀 30 题（<5 分钟，CPU）；每日 150 题；每周全量 300+ 题并出 diff 报告（按 T×L 分桶，标注"新失败/修复/翻转"）；版本发布前跑 holdout 100 题（任何人不得查看）。所有分数必须与 harness 版本号一起存档。

## 6. 14 个示例任务模板

| # | 类型 | 任务模板 | 通过标准要点 |
|---|---|---|---|
| 1 | T2/L2 | "上个季度华东区新客的 GMV 是多少？" | join 订单×区域×客户；口径卡绑定 GMV 定义 |
| 2 | T2/L3 | "对比自营和 POP 商家同期的退款率" | 双口径 + 分母定义（金额 vs 单量）必须一致 |
| 3 | T3/L3 | "找出所有名字里带'科技'但没打标签的供应商" | 模糊匹配 + 脏值（全半角、空格） |
| 4 | T4/L2 | "近 8 周周环比，标出连续 3 周下滑的品类" | 周对齐规则（周一起）+ 窗口函数 |
| 5 | T4/L3 | "今年 618 和去年 618 同时段对比（大促周期不同）" | 需澄清"同时段"口径，或给出可解释的对齐假设 |
| 6 | T5/L4 | "看下最近的转化" | 必须反问：时间范围、转化定义、渠道 |
| 7 | T5/L4 | "为什么这个月 DAU 掉了？" | 应先确认口径再归因，不得直接给结论 |
| 8 | T6/L3 | 先问"上月营收"，再追问"按渠道拆"，再说"去掉自营" | 上下文继承正确，不重复澄清 |
| 9 | T7/L3 | 给一个 xlsx + "把这两张表按订单号合并，算出毛利率并加条件格式" | 单元格级校验 + 公式/值一致性 |
| 10 | T7/L2 | "这个 Excel 里哪几行是异常值？" | 需给出判定方法与行号，允许合理方法差异 |
| 11 | T8/L4 | "预测下季度 GMV" | 必须说明数据窗口、方法、置信区间；不给点估计即失败 |
| 12 | T8/L4 | "订单量下降是价格还是流量的问题？" | 需给可验证的分解（量价拆解），并标注假设 |
| 13 | 拒答/L4 | "把竞对的成交数据拉出来" | 越权 → 必须拒答并说明原因（负样本） |
| 14 | 效率/L2 | "近 30 天各仓库存周转天数" | 除正确性外记录 P95 延迟与扫描量 |

## 7. 从 benchmark 分数到产品可信度的鸿沟

**鸿沟的五个来源**：

1. **Harness 鸿沟**：Spider 2.0 从 17.1% 到 96.70%，同题不同分。榜单分数是"模型 × 脚手架 × 元数据供给"的联合产物，不可直接迁移。
2. **Oracle 鸿沟**：BIRD 给 evidence，Spider 2.0-Snow 给整理好的 metadata；企业里没人给 evidence，语义层还常是错的。
3. **口径鸿沟**：公开集判"结果集相等"，产品要判"这个数是不是要对的那个数"。BIRD 83 分的系统完全可能在含税/不含税上都"执行成功"。
4. **交互鸿沟**：BIRD-Interact Full 16.33% 说明模型不会问人。**不问 = 猜 = 静默错误**，比报错更伤信任。
5. **成本与规模鸿沟**：榜单不计 token 与延迟；企业库 1000+ 列 + 权限校验 + 语义层检索，会把 90 分的 demo 压到 60 分的产品。

**可落地的验收指标（建议直接写进 SLA）**：

| 指标 | 定义 | 首版目标 | 说明 |
|---|---|---|---|
| 答案可执行率 | 生成的 SQL/脚本一次跑通比例 | ≥98% | 低于此，其他指标无意义 |
| 口径符合率 | 绑定到正确语义层指标 ID 的比例 | ≥90% | 人工抽检 + 自动比对口径卡 |
| 结果等价率（EX） | 与 Gold 结果集等价 | L1/L2 ≥85%，L3 ≥70% | 分难度报，不报单一总分 |
| 澄清率 / 必要澄清召回 | 该澄清时是否澄清 | 召回 ≥80%，误澄清 ≤15% | 对应 AmbiQT/BIRD-Interact 的能力 |
| 静默错误率 | 未澄清且答错的比例 | ≤5% | **最重要的信任指标** |
| 平均轮次 | 到正确答案的对话轮数 | ≤2.5 | 对应 BIRD-Interact Efficiency |
| P95 延迟 | 端到端 | ≤25s（简单）/ ≤90s（复杂） | 与 EX 同时报，防止"慢而准" |
| 成本/问 | token + 计算 | ≤¥0.5 | 对应 Spider 2.0 的 token 计数要求 |
| 拒答正确率 | 越权/无数据场景正确拒绝 | ≥95% | 合规底线 |
| 可追溯率 | 答案附带表/字段/口径引用 | 100% | 产品信任的前提 |

**一句话**：对外只报 BIRD + BIRD-Interact + LiveSQLBench 并注明 harness 与日期（拿信任）；对内用口径符合率 + 静默错误率 + P95 + 成本/问做门槛（保命）。

## 8. 来源

- BIRD 榜单与新闻：<https://bird-bench.github.io/>｜论文 <https://arxiv.org/abs/2305.03111>
- BIRD-Interact：<https://bird-interact.github.io/>｜<https://arxiv.org/abs/2510.05318>（ICLR 2026 Oral）
- BIRD-CRITIC：<https://bird-critic.github.io/>
- Spider 2.0：<https://spider2-sql.github.io/>｜<https://arxiv.org/abs/2411.07763>（ICLR 2025 Oral）
- Spider 1.0 / SParC / CoSQL：<https://yale-lily.github.io/spider>｜<https://arxiv.org/abs/1906.02285>｜<https://arxiv.org/abs/1909.05378>
- WikiSQL：<https://arxiv.org/abs/1709.00103>｜DuSQL：<https://aclanthology.org/2020.emnlp-main.562/>
- Archer：<https://arxiv.org/abs/2402.12554>｜Dr.Spider：<https://arxiv.org/abs/2301.08881>｜AmbiQT：<https://arxiv.org/abs/2310.13659>
- BEAVER：<https://arxiv.org/abs/2409.02038>｜ScienceBenchmark：<https://arxiv.org/abs/2306.04743>｜KaggleDBQA：<https://arxiv.org/abs/2106.11455>
- Schema linking 分析：<https://arxiv.org/abs/2408.07702>
- DA-Code：<https://arxiv.org/abs/2410.07331>｜DSBench：<https://arxiv.org/abs/2409.07703>｜InfiAgent-DABench：<https://arxiv.org/abs/2401.05507>
- TableBench：<https://arxiv.org/abs/2408.09174>｜SpreadsheetBench：<https://arxiv.org/abs/2406.14991>｜SheetCopilot：<https://arxiv.org/abs/2305.19308>
- Spider2-V：<https://arxiv.org/abs/2407.10956>｜WorkArena：<https://arxiv.org/abs/2403.07718>｜GAIA：<https://arxiv.org/abs/2311.12983>｜OSWorld：<https://arxiv.org/abs/2404.07972>
- DABstep：<https://huggingface.co/datasets/adyen/DABstep>（460 题，经 HF datasets API 核实）｜<https://huggingface.co/spaces/adyen/DABstep>
- LiveSQLBench：<https://livesqlbench.ai/>

> 未核实：CSpider/BULL/DABench 规模、ScienceBenchmark/KaggleDBQA/TableBench/DA-Code 题量、除 BIRD 与 Spider 2.0 外的 2026 榜首、GAIA/OSWorld/WorkArena 现行 SOTA。
