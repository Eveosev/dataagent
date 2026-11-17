---
version: v0.3
date: 2026-11-18
status: 草案；目录与工具已落地，17 个任务已建，B16/B17 数据已构建
basis: 09-benchmark-plan.md §2（17 个已建任务）、§3（评测集与流程）、§4（参考 benchmark）
---

# Benchmark 任务目录

承载 [09-benchmark-plan.md](../09-benchmark-plan.md) 的 17 个已建任务（B01–B17），按「任务 → 轮次 → 运行」三层落盘，供多次迭代横向对比与门禁裁定。

## 1. 不变量

| 不变量 | 实现 | 违反后果 |
|-|-|-|
| 可比 | 每轮固定 `dataset.revision` + `env`（模型、内核、harness）；环境变了就是另一轮，不与旧轮直接算 Δ | 趋势图失去意义 |
| 可隔离 | `unseen_acceptance` 不参与调参；样本被读过即记入 `exposure.jsonl` 并降级为 `regression` | 指标虚高，无法验收 |
| 可追溯 | 每轮留 `run.json`、`scorecard.json`、`cases.jsonl`、产物；基线是显式指针而非「上一次」 | 无法归因、无法回滚 |

`check.py` 强制执行前两条的可机检部分；`regression` 与 `unseen_acceptance` 的隔离靠流程与台账，不是靠目录名。

## 2. 目录结构

```text
09-benchmark/
├── README.md                  # 本文件：目录契约
├── registry.json              # 17 个任务的唯一索引（状态、主指标、门槛层级、基线与最近轮次）
├── schema/                    # task / manifest / case / run / scorecard 的 JSON Schema
├── examples/                  # 用例与记分卡的填写样板，不参与统计
├── harness/
│   ├── README.md              # 适配器与评分器契约
│   ├── config.default.json    # 适配器、并发、超时、预算、环境版本
│   ├── adapters/              # 被测系统入口（CLI / MCP / HTTP）
│   └── graders/               # 指标实现，按 metric.grader 命名
├── tasks/
│   └── B01-irregular-table/   # 一个任务一个目录，B01–B17
│       ├── task.json          # 任务卡：原子、参考 benchmark、指标、门槛、隔离规则
│       ├── NOTES.md           # 迭代日志与决策（唯一手写的记录处）
│       ├── dataset/
│       │   ├── manifest.json  # 数据版本、来源与许可、split 计数、暴露台账指针
│       │   ├── exposure.jsonl # 暴露台账：哪条样本在哪个轮次被谁读过
│       │   ├── cases/         # 用例，按 split 分目录；金标与输入分离
│       │   │   ├── development/
│       │   │   ├── regression/
│       │   │   └── unseen_acceptance/
│       │   ├── fixtures/      # 脱敏样本本体；大文件走外部存储只留 digest
│       │   └── expected/      # 金标；与输入分离，只在判分时读
│       └── history/
│           ├── baseline.json  # 当前基线指针 + 指标快照
│           └── runs/<round-id>/
│               ├── run.json        # 环境、样本量、缺失、成本
│               ├── scorecard.json  # 分 split 指标、Δ、verdict、门禁结论
│               ├── cases.jsonl     # 逐用例结果（含失败原因）
│               └── artifacts/      # 输出、日志、轨迹、图表
├── rounds/<round-id>.json     # 一次迭代：17 个任务的 run 槽位 + 环境 + 汇总裁定
├── monitor/
│   ├── thresholds.json        # 绝对门槛 + 相对基线规则 + 告警分级
│   ├── trend.md               # 由 report.py 生成的趋势看板，勿手改
│   ├── scorecard-template.md  # 人工裁定用的记分卡说明
│   └── incidents/             # P0/P1 告警的归因记录
└── tools/
    ├── check.py               # 目录契约校验（stdlib，无依赖）
    ├── new_round.py           # 开一轮，生成 round 与 17 个 run 骨架
    └── report.py              # 汇总 rounds/ 与 scorecard 生成 monitor/trend.md
```

`task.json` 是声明，`manifest.json` 是数据账，`history/` 是结果账。三者不互相写入，避免「改了任务卡就把历史洗白」。

## 3. 命名

| 对象 | 规则 | 示例 |
|-|-|-|
| 任务 | `B` + 两位序号，与计划 §2 行号一致，稳定不复用 | `B07` |
| 任务目录 | `<id>-<slug>`，slug 建后不改（改 slug 等于换任务） | `B07-e2e-analysis` |
| 轮次 / 运行 | `rNNN-YYYY-MM-DD` 正式轮；`xNNN-YYYY-MM-DD` 探索轮。同一轮内 17 个任务的 run_id 相同，便于横向 join | `r003-2026-11-18` |
| 用例 | `<task>-<场景>-<序号>`，文件名与 `case_id` 一致 | `B03-invoice-0042` |
| 指标 | 小写下划线，与 grader 同名或一一对应 | `evidence_span_f1` |

探索轮（`x`）不进趋势对比、不建基线，只用于调参；正式轮（`r`）才允许更新 `baseline.json`。

## 4. 任务清单

| 任务 | 模块 | 原子数 | 参考 benchmark | 主指标 | 门槛层级 |
|-|-|-|-|-|-|
| B01 | 不规则表格理解 | 13 | RealHiTBench、MiMoTable | `header_cell_accuracy` | block |
| B02 | 文档解析与 OCR | 5 | OmniDocBench、olmOCR-Bench | `text_ned` | block |
| B03 | 字段抽取与锚点 | 3 | ExtractBench、VRDU、DocILE | `value_f1` | block |
| B04 | 制度 → 规则 → 可判定性 | 11 | RuleArena、DeonticBench（待核） | `rule_selection_accuracy` | block |
| B05 | 指标定义与语义查询编译 | 18 | BEAVER、Spider 2.0、CWD、dbt-llm-sl-bench | `execution_accuracy` | block |
| B06 | 召回检索与检索充分性 | 15 | BRIGHT、TARGET | `recall_at_k` | warn |
| B07 | 端到端多步数据分析 | 31 | DABstep、KramaBench | `exact_match_accuracy` | warn |
| B08 | 预测与优化 | 9 | Context is Key、NL4Opt / IndustryOR / OptiBench / OptMATH | `smape` | warn |
| B09 | 表格计算、图表与报告 | 9 | SpreadsheetBench 2、VisEval、nvBench 2.0 | `cell_accuracy` | warn |
| B10 | 持续监控与告警 | 9 | TSB-AD | `vus_pr` | warn |
| B11 | 动作执行与策略遵从〔FDE〕 | 21 | τ²-bench（τ³）、CRMArena-Pro | `pass_k_stability` | warn |
| B12 | 权限、敏感信息与外部数据安全 | 8 | AgentDojo、CRMArena-Pro 保密子集 | `attack_success_rate` | guard |
| B13 | 记忆与经验召回 | 11 | LongMemEval v2、MemoryAgentBench | `memory_accuracy` | warn |
| B14 | 数据建模与物化 | 7 | ELT-Bench（Verified）、Spider 2.0 dbt | `srdel` | warn |
| B15 | FDE 交付效果 | 15 | —（现场测量） | `time_to_first_trusted_answer` | field |
| B16 | 多源对齐与实体解析 | 6 | DeepMatcher / Magellan、Leipzig DBS（DBLP-ACM / Amazon-Google / Abt-Buy） | `entity_pair_f1` | warn |
| B17 | 字段映射 / schema matching | 5 | Valentine（NYU schema matching 子集） | `mapping_top1` | warn |

门槛层级：

| 层级 | 含义 | 当前任务 |
|-|-|-|
| `block` | 结果进 DA11.9 S2 上线门禁，任一主指标跌破绝对门槛或相对基线超限即阻断 | B01–B05（对应计划 §3「S2 门禁引用第 1–5 项」） |
| `guard` | 安全硬边界：泄漏类指标为绝对零容忍，其余按 `warn` 处理 | B12 |
| `warn` | 只告警与归因，不阻断发布 | B06–B11、B13、B14、B16、B17 |
| `field` | 不进 CI，按交付 cohort 季度汇总 | B15 |

原子数为 `catalog_atoms` 展开后的条数；同一原子可被多个任务引用（如 DA02.8 同时进 B02 与 B04），这是有意的重叠：前置解析质量会直接反映在下游任务上。

## 5. 一次迭代

```bash
cd docs/research/dataagent-2026-11-03/09-benchmark

# 1. 开轮（生成 rounds/<id>.json 与 17 个 run 骨架）
python3 tools/new_round.py --label model-swap --model <模型> --kernel agent-kernel@<sha>

# 2. 冻结数据版本；unseen_acceptance 本轮不得调参
# 3. 跑 harness（适配器见 harness/README.md），写 scorecard.json 与 cases.jsonl
# 4. 校验
python3 tools/check.py

# 5. 裁定：过门槛的轮次才写 history/baseline.json 与 registry.json 的 baseline_run
# 6. 刷新看板
python3 tools/report.py

# 7. 结论与决策写进对应任务的 NOTES.md；P0/P1 写 monitor/incidents/
```

第 5 步的裁定规则：

| 条件 | 动作 |
|-|-|
| `block` 任务全部 `pass`，`guard` 无告警，无 P0 | 可替代基线：写 `baseline.json`（含指标快照）与 `registry.json.baseline_run` |
| 任一 `block` 任务 `fail` | 不换基线；`decision=hold`；进 `incidents/` 归因 |
| 指标改善但成本或延迟超限 | 不换基线；按 P1 处理 |
| 样本量 < `defaults.min_samples_for_gate` | `verdict=unknown`，不得据此换基线，也不得报「通过」 |

基线只升不降：新轮次综合不如基线时不更新指针，避免用低水位替换高水位。

## 6. 监控

`monitor/thresholds.json` 三层阈值：

| 层 | 判据 | 例子 |
|-|-|-|
| 绝对 | 指标本身不能低于 / 高于某值 | B01 `row_retention` ≥ 1.0（静默丢行 0）；B12 `sensitive_leak_rate` = 0 |
| 相对 | 相对基线跌幅，按 pp 或比例 | 默认阻断 −5pp、告警 −2pp；`lower` 方向指标取反向 |
| 稳定 | 同一轮内重复跑的一致性 | `pass^k`（k=3）、口径一致率（同题重复 3 次） |

绝对门槛只在计划已给出明确要求处设置（当前 2 条），其余在首次 `r` 轮后按实测分布回填；`threshold_status=pending_baseline` 的指标不参与门禁，只记录。

告警分级见 `thresholds.json.escalation`：P0 阻断并回滚候选，P1 48 小时内归因，P2 只记录。趋势看板由 `report.py` 生成，每轮一行、每任务一行，含主指标最新值 / 基线与 Δ。

## 7. 隔离与防泄漏

| split | 用途 | 谁能读 | 是否进门禁 |
|-|-|-|-|
| `development` | 日常调试、构造 grader | 开发者 | 否 |
| `regression` | 回归与对比；已暴露样本的归宿 | 开发者、CI | 否 |
| `unseen_acceptance` | 验收与门禁 | 仅裁定人；CI 只拿聚合结果 | 是 |

规则：

- 任何样本被人工读过、被写进提示或 few-shot，即视为暴露：在 `exposure.jsonl` 追加一行（case_id、run_id、时间、原因），并在 manifest 里把它从 `unseen_acceptance` 移到 `regression`。
- `check.py` 会拒绝仍然留在 `unseen_acceptance` 却已在台账中的用例。
- 轮换：每 6 个正式轮或每季度（以先到为准），替换 `unseen_acceptance` 的 25%；替换时 `manifest.revision` 加次版本号，旧轮分数不重算但标注不可比。
- 修复者能看到的失败用例，自动降级为 `regression`，再用未暴露样本验收——这是 DA11.5 的既定要求。

## 8. 与 DA11 的对应

| 目录产物 | 对应原子 | 去向 |
|-|-|-|
| `scorecard.json` + `cases.jsonl` | DA11.4.1–4（检索、问数、回放、规则库回归） | 回归报告；`baseline` 即回归基线 |
| `unseen_acceptance` 上的分 split 指标 | DA11.5.5、11.5.6 | `AcceptanceReport.metrics`（`MetricBundle`） |
| 每轮趋势与成本 | DA11.6.1、11.6.2 | 持续改进度量；经验开关的对照即两轮 Δ |
| `block` 任务的门禁结论 | DA11.9.2 | 上线门禁判据之一 |
| `exposure.jsonl` 与 split 冻结记录 | DA11.5.6、DA11.4 的样本隔离 | 验收样本清单与暴露记录 |

字段对齐 `dataagent-contracts` 的 `QualityMetric` / `MetricBundle` / `AcceptanceReport`：`scorecard.split_scores.*.metrics` 的每项都是 value / numerator / denominator，可直接落 `QualityMetric`；缺样本写进 `samples.missing`，不静默从分母里剔除。

## 9. 数据存放

```text
workspace/benchmark-data/                  # 原始数据根（不入 docs，不入 git）
  <task>/<source-id>/                      # 一份来源一个目录
    FETCH.json                             # 抓取记录：locator/revision/digest/files/MB
    <原始文件…>
  fetch-report.json                        # 全量抓取汇总
  .pydeps/                                 # pyarrow/duckdb/pyyaml（转换器用）
docs/research/.../09-benchmark/
  datasets.lock.json                       # 数据源清单：id/task/kind/locator/license/status
  tools/fetch.py                           # 下载器：hf / git / url_zip
  tools/build_cases.py                     # 构建器：切分、落盘、回填 manifest
  tools/converters/<TASK>.py               # 每任务一个转换器
```

| 项 | 规则 |
|-|-|
| 三层归属 | 原始数据按 **任务 → 来源** 存放；`FETCH.json` 记录版本与摘要，可复核 |
| 引用方式 | 大文件不进 docs，用例写 `bench://<source-id>/<path-within-source>`；跑分时由 harness 解析回原始根 |
| 单文件大小 | ≤ 2 MB 的文本输入落 `dataset/fixtures/`（只写被选中的用例）；更大的走 `bench://` |
| 金标 | 与输入分离：`dataset/expected/<case_id>.json`，`case.expected.ref` 指向它，不内联进提示 |
| 校验和 | 每个 fixture 与来源目录记 sha256；`manifest.sources[].digest` 存数据集级 digest |
| 许可 | 外部 benchmark 记名称、版本、许可；客户样本必须脱敏并记来源与授权依据 |
| 不可变 | `manifest.status=frozen` 后不得改动；变更走 revision（`build_cases.py` 内容摘要不变时保持不变，内容变化才 +1，形如 `v0.N`） |
| 覆盖诚实 | 转换器在 manifest `build.coverage` 写明「已覆盖 / 部分覆盖 / 缺失」的指标；缺数据不得用假金标补 |

### 9.2 不可得来源与所需动作

| 来源 | 任务 | 原因 | 所需动作 |
|-|-|-|-|
| DocILE | B03 | 需在站点签署使用协议 | 已用 CORD-v2（票据）+ FUNSD（表单/bbox）替代，不再阻断 |
| Spider 2.0 全量 / dbt 任务 | B14 | 需按官网流程申请；**已决定延后** | 申请后补 `spider2-dbt` 源，B14 暂由 ELT-Bench 覆盖 |
| LongMemEval m 档 | B13 | 2.7 GB，暂不取 | 需要时补 `longmemeval_m`，用例已用 oracle + s_cleaned |
| B15 交付数据 | B15 | 无公开 benchmark，需真实客户台账与影子日志 | 见 `tasks/B15-fde-delivery/NOTES.md`「数据构建」 |
| DeepMatcher UW 镜像 / Magellan 数据 | B16 | 镜像未声明数据集许可；Magellan 当前仓库不再分发基准数据 | 已改用 Leipzig 原始发布；[发布页](https://dbs.uni-leipzig.de/research/projects/object_matching/benchmark_datasets_for_entity_resolution) 的 January 2019 声明链接到 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)，见 `tasks/B16-multi-source-alignment/NOTES.md`「许可核实」 |
| Valentine 原始论文数据集归档（surfdrive 分享） | B17 | 分享链接已 404；Wayback 快照只有 1 MB 截断 zip，不能作为可复核样本 | 改用 Valentine 官方仓库 v1.1.1 的 `experiments/data/`（10 对 NYC Open Data 表）；[LICENSE](https://github.com/delftdata/valentine/blob/v1.1.1/LICENSE) 为 Apache-2.0，见 `tasks/B17-schema-matching/NOTES.md`「许可核实」 |


**原则**：缺数据不编金标。抓不到或未授权时，`manifest.build.coverage` 与 `NOTES.md` 明确写缺口，`fetch-report.json` 记 `status/remedy`；任何「补齐」都必须可复核（`FETCH.json` 有 locator 与 digest）。

### 9.1 抓取与构建

```bash
# 1) 下载（跳过 gated 源并打印 remedy；已完成的源跳过）
python3 -I docs/research/dataagent-2026-11-03/09-benchmark/tools/fetch.py
python3 -I .../fetch.py --only mimotable,bright --force

# 2) 构建某一任务的用例
python3 -I docs/research/dataagent-2026-11-03/09-benchmark/tools/build_cases.py --task B04
python3 -I .../build_cases.py --task B04 --dry-run     # 只报数量，不落盘

# 3) 校验 + 刷新趋势
python3 -I docs/research/dataagent-2026-11-03/09-benchmark/tools/check.py
python3 -I docs/research/dataagent-2026-11-03/09-benchmark/tools/report.py
```

- 抓取器幂等：`FETCH.json` 标记 `ok` 的源默认跳过；`--force` 重抓。
- 构建器幂等：先清空本任务 `cases/`、`expected/`、`fixtures/`，再按固定哈希切分重写；同一份原始数据两次构建结果一致。`manifest.build.content_digest` 记录 cases、expected、fixtures 与来源目录实际数据文件内容（逐文件 sha256，排除 `FETCH.json`、`.git` 等抓取元数据）的摘要，摘要方案记在 `build.content_digest_version`；摘要不变时保持原 `revision` 和 `updated`，内容变化才升版本。
- `gated` 源（DocILE、BEAVER、Spider2 全量）需人工接受条款并配置 HF token，`fetch.py` 会跳过并在 `fetch-report.json` 里写 `remedy`；这类缺口要如实留在 manifest，不得用替身数据充数。

## 10. 维护

| 动作 | 规则 |
|-|-|
| 加任务 | 只有计划新增核心模块才加；编号顺延 B16 起，同步 registry、README §4、schema 的 pattern |
| 改指标 | 主指标一旦进入门禁不得替换，只能新增；旧指标转 `warn` 保留 3 轮 |
| 改门槛 | 只能收紧或在有归因记录的轮次后放宽；放宽必须写进 NOTES.md 并注明依据 |
| schema 变更 | `schema/` 加版本字段，`check.py` 先兼容再切换；历史 run 不回填 |
| 删任务 | 置 `status=deprecated` 并保留目录，不物理删除，否则趋势断档 |

## 11. 现状

| 项 | 状态 |
|-|-|
| 目录、schema、registry | 已建（17 任务 / 196 个原子引用） |
| 原始数据 | 已落 `workspace/benchmark-data/`，46 个来源（43 可取 / 0 gated / 1 延后 / 1 已替代 / 1 跳过）；版本与摘要见各源 `FETCH.json` |
| 规范化用例 | 16/17 任务已建，共 3603 条；所有 `fixtures/` 与 `bench://` 引用均已落地（`check.py` 校验） |
| registry/task 状态 | 已建任务 `status=collecting`；B15 保持 `planned`（无公开数据） |
| grader 实现 | 18 个已实现（覆盖 B01–B04、B16、B17），其中 15 个指标可真正判分（`unknown_retention` 只在 unknown 子集上计分）；其余 40 个未实现或金标缺口，见 `harness/graders/README.md` |
| 判分链路 | `harness/grade.py` 可跑通：金标回填得满分（B03/B16/B17）；B03/B16 扰动 20% 后掉分；scorecard 通过 schema 校验 |
| B16 判分自检 | oracle 三切分 F1=1、FMR=0；empty 三切分 F1=0；手工金标回填 F1=1、FMR=0；聚类 `[[L,R1],[R1,R2]]` 经传递闭包得 F1=1、FMR=0；`[[L,R1,OUTSIDE]]` 把 OUTSIDE 计 FP，得 F1=2/3、FMR=0.5；FMR `1/1`+`3/4` 按预测对 pooled=0.8；全程无合并时 value=null、denominator=0；零匹配场景未覆盖（240 条均至少一个真匹配），见 B16 NOTES「覆盖与缺口」 |
| B17 判分自检 | oracle 三切分 `mapping_top1`=1、`no_match_accuracy`=1；empty 三切分均为 0；146 条 = 77 个有目标字段 + 69 个无对应字段，三个 split 都同时含两类；显式 `null`/空数组才算无匹配作答，省略作答按错计；列名大小写/空格/下划线归一；单测 12 条，见 B17 NOTES 验证记录 |
| 适配器 | `dataagent-cli` / `oracle` / `empty` 三个，见 `harness/adapters/README.md`；`harness/run.py` 一键产出 run.json + cases.jsonl + scorecard。B16/B17 的 oracle 分支已补，B16 三切分 F1=1、FMR=0，B17 三切分 `mapping_top1`=1 |
| 已跑通的探索轮 | B02 `x001`（oracle，满分）、B02 `x002`（empty，地板）、B02 `x003`（CLI 缺失，如实 failed）、B03/B04 `x001`（oracle）、B16 `x544`（oracle，三切分 F1=1、FMR=0）、B16 `x045`（empty，三切分 F1=0）、B17 `x315`（oracle，三切分 `mapping_top1`=1、`no_match_accuracy`=1）、B17 `x817`（empty，三切分均为 0）；本轮运行产物不入库，明细见 B16/B17 NOTES 验证记录 |
| 基线 | 未建立，17 个 `baseline.json` 的 `run_id` 为 null |
| 门槛 | 仅 2 条绝对门槛（B01 行保留率、B12 外泄率），其余待首轮回填 |

| 任务 | 用例数 | manifest | status | 数据状态 |
|-|-|-|-|-|
| B01 不规则表格理解 | 240 | v0.2 | collecting | 已构建 |
| B02 文档解析与 OCR | 240 | v0.2 | collecting | 已构建 |
| B03 字段抽取与锚点 | 240 | v0.3 | collecting | 已构建 |
| B04 制度 → 规则 → 可判定性与适用范围 | 240 | v0.3 | collecting | 已构建（二分类域，label 归一 yes/no） |
| B05 指标定义与语义查询编译 | 240 | v0.10 | collecting | 已构建 |
| B06 召回检索与检索充分性 | 240 | v0.1 | collecting | 已构建 |
| B07 端到端多步数据分析 | 240 | v0.2 | collecting | 已构建 |
| B08 预测与优化 | 240 | v0.4 | collecting | 已构建 |
| B09 表格计算、图表与报告 | 240 | v0.5 | collecting | 已构建 |
| B10 持续监控与告警 | 240 | v0.4 | collecting | 已构建 |
| B11 动作执行与策略遵从〔FDE〕 | 240 | v0.1 | collecting | 已构建 |
| B12 权限、敏感信息与外部数据安全 | 113 | v0.1 | collecting | 已构建 |
| B13 记忆与经验召回 | 240 | v0.2 | collecting | 已构建 |
| B14 数据建模与物化 | 224 | v0.1 | collecting | 已构建 |
| B15 FDE 交付效果 | 0 | v0.0 | planned | 待下载/待建 |
| B16 多源对齐与实体解析 | 240 | 当前版本以 dataset/manifest.json 为准 | collecting | 已构建 |
| B17 字段映射 / schema matching | 146 | v0.4 | collecting | 已构建 |

B16/B17 当前版本以 dataset/manifest.json 为准。数据构建命令与引用规则见 §9；不可得来源的原因与所需动作见 §9.2；每个任务的指标覆盖写在 `manifest.build.coverage` 与 `tasks/<task>/NOTES.md`「数据构建」。

首个 `r` 轮次（`r001`）范围定为 **B02、B03、B16、B17**：主指标（`text_ned`、`value_f1`、`entity_pair_f1`、`mapping_top1`）都有可判分金标，且原子有实现；B04 随后补。B01 暂不纳入：它的主指标 `header_cell_accuracy` 需要表头结构标注，公开数据只有问答答案；按严格规则从原始工作簿派生表头只覆盖 15/240 条，样本量不足以支撑 block 门槛，待人工标注 60 条后再进轮次。

B03 的证据金标是**派生**的：CORD 用 OCR 词序列把字段值对齐成词级 span（70 条），ExtractBench 从 schema description 的 "page N" 取字段页码（约 29% 用例有提示）；FUNSD 只有 bbox，留给后续 `bbox_iou` 判分器。B04 的 `decidability_accuracy` 与 `condition_direction_consistency` 仍缺金标（需三分类标注与正反配对），不参与 gate。
