# D. 学术前沿：agentic NL2SQL / 数据探查 / Ontology / 数据分析 Agent（2024–2026）

> 核实方式：逐篇拉取 arXiv abs 页与 API（`export.arxiv.org`），标题、首次提交日期、摘要中的分数均以原文为准。所有成绩都是**论文自报（self-reported）**，BIRD 有 dev/test 两套口径，混引会失真，下表已分别标注。检索不到原文的条目一律写「未核实」，不补分数。

## 1. Executive Summary

- **范式已从「一次生成」转为「上下文工程 + 测试时扩展」**。2023 年的 DIN-SQL/DAIL-SQL 靠 prompt 分解与样例选择把 Spider 推到 85–86%；2024 年后的 CHESS/CHASE-SQL/XiYan 把增益主要放在三处：schema 压缩、多候选生成、候选选择器。
- **BIRD 上的公开天花板约 81.67%（Agentar-Scale-SQL，test，2025-09）**，两年内从 55.9% 升到 81.67%，但增益几乎全部来自「更多采样 + 更好的选择」，而非单模型能力。
- **Spider 2.0 打回原形**：632 个企业级任务、单库常超 1000 列、BigQuery/Snowflake 方言，o1-preview 代码 agent 仅解 21.3%（同框架在 Spider 1.0 是 91.2%、BIRD 73.0%）。真实瓶颈是元数据检索、方言与长上下文，不是 SQL 语法。
- **schema/值召回是唯一被反复验证的「低成本高收益」模块**：CHESS 的 Schema Selector 带来约 +2% 且 token 降 5 倍；LinkAlign 用「库检索 → 项定位」两阶段在 Spider 2.0-Lite 拿到 33.09%（开源模型）。
- **探查/建模侧学术界仍薄弱**：FD/IND 发现仍是 Metanome（HyFD/BINDER）这类确定性算法；LLM 的增量价值在语义命名、描述生成与 join 语义判定（SemJoin、Uber-Join、HyperJoin），且必须带成本/精度保证才可上线。
- **数据分析 agent 的失败模式已被量化**：上下文技术（语义层/多 agent/压缩）不是普适增益，对「爱调查」的 agent 反而 −5pp（2026-10 的行为研究）。这直接否定「堆编排」的产品直觉。

## 2. 方法族谱表

| 方法（首发） | 核心机制 / pipeline | 成绩（自报） | 开源 |
|---|---|---|---|
| DIN-SQL（2023-04） | 四阶段分解：schema 链接 → 难度分类 → 分难度生成 → 自纠正 | Spider 85.3 EX；BIRD 55.9 | 未核实 |
| DAIL-SQL（2023-08） | 系统比较 question representation / example selection / organization，提出整合方案 | Spider 86.6 EX | 未核实 |
| MAC-SQL（2023-12） | decomposer + selector（切子库）+ refiner 三 agent，工具按需激活 | BIRD 59.59（GPT-4）；SQL-Llama 43.94 | 是 |
| CodeS（2024-02） | SQL 语料增量预训练 1B–15B + 双向数据增强，主打私有化 | Spider/BIRD 多项 SOTA（摘要未给 BIRD 主表数值，**具体分数未核实**） | 是（论文声明） |
| MCS-SQL（2024-05） | 多 prompt 探索 + 置信度过滤 + 多选式选择 | BIRD 65.5；Spider 89.6 | 未核实 |
| CHESS（2024-05） | IR（值/实体召回）→ Schema Selector → Candidate Generator（迭代修订）→ Unit Tester（NL 单测） | BIRD test 71.10；schema 压缩 +2%、token ÷5、LLM 调用 −83% | 是 |
| CHASE-SQL（2024-10） | 三生成器（分治 / 执行计划 CoT / 实例感知合成样例）+ 成对比较选择器 | BIRD test 73.0 / dev 73.01 | 未核实 |
| XiYan-SQL（2024-11） | M-Schema 半结构化 schema + 多生成器集成（SFT + NER 选例 ICL）+ refiner + 选择模型 | BIRD 75.63；Spider test 89.65 | 是 |
| OpenSearch-SQL（2025-02） | 预处理/抽取/生成/精修 + Alignment 模块 + SQL-Like 中间语言 + 动态 few-shot | BIRD dev 69.3 / test 72.28 | 未核实 |
| Alpha-SQL（2025-02） | 零样本 MCTS：LLM 作 action model，自监督 reward 指导搜索 | BIRD dev 69.7（32B，无微调） | 未核实 |
| ReFoRCE（2025-02） | 表分组压缩 + LLM schema linking + 自修订 + 多数票共识 + 列探索（执行反馈） | Spider 2.0-Snow 35.83 / Lite 36.56 | 未核实 |
| LinkAlign（2025-03） | 多轮语义检索选库 + 无关信息隔离 + schema 抽取增强；Agent/Pipeline 双模 | Spider 2.0-Lite 33.09（纯开源 LLM） | 是 |
| Agentar-Scale-SQL（2025-09） | 三类测试时扩展：RL 内在推理 + 迭代精修 + 多样合成与锦标赛选择 | BIRD test 81.67（当时榜首） | 未核实 |
| DeepEye-SQL（2025-10） | 把 NL2SQL 当软件工程：关系闭包链接 + N-version 生成 + 「语法-逻辑-质量」工具链 + 置信度裁决 | BIRD dev 73.5 / test 75.07；Spider 89.8（30B MoE 免微调） | 未核实 |
| Tool-SQL | **未核实**：arXiv 检索不到同名论文，疑为 tool-augmented 一类（工具调用/外部执行器）的口头称呼 | — | — |

> 开源列只标注本环境可直接核实到仓库/论文声明的项；标「未核实」不等于闭源（多为未逐一访问）。

> 未列入上表但重要的：BIRD-Interact / LiveSQLBench（交互式、活库评测，2025–2026 由 BIRD 团队维护）、DSABench（2026-10，多库路由+执行）。

## 3. 三个子问题的 SOTA 与取舍

### 3.1 Schema / 值召回

有效顺序是**「先缩库，再缩表，最后才匹配值」**：

1. **库/表级检索**：把库、表做成带业务描述的卡片，用 embedding + BM25 混合召回；LinkAlign 证明单库内做 schema linking 不够，多库场景必须先做 database retrieval，否则后段全错。
2. **列级链接**：LLM 直接读全 schema 在 1000 列以上必崩。CHESS 的 Schema Selector、ReFoRCE 的 pattern-based table grouping 都是先把列数压到几十再让模型选。M-Schema（XiYan）用半结构化文本（类型、主外键、样例值、描述）替代裸 DDL，是目前性价比最高的表示法。
3. **值级召回**：痛点不是「找不到」，而是「值与问题里的表述不同形」（缩写、脏值、同义词）。工程上成熟的是 **embedding + BM25 混合 + LSH/倒排做候选剪枝，再对 top-k 列做 cell matching**；CHESS 的 IR 与 BIRD 系方法的 value retrieval 都是这个套路。领域同义词表（生物、医疗）仍建议人工维护一小份高置信映射，比让 LLM 每次现推稳定。
4. **裁剪 vs 召回的取舍**：召回不足（漏掉一列）几乎必错，召回过量只是加 token。因此阈值应偏松，用「候选集 + 二次判定」而不是「一次硬过滤」。

### 3.2 探查与 Ontology 构造

- **确定性画像仍是底座**：类型、基数、空值率、分位、Top-K、唯一性用 SQL 直接算；FD/IND/UCC 发现用 Metanome（含 HyFD、BINDER 等算法），可复现、可解释。LLM 不适合替代这一步。
- **LLM 的增量在语义层**：列/表命名与描述生成、业务指标口径、join 语义判定。join 侧 2026 年出现明显工程化转向：SemJoin（2026-06）用 advisor 在「聚类剪枝」和「分类器」两种策略间路由，比 adaptive block join 高 20–33 F1，且 3 个数据集中 2 个 token 更少；Uber-Join（2026-10）把 join 放进预算约束的多臂老虎机，用抽样验证给出**精度保证**——这说明「LLM 全量 pair 比较」在成本上不可行。
- **表发现/数据湖侧**：LakeBench（2023-07）提供数据发现基准，DeepJoin（2022-12）用预训练语言模型做可连接表发现，HyperJoin（2026-01）用 LLM 增强超图链接预测。这一支的代码/数据集相对齐全，可直接借鉴评测方法。
- **知识图谱/RDF 映射**：OBDA（Ontop）+ R2RML 是成熟标准路径，适合「虚拟化查询已有库」而不是「物化一张图」。LLM 自动生成 R2RML 的可靠性仍不足，建议「LLM 起草 + 人工审阅 + 版本化」，与我们 L3 mapping 层一致。
- **命名与描述生成**：应把 LLM 输出当作**待审提案**而非事实，保留证据字段（哪张表、哪些样例值、置信度）。

### 3.3 数据分析执行

- **planner/executor/verifier 分工已收敛**：Data Interpreter（2024-02）用层次图分解 + 可编程节点生成，在 InfiAgent-DABench 上把 75.9% 提到 94.9%；CodeAct（2024-02）证明「动作=可执行 Python」比 JSON 工具调用成功率高至多 20%；DeepAnalyze（2025-10）用课程式 agentic 训练，8B 模型超过多数闭源 workflow agent。
- **长任务的中间产物必须外置**：StateGuard（2026-09）把约束、版本化变量、中间结论存成 state graph，做有效性校验与干预，显著降低「陈旧中间结果被静默继承」导致的错误传播。这比把历史塞进 context 更可靠。
- **澄清（ambiguity）是独立能力**：DSABench（2026-10）显示多库任务 Route+Exec 成功率仅 6.69–7.98%，给一次澄清后升到 11.44–13.25%，最优 16.99%；在歧义任务上，澄清把「正确分支源召回」提高 39.8–43.2pp。PlanPool（2026-10）进一步指出失败根因是**过早终止澄清**，解法是把澄清计划外化成可变问题池，每个问题必须显式「问过或放弃」。

## 4. 五条「工程上真正有效」的结论

| # | 论文宣称 | 交叉验证后的判断 |
|---|---|---|
| 1 | schema 压缩能同时提精度、降成本（CHESS：+2%、token ÷5） | **成立且最值得先做**。这是纯工程收益，不依赖模型强弱。宣称的「+2%」是小幅，但 token 与延迟收益是一阶的。 |
| 2 | 多候选 + 选择器优于单次生成（CHASE-SQL 73.0、MCS-SQL 65.5、Agentar 81.67） | **成立但有成本墙**。分数提升与候选数近似对数关系，而成本线性增长；生产上应按难度路由，而不是全局开满。 |
| 3 | 执行反馈修复能显著纠错（ReFoRCE、Alpha-SQL、DeepEye 的预执行工具链） | **成立，但「执行通过≠语义正确」**。2026-10 的 Beyond Correctness 明确指出 agent 会用「碰巧对上答案的未验证假设」蒙混过关，必须配语义校验与假设披露。 |
| 4 | 多 agent 编排/语义层/记忆压缩普遍有益 | **被证伪为普适结论**。2026-10 的行为研究（1514 任务、7 个模型、5 个基准）发现 agent 分三类（调查型、抢答型、早停型），同一技术只对匹配的类型有效：编排对「调查型」反而 −5pp，语义层会让它们停止探查。 |
| 5 | Spider 2.0 分数低是模型不够强 | **不成立**。o1-preview 在 Spider 1.0 有 91.2%、BIRD 73.0%，到 Spider 2.0 只剩 21.3%；差距来自元数据搜索、跨方言、项目级上下文，属于**系统能力**问题。 |

补充一条成本侧的实测：CHESS 在达到 71.10% 时比同类方法少约 83% 的 LLM 调用——**「调用次数」应当作为与准确率并列的一等指标**，否则论文间的分数不可比。

## 5. 可落地到产品的 6 条设计建议

1. **三层上下文，永不投喂全 schema**：L0 画像（表/列摘要 + Top-K 值）→ 候选集（≤30 列，带样例值）→ 生成上下文（M-Schema 子集）。每层都可单独评测召回率，出问题能定位到层。
2. **建值索引而不是每次现查**：对每列采样 50–100 个值，建 embedding + BM25 混合索引，配 LSH 剪枝；cell matching 只对 top-k 列执行。索引随 L0 画像增量更新，可作为可丢弃缓存。
3. **探查流水线产品化，语义层当一等公民**：profiling（SQL 直算）→ IND/FD（Metanome 系）→ LLM 起草命名/描述/join 语义 → 人工确认 → 写 L1/L2 语义层并版本化。禁止每次问答让 LLM 重推业务口径。
4. **planner / executor / verifier 三段分离，中间产物落 state graph**：executor 只读账号 + 语句超时 + LIMIT + AST 校验；verifier 做「语法-逻辑-质量」三段检查，成本受限时用抽样执行。所有中间表、结论、假设写入可追溯的 artifact 存储（对齐 L5 memory）。
5. **澄清做成显式协议而非隐式行为**：维护 question pool，每个识别出的歧义必须「问」或「显式放弃并记录假设」；默认 1 轮、最多 2 轮，把「未澄清的假设」写进最终答案。这是当前投入产出比最高的一项体验改进（+4~7pp 成功率，歧义任务 +40pp）。
6. **按难度路由 + 预算化**：先跑单次 few-shot（便宜），置信度低或涉及多表/多库时升级到多候选 + 执行修复；把 LLM 调用数、token、P95 延迟写进 SLA 与回归测试，避免「离线分数涨、线上成本炸」。

安全侧三条硬约束：只读角色与行级过滤放到 L4 policy；单元格内容视为不可信输入（prompt injection 载体），拼接进 prompt 前做转义与来源标记；对外发布的结果附 SQL 与数据血缘。

## 6. 链接

- CHESS https://arxiv.org/abs/2405.16755 ｜ CHASE-SQL https://arxiv.org/abs/2410.01943 ｜ XiYan-SQL https://arxiv.org/abs/2411.08599 ｜ 代码 https://github.com/XGenerationLab/XiYan-SQL
- MCS-SQL https://arxiv.org/abs/2405.07467 ｜ DIN-SQL https://arxiv.org/abs/2304.11015 ｜ DAIL-SQL https://arxiv.org/abs/2308.15363 ｜ MAC-SQL https://arxiv.org/abs/2312.11242
- CodeS https://arxiv.org/abs/2402.16347 ｜ OpenSearch-SQL https://arxiv.org/abs/2502.14913 ｜ Alpha-SQL https://arxiv.org/abs/2502.17248
- ReFoRCE https://arxiv.org/abs/2502.00675 ｜ LinkAlign https://arxiv.org/abs/2503.18596 ｜ Agentar-Scale-SQL https://arxiv.org/abs/2509.24403 ｜ DeepEye-SQL https://arxiv.org/abs/2510.17586
- Spider 2.0 https://arxiv.org/abs/2411.07763 ｜ DSABench https://arxiv.org/abs/2610.14700 ｜ Beyond Correctness / PlanPool https://arxiv.org/abs/2610.02739
- Same Context, Different Agents https://arxiv.org/abs/2610.20959 ｜ StateGuard https://arxiv.org/abs/2609.34134
- SemJoin https://arxiv.org/abs/2606.29532 ｜ Uber-Join https://arxiv.org/abs/2610.25178 ｜ HyperJoin https://arxiv.org/abs/2601.01015 ｜ DeepJoin https://arxiv.org/abs/2212.07588 ｜ LakeBench https://arxiv.org/abs/2307.04217
- Metanome（HyFD/BINDER 所在框架） https://github.com/HPI-Information-Systems/Metanome ｜ R2RML https://www.w3.org/TR/r2rml/ ｜ Ontop https://ontop-vkg.org/
- Data Interpreter https://arxiv.org/abs/2402.18679 ｜ CodeAct https://arxiv.org/abs/2402.01030 ｜ DS-Agent https://arxiv.org/abs/2402.17453 ｜ DeepAnalyze https://arxiv.org/abs/2510.16872 ｜ YORO https://arxiv.org/abs/2409.12172
