# scorecard 记分卡

每轮每个任务一份 `history/runs/<round-id>/scorecard.json`。结构见 `schema/scorecard.schema.json`；本文件说明怎么填、怎么裁定。

## 1. 填写顺序

1. 跑完三个 split，逐用例写 `cases.jsonl`（`samples.scored` 必须等于其中 `status=ok` 的行数）。
2. 按 `task.json.metrics` 填 `split_scores.<split>.metrics`：每项 `value` / `numerator` / `denominator`。
3. 对 `baseline.json` 快照算 `deltas`（仅 `direction=higher` 取正差值；`lower` 指标也存原始差值，符号不给解释权，解释在 `gate`）。
4. 写 `verdict`，再写 `gate`。顺序不能反：先有结论，再判门禁。

## 2. verdict 定义

| verdict | 含义 | 使用条件 |
|-|-|-|
| `pass` | 全部阻断指标达门槛，且无缺失 | `samples.missing` 为空 |
| `fail` | 任一阻断指标未达门槛 | 必须填 `gate.blockers` |
| `unknown` | 样本量不足或指标不可判定 | 样本 < `defaults.min_samples_for_gate`，或关键 grader 返回 `null` |
| `not_applicable` | 本轮不该跑这个任务（如 B15 未接入客户） | `samples.total=0`，且在 `notes` 写原因 |

`unknown` 不等于通过：门禁遇到 `unknown` 按未通过处理，但保留 `blockers` 为空，便于区分「坏」与「没测」。

## 3. gate 推导

| 层级 | `decision` 取值 | 规则 |
|-|-|-|
| `block` | `release` / `hold` | 任一 `blocking_metrics` 跌破绝对门槛或超相对阈值 → `hold`，写入 `blockers` |
| `guard` | `release` / `hold` | 泄漏类指标 > 0 → `hold`；其余按 `warn` |
| `warn` | `warn` / `record_only` | 只记 Δ，不阻断 |
| `field` | `record_only` | 季度汇总，不参与当轮门禁 |

相对阈值来自 `monitor/thresholds.json.defaults`：`block_drop_pp` 与 `block_relative` 取更严者；`lower` 方向指标把「跌幅」换成「升幅」。

## 4. 示例（B01，一轮中 `unseen_acceptance` 已建）

```json
{
  "run_id": "r003-2026-11-18",
  "task_id": "B01",
  "baseline_run": "r001-2026-11-05",
  "split_scores": {
    "development": {"count": 120, "metrics": {
      "header_cell_accuracy": {"value": 0.94, "numerator": 113, "denominator": 120},
      "row_retention": {"value": 1.0, "numerator": 9840, "denominator": 9840}
    }},
    "regression": {"count": 60, "metrics": {
      "header_cell_accuracy": {"value": 0.92, "numerator": 55, "denominator": 60}
    }},
    "unseen_acceptance": {"count": 80, "metrics": {
      "header_cell_accuracy": {"value": 0.913, "numerator": 73, "denominator": 80},
      "row_retention": {"value": 1.0, "numerator": 6120, "denominator": 6120},
      "downstream_qa_accuracy": {"value": 0.87, "numerator": 70, "denominator": 80}
    }}
  },
  "deltas": {"header_cell_accuracy": -0.017, "row_retention": 0.0},
  "verdict": "pass",
  "gate": {"tier": "block", "decision": "release", "blockers": []},
  "notes": "多行表头子集 -3.2pp，合并单元格子集 +1.4pp；未达告警线"
}
```

## 5. 常见错误

| 错误 | 为什么不行 | 正确做法 |
|-|-|-|
| 把 `missing` 当 0 分 | 分母被动扩大，指标虚低但趋势被掩盖 | 记入 `samples.missing`，`value=null` |
| 分母为 0 仍填 `pass` | 无样本的通过是假通过 | `verdict=unknown` 或 `not_applicable` |
| 只跑 `development` 就报分 | 调参集不具验收意义 | `unseen_acceptance` 必须跑，否则 `unknown` |
| 换 split 凑分 | 同一任务跨轮次 split 必须一致 | 换 split 视作改数据版本，`manifest.revision` 升版并标注不可比 |
| 手改历史 scorecard | 基线不可信 | 重跑并生成新轮次 |
