# B04 制度 → 规则 → 可判定性与适用范围 — 迭代记录

## 现状

- 状态：`collecting`，用例 240 条已建，基线未建立。
- 原子：DA02.8.1, DA02.8.2, DA03.4.3, DA03.15.1, DA03.15.2, DA03.15.3, DA03.15.4, DA03.16.1, DA03.16.2, DA03.16.3, DA03.16.4
- 参考：RuleArena, DeonticBench

## 为什么不用单测覆盖

规则选错、条件方向写反、unknown 被当作确定结论；方向性错误需要成对反例才能暴露。

## 待办

1. 按 `dataset/manifest.json` 的 sources 采集并脱敏，写入 `dataset/cases/`，金标与输入分离。
2. 落地 grader：decidability_classification, direction_symmetry, rule_choice_match, unknown_preservation。
3. 第 1 次 r 轮次跑完后，按 `monitor/thresholds.json` 回填各指标门槛。
4. 首次基线写入 `history/baseline.json`；趋势看板由 `tools/report.py` 生成，本文件只记结论与决策。

<!-- data-build:start -->
## 数据构建

- 构建：`tools/build_cases.py --task B04`（转换器 `tools/converters/B04.py`），manifest `v0.3`
- 原始数据：deonticbench，落在 `workspace/benchmark-data/B04/`
- 当前用例：development 120 / regression 60 / unseen 60（共 240）
- 标签口径：只取二分类域 `housing` / `sara_binary` / `uscis-aao`，`yes/1/Accepted → yes`、`no/0/Dismissed → no`，原始值保留在 `gold.raw_label`；unseen 中 yes 21 / no 39
- 未入库：`airline` 与 `sara_numeric` 的 label 是数值答案（计数题），与 `rule_selection_accuracy` 的分类口径不兼容
- 去重：`hard` 是 `whole` 的子集，只作为标签复用，不重复入库
- 指标覆盖：已覆盖 rule_selection_accuracy；缺口 condition_direction_consistency、decidability_accuracy、unknown_retention
- 说明：airline 与 sara_numeric 的 label 是数值答案，不适用于分类指标，未入库；二分类域没有 unknown 标签，unknown_retention 需自建歧义用例；方向一致性与三分类需自建配对/标注。
<!-- data-build:end -->

## 指标可判性

| 指标 | 状态 | 说明 |
|-|-|-|
| `rule_selection_accuracy` | 可判 | DeonticBench 的 yes/no/unknown 判定标签 |
| `unknown_retention` | 当前无样本 | 二分类域没有 unknown 标签；需自建歧义用例（指标保留，计 0 分母 missing） |
| `decidability_accuracy` | 缺金标 | 需要三分类（decidable / needs_evidence / undecidable）标注；DeonticBench 只给二分类判定 |
| `condition_direction_consistency` | 缺金标 | 需要同规则正反配对（同事实、相反取向），公开集没有配对关系 |

前两项已能支撑 B04 的 block 门槛（`blocking_metrics` 只含 `rule_selection_accuracy`）；后两项要自建配对集与三分类标注，补齐前不参与 gate。

## 迭代日志

| 轮次 | 结论 | 变更 |
|-|-|-|
| — | 尚未运行 | — |
