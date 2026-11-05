# harness：适配器与评分器契约

一次运行的固定形状：**读用例 → 调被测系统 → 存原始输出 → 用 grader 打分 → 写 scorecard**。harness 不判断好坏，判断在 `monitor/thresholds.json`。

## 1. 目录

| 路径 | 内容 |
|-|-|
| `config.default.json` | 适配器、并发、超时、重复次数、预算、环境版本；每轮可覆盖 |
| `adapters/<name>.py` | 把统一入参翻译成被测系统调用（CLI / MCP / HTTP），返回统一出参；现有 `dataagent-cli` / `oracle` / `empty`，见 `adapters/README.md` |
| `graders/<grader>.py` | 单个指标的判分实现，文件名即 `task.json` 里的 `metric.grader` |

各任务不单独放代码：同名 grader 跨任务复用（如 `exact_match` 同时服务 B07 的精确匹配与 B01 的下游问答），改一次全任务生效，避免 15 份判分逻辑漂移。

## 2. 适配器契约

```python
def run_case(case: dict, env: dict, cfg: dict) -> dict
```

入参 `case` 为 `dataset/cases/<split>/<case_id>.json`，`env`/`cfg` 来自 `config.default.json` 与本轮覆盖。出参：

```json
{
  "case_id": "B01-demo-001",
  "status": "ok",                  // ok | failed | timeout | skipped
  "output": {"ref": "artifacts/B01-demo-001.out.json"},
  "trace_ref": "artifacts/B01-demo-001.trace.jsonl",
  "tokens": 1820,
  "cost_usd": 0.0041,
  "latency_ms": 12400,
  "error": null
}
```

- `output` 允许内联小结果，超过阈值一律写文件留 `ref`，`cases.jsonl` 只存引用。
- 失败必须显式给出 `status` 与 `error`，不得用空输出冒充成功；空输出会让召回类指标虚高。
- 同一用例重复 `run.repeats` 次（默认 3，用于 `pass^k`），每次一个 `attempt`，`cases.jsonl` 每行一个 attempt。

被测系统入口（CLI 形式）约定：

```bash
dataagent run --case <case.json> --out <run_dir>/artifacts/<case_id> --config <cfg.json>
```

适配器负责把它包装成上面的出参；MCP 与 HTTP 适配器遵循同一出参，不另立字段。

## 3. grader 契约

```python
def grade(case: dict, output: dict, cfg: dict) -> dict
```

```json
{"metric": "header_cell_accuracy", "value": 0.91, "numerator": 91, "denominator": 100, "notes": null}
```

- `value=None` 表示不可判定（如断言无法定位），记入 `samples.missing`，**不得当 0 分**，也不从分母剔除。
- `denominator` 必须是真实可判定的单位数；聚合方式由 `task.json` 的 `metric.aggregation` 决定（`mean_over_cases` / `median_over_series` / `pooled` / `sum`）。
- grader 只算值，不含阈值与方向；方向（`higher` / `lower`）与门槛在 `task.json` 与 `thresholds.json`。
- 判分器版本写进 `run.json.env.harness`，与模型版本同级记录：换了判分口径等于换了尺子。

## 4. 运行顺序

1. 校验 `manifest.status` 不是 `deprecated`，`dataset.revision` 与本轮登记一致。
2. 按 split 顺序跑 `unseen_acceptance` **最后**，避免中途看结果调参。
3. 汇总为 `scorecard.json`：每个 split 一份指标，`deltas` 对 `baseline.json` 快照，`gate.decision` 由阈值规则给出。
4. 写 `cases.jsonl`（逐用例、逐 attempt），产物进 `artifacts/`。
5. 更新 `rounds/<round-id>.json` 的槽位状态；再跑 `tools/check.py` 与 `tools/report.py`。

## 5. 最低要求

- 确定性：固定 `run.seed`；不固定随机源的结果必须标注 `nondeterministic: true` 并强制 `pass^k`。
- 并发：默认 2，`unseen_acceptance` 建议 1，便于复现单条失败。
- 预算：`budget.max_usd_per_round` 未设时不阻断，但 `run.json.cost` 必须实测填写，不能为 null。
- 不联网：外部 benchmark 数据先落地为本地快照，跑分阶段不访问外网，保证同轮可重放。

## 6. 判分 CLI（`harness/grade.py`）

适配器产出预测后，用 `grade.py` 判分并直接写符合 `schema/scorecard.schema.json` 的 scorecard：

```bash
python3 -I harness/grade.py --task B02 --pred runs/<run>/predictions.jsonl \
  --run-id x001-2026-11-05 --out runs/<run>/scorecard.json --detail runs/<run>/detail.jsonl
```

- 预测文件每行 `{"case_id": "...", "output": {...}}`，或 `{"case_id": "...", "output_ref": "artifacts/x.json"}`（相对 `--run-dir`，默认预测文件所在目录）。
- `value=null` 的指标进 `missing` 计数，不参与聚合；聚合方式取 `task.json` 的 `metric.aggregation`。
- 某指标在所有 split 都判不了时，写进 `gate.blockers`，`verdict` 保持 `pending`——**不产出假分**。
- 自测：`python3 -I harness/tests/test_graders.py`（手算口径）、`python3 -I harness/tests/test_pipeline.py`（金标回填=满分、扰动=掉分、scorecard 合规）。

## 7. 运行 CLI（`harness/run.py`）

```bash
python3 -I harness/run.py --task B02 --adapter dataagent-cli --round-id r001-2026-11-05
python3 -I harness/run.py --task B02 --adapter oracle --round-id x001-2026-11-05 --split development
```

- 输出目录固定为 `tasks/<task>/history/runs/<round-id>/`，已存在且非空时拒绝覆盖，避免同一 run-id 混入两次结果。
- 写 `run.json`（samples/cost/env）、`cases.jsonl`（逐 attempt）、`predictions.jsonl`、`artifacts/`，并自动调用 `grade.py` 生成 `scorecard.json` 与 `detail.jsonl`。
- 适配器失败（CLI 缺失、超时、非 0 退出）→ `status=failed`、case 进 `samples.missing`、`run.status=failed`，不生成 scorecard。
