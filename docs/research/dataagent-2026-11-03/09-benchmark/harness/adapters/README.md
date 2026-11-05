# adapters：把统一入参翻译成被测系统调用

契约（`harness/README.md` §2）：

```python
def run_case(case: dict, env: dict, cfg: dict) -> dict
```

出参必须含 `case_id`、`status`（ok / failed / timeout / skipped）、`output` 或 `error`；
失败要显式给 `status` 与 `error`，**不得用空输出冒充成功**。

| 适配器 | 用途 | 产出 | 能不能当模型分数 |
|-|-|-|-|
| `dataagent-cli.py` | 真实被测系统：`dataagent run --case ... --out ... --config ...`，读 `<out>/result.json` | 模型输出 | 能（CLI 就绪后） |
| `oracle.py` | 链路自检：直接回填金标 | 完美输出 | **不能**，`env.model=null`，只验证 judge 口径 |
| `empty.py` | 下限基线：什么也不输出 | 空 | 不能当能力分，但可作为指标下界参考 |

## 本地调用

```bash
# 链路自检（应满分）
python3 -I harness/run.py --task B02 --adapter oracle --round-id x001-2026-11-05

# 下限基线（应最低分）
python3 -I harness/run.py --task B02 --adapter empty --round-id x002-2026-11-05

# 真实 CLI（当前机器未安装 dataagent，会如实记 failed）
python3 -I harness/run.py --task B02 --adapter dataagent-cli --round-id x003-2026-11-05 --limit 3
```

`run.py` 会把 `run.json`、`cases.jsonl`、`predictions.jsonl`、`artifacts/`、`scorecard.json`、`detail.jsonl`
写到 `tasks/<task>/history/runs/<round-id>/`，随后可跑 `tools/check.py` 校验一致性。

## 新增适配器

在同目录加 `<name>.py`，暴露 `run_case`，然后 `--adapter <name>` 即可；`env.adapter` 会原样写进 `run.json`，
换适配器等于换尺子，Δ 不可直接比。
