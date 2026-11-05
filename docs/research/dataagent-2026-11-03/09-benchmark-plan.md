---
version: v0.2
date: 2026-11-04
status: 草案；任务目录见 09-benchmark/
basis: 总 Catalog 141 组 / 458 原子
---

# 能力效果监控与 Benchmark

## 1. 选取规则

| 纳入 | 不纳入 |
|-|-|
| 产出质量随真实输入分布或模型而变化的“软”能力组 | 结果确定的硬能力：执行引擎 DA07.1–07.6、版本管理 DA12.2、轨迹写入 DA04.1；以单元测试与性质测试覆盖 |
| 效果取决于真实文档与表格分布的硬能力：文件解析 DA01.4、OCR DA01.5 | — |

## 2. 核心模块

| # | 核心模块 | 原子组合（切片） | 单测覆盖不到 | 参考 benchmark | 监控指标 |
|-|-|-|-|-|-|
| 1 | 不规则表格理解 | DA01.4.2、01.4.6；DA02.1、02.2、02.4（S0） | 多行表头、合并单元格、合计行的识别依赖真实表格分布 | RealHiTBench；MiMoTable | 表头单元格正确率；行保留率（静默丢行为 0）；下游问答准确率 |
| 2 | 文档解析与 OCR | DA01.4.5；DA01.5；DA02.8（S0） | 扫描件、盖章件、复杂版面 | OmniDocBench（已接近饱和）；olmOCR-Bench | 文本 NED；表格 TEDS；阅读顺序；断言通过率 |
| 3 | 字段抽取与锚点 | DA02.12.1、12.3、12.4（S0） | 编造值、遗漏重复记录、证据位置错误 | ExtractBench；VRDU；DocILE | 值 F1；记录完整率；证据定位 F1（词级、页级）；编造率（应为 null 却给值） |
| 4 | 制度 → 规则 → 可判定性与适用范围 | DA02.8 条款切分；DA03.4.3；DA03.15；DA03.16（S0） | 规则选错、条件方向写反、`unknown` 被当作确定结论 | RuleArena；DeonticBench（待核） | 规则选择与应用准确率；条件方向一致率；可判定性三分类准确率；`unknown` 保持率 |
| 5 | 指标定义与语义查询编译 | DA03.4.1；DA06.1–06.3、06.8；DA07.5（S0 / 按需） | 同一问题多次口径不一；企业级 schema 复杂 | BEAVER；Spider 2.0；BIRD；data.world CWD；dbt-llm-sl-bench | 执行准确率；口径一致率（同一问题重复问结果相同）；无法表达时拒答率 |
| 6 | 召回检索与检索充分性 | DA05.1、05.2、05.4、05.6、05.9（按需） | 漏召回无法归因；停止时机 | BRIGHT；TARGET | Recall@k；nDCG@10；停止时漏召回率；多余检索步数 |
| 7 | 端到端多步数据分析 | DA06.4、06.5；DA07.1、07.2；DA08.1–08.6（按需） | 跨文件综合、读业务手册、中间结果 | DABstep；KramaBench | 精确匹配准确率（难题子集单列）；pass^k；步数与成本 |
| 8 | 预测与优化 | DA09.1–09.4（按需） | 预测需结合文本上下文；求解结果区分最优、可行、未知 | Context is Key；NL4Opt、IndustryOR、OptiBench、OptMATH（用清洗版） | CRPS / SMAPE；求解代码执行后目标值准确率；最优 / 可行 / 未知判定准确率 |
| 9 | 表格计算、图表与报告 | DA10.1–10.3（S0 / 按需） | 大型多 sheet 工作簿；目标单元格选错；图表可读性 | SpreadsheetBench 2；VisEval；nvBench 2.0 | 单元格级正确率；图表合法性与可读性；未修改区域保持率 |
| 10 | 持续监控与告警 | DA14.2、14.3、14.8（S2） | 误报与漏报只在真实时间序列上出现 | TSB-AD | VUS-PR；告警精度；检测延迟 |
| 11 | 动作执行与策略遵从 〔FDE〕 | DA06.6、06.7；DA07.7、07.8；DA15；DA16.2（S1） | 多轮交互中违反策略；该拒未拒；重复执行结果不一致 | τ²-bench（官方推荐 τ³）；CRMArena-Pro | pass^k；违规动作率；该拒未拒率；审批触发准确率 |
| 12 | 权限、敏感信息与外部数据安全 | DA12.1；DA16.1；读取外部数据的全部原子（S0） | 文件、表格中夹带的指令劫持 Agent；敏感数据外泄 | AgentDojo；CRMArena-Pro 保密子集 | 攻击成功率；防御下的任务完成度；敏感字段外泄率 |
| 13 | 记忆与经验召回 | DA04.3；DA05.3；DA12.3（按需） | 知识更新后仍用旧信息；时序推理 | LongMemEval（v2）；MemoryAgentBench | 准确率；过期知识误用率；拒答正确率 |
| 14 | 数据建模与物化 | DA13.1–13.3（按需） | 转换模型的列与真值不一致 | ELT-Bench（参考 Verified 版）；Spider 2.0 dbt 任务 | 加载成功率（SRDEL）；转换成功率（SRDT）；每条流水线成本 |
| 15 | FDE 交付效果 | DA18.5；DA11.6–11.8；DA16.5（S2） | 只能在真实客户环境测量 | — | 首个可信答案耗时；接入与变更工时；审批负担；影子运行一致率 |

## 3. 评测集与流程

| 项 | 规则 |
|-|-|
| 外部 benchmark | 横向标定能力上限；按版本记录分数与所用数据版本 |
| 自建金标集 | 每个模块一套，由脱敏真实样本构成；接入 DA11.4 回归评测 |
| 样本隔离 | 验收样本按 DA11.5 `unseen_acceptance` 隔离，记录暴露 |
| 对抗子集 | 第 3、4 项复用 Round 4 锚点反例矩阵与规则方向反转用例（[r4-review.md](06-data-layer-build/r4-review.md)）；第 12 项按 AgentDojo 方式把指令藏入单据与工作簿 |
| 自建优先 | 第 4 项（制度 → 判定）、第 5 项（认证 KPI 口径）外部参照最少，以自建集为主 |
| 度量汇总 | 结果进入 DA11.6 持续改进度量；S2 上线门禁（DA11.9）引用第 1–5 项指标 |

## 4. Benchmark 参考

| Benchmark | 对应模块 | 规模与判分 | 来源 |
|-|-|-|-|
| RealHiTBench | 1 | 708 张层级表、3,752 个问答，24 个领域；多数模型平均分低于 70 | [arXiv 2506.13405](https://arxiv.org/abs/2506.13405)；[GitHub](https://github.com/cspzyy/RealHiTBench) |
| MiMoTable | 1 | 428 个中英文表格、1,719 组问答；复杂表头、多 sheet、多文件；最佳 77.4% | [COLING 2025](https://aclanthology.org/2025.coling-main.173/) |
| OmniDocBench | 2 | v1.5 共 1,355 页；NED、TEDS；头部模型已超过 95 | [GitHub](https://github.com/shijinpjlab/OmniDocBench)；[饱和讨论](https://www.llamaindex.ai/blog/omnidocbench-is-saturated-what-s-next-for-ocr-benchmarks) |
| olmOCR-Bench | 2 | 单页 PDF，逐条事实断言、按通过比例计分 | [GitHub](https://github.com/allenai/olmocr/tree/main/olmocr/bench) |
| ExtractBench | 3 | 370 份企业文档、4,869 页、67 种文档类型；值 F1、证据定位 F1、成本 | [arXiv 2607.29677](https://arxiv.org/abs/2607.29677)；[GitHub](https://github.com/run-llama/ExtractBench) |
| VRDU | 3 | 两类表单；新模板泛化、嵌套重复字段 | [arXiv 2211.15421](https://arxiv.org/abs/2211.15421) |
| DocILE | 3 | 6,680 份标注的真实业务文档；关键信息定位与抽取、明细行识别 | ICDAR 2023（LNCS 14188） |
| RuleArena | 4 | 95 条真实规则、816 道题（航空行李、NBA、税务）；规则选择与应用指标 | [arXiv 2412.08972](https://arxiv.org/abs/2412.08972)；[ACL 2025](https://aclanthology.org/2025.acl-long.27/) |
| BEAVER | 5 | 私有数仓 812 张表、9,128 组问题–SQL，来自真实查询日志 | [arXiv 2409.02038](https://arxiv.org/abs/2409.02038)；[站点](https://beaverbench.github.io/) |
| data.world CWD | 5 | 保险领域企业 schema、43 个业务问题；加入知识图谱后准确率 16.7% → 54.2% | [arXiv 2311.07509](https://arxiv.org/abs/2311.07509)；[数据](https://github.com/datadotworld/cwd-benchmark-data) |
| dbt-llm-sl-bench | 5 | 11 个问题；语义层 98–100%、text-to-SQL 84–90%，不可表达的问题计 0 | [GitHub](https://github.com/dbt-labs/dbt-llm-sl-bench)；[dbt](https://www.getdbt.com/blog/semantic-layer-as-the-data-interface-for-llms) |
| BRIGHT | 6 | 1,398 个推理型检索查询；最佳 nDCG@10 低于 30 | [arXiv 2407.12883](https://arxiv.org/abs/2407.12883) |
| TARGET | 6 | 表检索，接 FeTaQA、TabFACT、OTT-QA、Spider、BIRD；Recall@k 与下游准确率 | [arXiv 2505.11545](https://arxiv.org/abs/2505.11545)；[站点](https://target-benchmark.github.io/) |
| DABstep | 7 | 约 450 题，来自 Adyen 支付业务，含业务手册；精确匹配，难题最佳低于 15% | [arXiv 2506.23719](https://arxiv.org/abs/2506.23719)；[数据](https://huggingface.co/datasets/adyen/dabstep) |
| KramaBench | 7 | 104 个任务、1,700 个文件、6 个领域；端到端最佳约 55% | [arXiv 2506.06541](https://arxiv.org/abs/2506.06541)；[站点](https://kramabench.org/) |
| Context is Key | 8 | 71 个预测任务、7 个领域，每题必须用到文本上下文 | [arXiv 2410.18959](https://arxiv.org/abs/2410.18959) |
| NL4Opt / IndustryOR / OptiBench / OptMATH | 8 | 执行求解代码后比对目标值；原数据有质量问题，用清洗版 | [综述 IJCAI 2025](https://www.ijcai.org/proceedings/2025/1192.pdf)；[OptiBench](https://arxiv.org/abs/2407.09887)；[OptiMind](https://arxiv.org/pdf/2509.22979) |
| SpreadsheetBench 2 | 9 | 321 个任务，平均 11.8 个 sheet；逐单元格比对，最佳 34.89% | [arXiv 2606.29955](https://arxiv.org/abs/2606.29955)；[GitHub](https://github.com/RUCKBReasoning/SpreadsheetBench-2) |
| VisEval | 9 | 2,524 个查询、146 个数据库；合法性、可读性多检查器 | [arXiv 2407.00981](https://arxiv.org/abs/2407.00981) |
| nvBench 2.0 | 9 | 7,878 个有歧义查询、24,076 个图表，一对多 | [arXiv 2503.12880](https://arxiv.org/abs/2503.12880)；[GitHub](https://github.com/HKUSTDial/nvBench-2.0) |
| TSB-AD | 10 | 单变量 350 条、多变量 180 条序列；主指标 VUS-PR | [NeurIPS 2024](https://proceedings.neurips.cc/paper_files/paper/2024/file/c3f3c690b7a99fba16d0efd35cb83b2c-Paper-Datasets_and_Benchmarks_Track.pdf)；[PyPI](https://pypi.org/project/TSB-AD/) |
| τ-bench / τ²-bench | 11 | 零售、航空、电信；数据库最终状态与断言判定，pass^k | [arXiv 2406.12045](https://arxiv.org/abs/2406.12045)；[τ²](https://github.com/sierra-research/tau2-bench) |
| CRMArena-Pro | 11、12 | 19 类 CRM 任务、4,280 个实例；单轮约 58%、多轮约 35%，保密意识接近 0 | [arXiv 2505.18878](https://arxiv.org/abs/2505.18878)；[数据](https://huggingface.co/datasets/Salesforce/CRMArenaPro) |
| AgentDojo | 12 | 97 个任务、629 个安全用例；安全与任务完成度同时计分 | [arXiv 2406.13352](https://arxiv.org/abs/2406.13352)；[GitHub](https://github.com/ethz-spylab/agentdojo) |
| LongMemEval（v2） | 13 | 信息抽取、多会话推理、知识更新、时序推理、拒答 | [arXiv 2605.12493](https://arxiv.org/abs/2605.12493) |
| MemoryAgentBench | 13 | 2,071 个问题；检索、测试时学习、长程理解、选择性遗忘 | [arXiv 2507.05257](https://arxiv.org/abs/2507.05257) |
| ELT-Bench | 14 | 100 条流水线、835 张源表、203 个数据模型；最佳 SRDEL 57%、SRDT 3.9% | [arXiv 2504.04808](https://arxiv.org/abs/2504.04808)；[Verified](https://arxiv.org/pdf/2603.29399) |

## 5. 任务目录

各模块的评测集、运行记录与趋势看板存放在 [09-benchmark/](09-benchmark/README.md)，按「任务 → 轮次 → 运行」三层组织：

| 层 | 位置 | 内容 |
|-|-|-|
| 任务 | `tasks/B01`–`B15` | 任务卡（原子、参考 benchmark、指标与门槛）、评测集账本 `dataset/manifest.json`、暴露台账、基线指针 |
| 轮次 | `rounds/<round-id>.json` | 一次迭代：15 个任务的槽位 + 环境版本 + 汇总裁定；正式轮 `r` 进趋势，探索轮 `x` 不进 |
| 运行 | `tasks/*/history/runs/<round-id>/` | `run.json`、`scorecard.json`、逐用例结果与产物 |

配套：`monitor/thresholds.json`（绝对 / 相对 / 稳定三层阈值与告警分级）、`monitor/trend.md`（生成物）、`tools/{check,new_round,report}.py`。隔离规则：`unseen_acceptance` 不参与调参，样本一经读取即记入 `exposure.jsonl` 并降级为 `regression`。
