# B17 字段映射 / schema matching

## 现状

- `status=collecting`，`primary_metric=mapping_top1`，`gate_tier=warn`，`in_ci=true`。
- 公开子集已构建：10 对表、146 个源字段（77 个有目标字段、69 个无对应字段），三个 split 共 146 条用例。
- oracle 满分、empty 地板已跑通；基线未建立，`history/baseline.json` 的 `run_id` 仍为 `null`。
- 私有子集（令才字段目录与报文映射）和业务数据未进入本轮，按缺口登记，由 T34b 及后续现场交付补。

## 任务范围

| 项 | 内容 |
|-|-|
| 输入 | 源表与目标表的列名、行数、每列至多 2 个截断样例值；一个源字段 |
| 输出 | 该源字段的 top-1 目标列名；无对应字段时显式 `null` 或空数组 |
| 金标 | Valentine `ground_truth.json.matches`；未出现的源字段按 `has_false_positives=false` 记为无对应字段 |
| 主指标 | `mapping_top1`：正确字段数 / 总源字段数，pooled |
| 次指标 | `no_match_accuracy`：无对应字段子集上显式返回空的比例，pooled；无该子集的用例记 missing |
| 不在范围 | 多对多映射、复合键、Join 计划、值转换、跨表主外键推断；计划行中的 DA02.3 结构转换（转置/宽长表/嵌套展开）也未登记为已覆盖原子 |

`catalog_atoms`：`DA02.4.2`、`DA02.4.3`、`DA02.9.1`、`DA02.9.3`、`DA03.6.2`。这些原子在 Catalog 中描述字段画像、类型推断、Schema 差异与语义表列映射；本任务只覆盖单源字段到单目标字段的 top-1，不把多对多、Join 或 DA02.3 结构转换算作已覆盖。

## 参考 benchmark

| 参考 | 用途 | 说明 |
|-|-|-|
| [Valentine](https://github.com/delftdata/valentine) v1.1.1 | 数据与评测口径 | schema matching 框架；`experiments/data/` 含 10 对 NYU 表，每对 `source_table.csv`、`target_table.csv`、`ground_truth.json` |
| [Valentine ICDE 2021](https://ieeexplore.ieee.org/abstract/document/9458921) | 方法背景 | 原始论文的数据归档已不可用；本轮不声称复现论文全量实验 |

## 数据构建

### 来源

- 源 ID：`valentine-schema-matching`
- 仓库：`https://github.com/delftdata/valentine.git`
- 版本：tag `v1.1.1`，解析到 commit `19029e3c9b1c3d5fc514ab601f658307c37c8e1c`
- 目录：`experiments/data/`，10 对表
- 抓取：`python3 -I tools/fetch.py --task B17`；`FETCH.json` 记录 202 个文件、140.0 MB、digest `sha256:4a54d50c...`
- 原始数据只落 `workspace/benchmark-data/`（仓库 `.gitignore` 已忽略），不进入 Git

### 许可核实

| 候选 | 许可 | 决定 | 证据 |
|-|-|-|-|
| Valentine 官方仓库 v1.1.1 `experiments/data`（10 对表） | Apache-2.0 | 采用；manifest 记 attribution | [LICENSE](https://github.com/delftdata/valentine/blob/v1.1.1/LICENSE)：`Copyright 2021-2026 Delft University of Technology`，`Licensed under the Apache License, Version 2.0` |
| Valentine 原始论文数据集归档（surfdrive） | 未声明；分享页不可用 | 不采用；2026-11-18 访问 404，Wayback 快照 zip 截断为 1 MB | `https://surfdrive.surf.nl/files/index.php/s/QU5oxyNMuVguEku` |
| `valentine-paper-results` | 仓库含结果与可视化，未声明原始数据许可 | 不采用；只有算法输出，没有原始表对与金标 | `https://github.com/delftdata/valentine-paper-results` |
| `valentine-generator` | 代码仓库，数据集不随仓库分发 | 不采用；需要外部基础表，不能独立产出一致快照 | `https://github.com/delftdata/valentine-generator` |
| NYC Open Data（原始来源） | NYC Open Data Terms of Use | 作为 provenance 署名，不单独作为再分发许可 | `https://opendata.cityofnewyork.us/overview/` |

数据 README（`experiments/README.md`）写明：表对由 Yurong Liu 整理，来自 NYC Open Data，并用 LLM 做 schema/value 扰动；每对含 `source_table.csv`、`target_table.csv`、`ground_truth.json`。

10 对表逐对核对：目录都含上述三件套，均无独立 LICENSE 或相反声明；按仓库根 LICENSE 的 Apache-2.0 处理，清单见 `manifest.build.coverage.license_audit[0].datasets`。再分发按仓库 Apache-2.0 执行，manifest `sources[].attribution` 与每个 expected 文件都保留署名。

### 用例形状

一条用例对应一个源字段。`dataset/fixtures/<case_id>.json` 含：

- `source_table` / `target_table`：表路径、行数、全部列名、每列至多 2 个截断到 80 字符的样例值
- `source_field`：待映射的源字段
- `instruction`：要求 top-1；无对应字段显式返回 `null`/空数组

`dataset/expected/<case_id>.json` 含 `source_field`、`target_field`（字符串或 `null`）、`candidate_targets`、来源、许可、attribution。输入与金标分离；fixture 不含完整行，expected 只在判分时读。

### 切分

- 固定盐 `valentine-pair-v1-000029`，按 `sha256(salt + ":" + pair_dir)` 前 8 位 hex mod 100 分桶：`<60` development，`<80` regression，其余 unseen_acceptance。
- 同一表对的全部源字段落在同一 split，避免同表跨 split 泄漏。
- 结果：

| split | 表对 | 字段 | 有目标字段 | 无对应字段 |
|-|-|-|-|-|
| development | Capital Projects、DCM StreetCenterLine、DPR Athletic Facilities、COVID Free Meals、Public Art Inventory、Swim for Life | 93 | 47 | 46 |
| regression | Housing Maintenance、Street Resurfacing | 28 | 17 | 11 |
| unseen_acceptance | DSNY Districts、NYC Energy Benchmarking | 25 | 13 | 12 |

盐只用于分桶，不参与用例内容或金标；改盐等于换切分，必须同步升 manifest revision 并在 NOTES 记原因。样本暴露按表对整体降级，避免同表字段跨 split。

### 金标口径

- 正例只取 `ground_truth.json.matches[].source_column` 与 `target_column` 的精确匹配；本批 10 对表无重复 source、无目标列不在 target 表头的情况。
- 源表头中未出现在 `matches` 的字段记为 `target_field=null`。依据有两条：Valentine 自己的评测（`experiments/bench.py`）只把 `matches` 当正例，预测出任何不在此集合的 pair 都计 FP；每对 `meta.has_false_positives=false` 又说明 `matches` 内没有错标。因此未列入 `matches` 的源字段在本口径下就是无匹配，不是本项目额外推断的金标。
- 没有生成、补写或人工改写任何金标；`expected` 的 `annotation` 字段保留这一口径。

## 判分口径

`harness/graders/mapping_top1.py` 实现两个入口：

| 指标 | 口径 |
|-|-|
| `mapping_top1` | 每个源字段只看 top-1；目标字段正确得 1，错误或未作答得 0；总正确数 / 总源字段数 |
| `no_match_accuracy` | 只看金标为 `null` 的字段；显式 `null`/空数组得 1，否则 0；无此类字段的用例 `value=None` |

细节：

- 无对应字段必须显式作答：输出 `{}`、省略该源字段、或只给其他字段，都算未作答，按 0 计。空容器 `{"mappings": []}` 视为显式空答案。
- 列名归一：NFKC、casefold、去空格/下划线/连字符；`First Name`、`first_name`、`firstName` 视为同一列。
- 目标列必须落在 `candidate_targets` 内；落在候选外的预测判错，并在 notes 计 `invalid`。
- 输出形状兼容 `target_field`、`target`、`mappings`（dict/list）、`matches`、`pairs`、`fields`、`right_ids` 等；同一源字段出现多次取第一次（top-1）。
- 空适配器返回 `{}`，对正例和无匹配字段都算未作答，因此地板是 0，不是“无匹配也得分”。

## 覆盖与缺口

已覆盖：

- 77 个有目标字段的正例，69 个无对应字段的负例；三个 split 都同时含两类。
- 列名同义/缩写（如 `total_changes` → `total_schedule_changes`）、大小写与分隔符差异、部分列值扰动。
- 无匹配字段的显式空答案；这是 schema matching 最容易“硬猜一个最近列”的失败模式。

部分覆盖：

- 只有 schema 级列名与少量样例值，没有实例级值匹配、类型约束、主外键、复合键。
- 只有 10 对表、NYC Open Data 一个来源；跨行业、中文业务字段未覆盖。
- 只有 top-1 单目标；数据集中若存在多对多，本任务不评测。

缺口（不编金标）：

| 缺口 | 影响 | 下一步 |
|-|-|-|
| 私有子集（令才字段目录与报文映射）未接入 | 无法衡量令才真实字段名、别名与报文结构上的 top-1 效果；公开子集分数不能替代私有验收 | T34b 接入字段目录与人工确认映射，按 `private://` 解析补私有子集；私有数据不进 Git、不进日志正文 |
| 业务数据（客户字段目录、人工映射、值域）未提供 | 跨行业、中文命名与客户习惯未覆盖；结论只适用于公开英文表结构 | 客户授权并脱敏后登记独立来源，补 development/regression；unseen_acceptance 只放未暴露样本 |
| Valentine 原始论文全量数据不可得 | 不能声称复现论文全量结果；样本只有 10 对 NYU 表 | 保持公开子集口径；如后续拿到可复核归档，再升 revision 并重跑 |
| 无多对多/复合键标注 | 不能评测一对多、多对一、复合键拼接 | 单列新任务或扩展 expected 形状后再做，不在本轮伪造 |

## 验证记录

运行产物在 `history/runs/`，已被 `tasks/B17-schema-matching/.gitignore` 的 `history/runs/` 忽略，不提交。

| 检查 | 命令 | 结果 |
|-|-|-|
| 抓取 | `python3 -I tools/fetch.py --task B17` | 1/1；首次 ok，复跑 cached；202 文件 / 140.0 MB；commit `19029e3c...` |
| 构建 | `python3 -I tools/build_cases.py --task B17` | development 93 / regression 28 / unseen_acceptance 25；146 条；revision `v0.4`；content digest `sha256:723ded0e0183` |
| 构建幂等 | 再跑一次 `build_cases.py --task B17` | `changed=False`，revision 保持 `v0.4`，digest 不变 |
| 判分器单测 | `python3 -I tasks/B17-schema-matching/tests/test_mapping_top1.py` | 12 tests OK |
| oracle | `python3 -I harness/run.py --task B17 --adapter oracle --round-id x315-2026-11-18` | 146/146 ok；三切分 `mapping_top1=1.0`、`no_match_accuracy=1.0` |
| oracle 验收 | `python3 ~/Vibe/dataagent-private/bin/bench_score_check.py tasks/B17-schema-matching/history/runs/x315-2026-11-18/scorecard.json mapping_top1=1` | exit 0；三切分均 `1.0` |
| empty | `python3 -I harness/run.py --task B17 --adapter empty --round-id x817-2026-11-18` | 146/146 ok；三切分 `mapping_top1=0.0`、`no_match_accuracy=0.0` |
| empty 验收 | `python3 ~/Vibe/dataagent-private/bin/bench_score_check.py tasks/B17-schema-matching/history/runs/x817-2026-11-18/scorecard.json mapping_top1=0` | exit 0；三切分均 `0.0` |
| 目录契约 | `python3 tools/check.py` | exit 0；`tasks=17 atoms=196`；B17 无 ERROR；其余任务的 WARN 为既有缺口（原始数据未下载、grader 未实现、未安装 jsonschema） |
| schema 校验 | 临时 venv 装 `jsonschema` 后跑 `python tools/check.py`，并对 `x315/x817` 的 `run.json`、`scorecard.json` 调 `jsonschema.validate` | 全部通过；默认环境未装 `jsonschema`，因此上述契约检查会跳过 schema 并打 WARN |
| 运行产物忽略 | `T=$(ls -d tasks/B17-*); test -z "$(git ls-files $T/history/runs)"; git check-ignore -q $T/history/runs/probe/scorecard.json` | exit 0 |

分 split 明细（oracle）：

| split | cases | mapping_top1 | no_match_accuracy |
|-|-|-|-|
| development | 93 | 93/93 = 1.0 | 46/46 = 1.0 |
| regression | 28 | 28/28 = 1.0 | 11/11 = 1.0 |
| unseen_acceptance | 25 | 25/25 = 1.0 | 12/12 = 1.0 |

## 待办

- 首次 `r` 轮次后写 `history/baseline.json`；当前基线为空，门槛用 `pending_baseline`。
- T34b 接入私有子集；业务数据由客户授权后另立来源。
- 若后续要评测多对多/复合键，先扩展 expected 与 grader 口径，再补数据；不要用当前 top-1 指标冒充。
