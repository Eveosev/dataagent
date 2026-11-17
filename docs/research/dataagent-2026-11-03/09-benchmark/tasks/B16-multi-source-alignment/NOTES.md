# B16 多源对齐与实体解析 — 迭代记录

## 现状

- 状态：`collecting`，用例 240 条（development 120 / regression 60 / unseen_acceptance 60），基线未建立。
- 原子：DA02.5.1、DA02.5.2、DA02.5.3（Join 关系发现）；DA03.2.1、DA03.2.2、DA03.2.3（身份对齐）。
- 参考：DeepMatcher（SIGMOD 2018）基准集、Leipzig DBS benchmark datasets for entity resolution、Magellan。
- 主指标：`entity_pair_f1`；次指标：`false_merge_rate`（越低越好）。

## 为什么不用单测覆盖

同名异物、跨源字段差异、多对一匹配与记录噪声只在真实商品/文献分布上出现；单测能钉住判分公式，不能替代成对记录上的召回与误合并测量。

## 数据构建

### 许可核实

| 候选 | 许可 | 结论 |
|-|-|-|
| DeepMatcher UW-Madison `Datasets.md` 镜像 | 数据集许可未声明；仓库 `LICENSE` 为 BSD-3-Clause，只覆盖代码 | 不采用镜像 |
| Magellan `anhaidgroup/magellan` | MIT（当前仓库只含项目站点代码，不再分发基准数据） | 不采用 |
| Fodors-Zagats、iTunes-Amazon、Walmart-Amazon、BeerAdvo-RateBeer、Company | 原始站点与 DeepMatcher 镜像均未声明可再分发许可 | 舍弃 |
| DBLP-ACM、Amazon-Google、Abt-Buy | Leipzig DBS group 自 2019-01 起以 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 发布；[发布页](https://dbs.uni-leipzig.de/research/projects/object_matching/benchmark_datasets_for_entity_resolution) 的 January 2019 声明链接到该 4.0 条款（2026-11-17 核对） | 采用 |

采用的数据集就是 DeepMatcher 论文使用的同一批成对实体匹配集，但抓取 Leipzig 原始发布而不是 UW-Madison 镜像：镜像没有数据集级许可，Leipzig 发布页的 January 2019 声明以 Creative Commons license 提供这些数据集，许可链接指向 CC BY 4.0，并要求署名 Leipzig DBS group / Köpcke et al., VLDB 2010。manifest 的 `sources[].license` 与 `build.coverage.license_audit` 都记了这条链。

### 许可证据（2026-11-17 核对）

发布页：<https://dbs.uni-leipzig.de/research/projects/object_matching/benchmark_datasets_for_entity_resolution>。原文：

> January 2019: These datasets are made available by the database group of Prof. Erhard Rahm under the [Creative Commons license](https://creativecommons.org/licenses/by/4.0/).

同页表格列出 Abt-Buy、Amazon-GoogleProducts、DBLP-ACM 及各自的 perfect mapping；声明中的 “Creative Commons license” 直接链接到 `https://creativecommons.org/licenses/by/4.0/`。旧 `old.dbs.uni-leipzig.de` 子域返回 403，不作为证据。manifest 的 `sources[].license_url`、`sources[].license_evidence` 与 `build.coverage.license_audit` 记录同一链接和引文。

### 用例形状

每条用例给一条左表记录与 5–8 条右表候选：

```json
{
  "left": {"id": "...", "title": "..."},
  "right_candidates": [{"id": "...", "title": "..."}, ...]
}
```

金标是 `expected.pairs` 的实体对列表，只来自数据集自带的 `*_perfectMapping.csv`。Amazon-Google 有 1,300 对、1,113 条左记录，其中 144 条左记录对应多个右记录；候选里保留该左记录的全部真匹配。

非金标候选按数据集 gold mapping 的排他性视为非匹配：同一左记录的真匹配已在 gold mapping 中列全，候选里的其它右记录不是它的匹配。这是 DeepMatcher / Magellan 成对评测的通行口径，也是本任务唯一的负例来源；未标注的真匹配是已知噪声，写进 manifest `build.coverage.note`，不当成 0 分理由。

候选负例取同 split 内与左记录 token Jaccard 相似度最高的 4 条，过滤相似度 ≥ 0.95 的近重复；候选顺序按哈希固定，金标不会总在首位。

### 切分

- 先按 gold mapping 做连通分量，再对分量键做固定 sha256 60/20/20；同一实体的记录不跨 split。
- 候选只从同 split 的右表记录里取；未进 gold mapping 的右记录按自身 id 哈希分配 split。
- `tools/build_cases.py` 的默认上限 120/60/60 再按 case_id 哈希截取；两次构建的用例内容一致，内容摘要不变时 revision / build.version 保持不变。
- 3 个源的可用用例：development 2,623 / regression 906 / unseen_acceptance 889；取 240 条入册。

## 判分口径

`harness/graders/entity_pair_f1.py` 提供两个入口：

- `grade()` → `entity_pair_f1`：微观 F1，`2TP / (2TP + FP + FN)`，跨用例 `pooled`。
- `false_merge()` → `false_merge_rate`：`FP / (TP + FP)`，即已预测合并中错误合并的占比；单用例没有预测合并时记 0（没有发生错误合并）。它只惩罚误合并，不惩罚漏合并；漏合并由 F1 反映。跨用例按预测实体对 `pooled` 汇总：总 FP / 总 (TP + FP)；若全部用例都没有预测合并，pooled 分母为 0，scorecard 的 value 为 null（没有可汇总的合并，不当作 0 分）。

产出接受 `pairs` / `matches` / `links` / `alignment` 的实体对列表，也接受 `clusters`（先对簇成员求连通分量，再展开左记录与簇内所有其他成员的实体对；候选集外成员也计入 FP；`[[L,R1],[R1,R2]]` 会经 R1 合并为同一实体）和 `{"right_ids": [...]}`。左 id 缺省时用用例的 `left_id`；预测出候选集外的 id 或错误左 id 仍计 FP，并在 notes 的 `invalid` 计数里记数。

## 覆盖与缺口

- 已覆盖：实体对 F1、错误合并率。
- 缺口：`conflict_retention_rate`（冲突保留率）。三个源只标注实体对，未标注跨源同对象的值冲突；按 README §9「覆盖诚实」记录，不用假金标补。
- 范围：本轮评成对实体对齐（左记录 → 右候选），不含 N 路聚类与 Join 计划生成。
- 生成器 `tools/converters/B16.py`；原始数据在 `workspace/benchmark-data/B16/`，不入库。

## 待办

1. 首次 `r` 轮次跑完后，按 `monitor/thresholds.json` 回填门槛。
2. 首次基线写入 `history/baseline.json`；趋势看板由 `tools/report.py` 生成，本文件只记结论与决策。
3. 若后续补到带值冲突标注的跨源样本组，再加 `conflict_retention_rate`，不改已进门禁的主指标。

<!-- data-build:start -->
## 数据构建摘要

- 构建：`tools/build_cases.py --task B16`（转换器 `tools/converters/B16.py`）；当前版本以 `dataset/manifest.json` 为准
- 版本：`build_cases.py` 对 cases、expected、fixtures 与 sources 算内容摘要；摘要不变时重复构建不升 `revision`
- 原始数据：`leipzig-dblp-acm`、`leipzig-amazon-google`、`leipzig-abt-buy`，落在 `workspace/benchmark-data/B16/`
- 当前用例：development 120 / regression 60 / unseen 60（共 240）
- 金标：数据集自带 `perfectMapping.csv`；非金标候选按排他性视为非匹配
- 指标覆盖：已覆盖 `entity_pair_f1`、`false_merge_rate`；缺口 `conflict_retention_rate`
<!-- data-build:end -->

## 迭代日志

| 轮次 | 结论 | 变更 |
|-|-|-|
| x424 / x929 | oracle F1=0（适配器缺 B16 分支），empty F1=0；240/240 全部产出；FMR 按预测对 pooled，无合并时 value=null | 修复聚类传递闭包与 FMR 汇总；数据 v0.7（历史） |
| x506 / x009 | oracle 三切分 F1=1、FMR=0；empty 三切分 F1=0；240/240 全部产出 | 补 oracle B16 分支；聚类候选集外成员计 FP；数据 v0.8（历史） |
| x816 / x320 | oracle 三切分 F1=1、FMR=0；empty 三切分 F1=0；240/240 全部产出 | 数据 v0.9（历史） |
| x434 / x938 | oracle 三切分 F1=1、FMR=0；empty 三切分 F1=0；240/240 全部产出 | 数据 v0.10（历史）；补许可证据 |
| x544 / x045 | oracle 三切分 F1=1、FMR=0；empty 三切分 F1=0；240/240 全部产出 | 补充验收轮；版本见验证记录 |

## 验证记录

版本列只记录该轮构建的数据版本；当前版本以 `dataset/manifest.json` 为准。

| run_id | 适配器 | development F1 / FMR | regression F1 / FMR | unseen_acceptance F1 / FMR | 数据 |
|-|-|-|-|-|-|
| `x434-2026-11-17` | oracle | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | v0.10 |
| `x938-2026-11-17` | empty | 0.000 / null | 0.000 / null | 0.000 / null | v0.10 |
| `x544-2026-11-17` | oracle | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | v0.11 |
| `x045-2026-11-17` | empty | 0.000 / null | 0.000 / null | 0.000 / null | v0.11 |

FMR 的 `null` 表示该切分没有预测合并，pooled 分母为 0；不是 missing，也不是 0 分。本轮运行产物在 `history/runs/`，按 `.gitignore` 排除；验证结论以上表为准。
