# r3 修复记录：r2-review 阻塞项与更正

- 日期：2026-11-06；开发者自评见 [r3-runtime.score.json](r3-runtime.score.json)（**89.0 / B / GATE-UNKNOWN**，见下）
- 修复前源码快照：`/tmp/agentos-snapshots/pre-r3-20261106-025505.tar.gz`（AgentOS 非 git 仓库）
- 修复后快照：`dataagent-runtime@sha256:78c93a64776a5dbc4ad45fd9c3f9f849d5d105b300f08179445fcaa2f9e1f400`（67 文件）

## 更正：R13 按标准记 unknown（r2-review §0/§6）

r2 自评把 R13 记 `na` 不符合 [code-landing-rubric.md](../../../standards/code-landing-rubric.md):240,279（「无基线记 unknown」）。r3 自评更正为 **unknown**，因此自评即 **89.0（B）/ GATE-UNKNOWN / 不可验收**，与 Tester r2 独立评分同构。

**清除 R13 的两条路径都超出开发者权限**，需要 owner（人）决策：

1. **发布基线制品**：AgentOS 非 git 仓库（无法打 tag）；Mint Hub 发布在本方案范围外（[12-unified-cli-build-plan.md](../12-unified-cli-build-plan.md) 明示 Q3）。发布会改变共享 Hub 状态并扩大方案范围。
2. **带日期的硬规则豁免**：rubric 允许（skill 决策规则「hard rules only 记录 dated exemption」），但豁免只能由标准 owner 给出。

开发者不在本轮单方面执行任何一条；已提交决策请求。

## D8（P2）：`--file` 缺文件 → 结构化 usage error（exit 2）

- 位置：`packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py:484-490`
- 改法：`_build_payload` 对 `hooks.make_file_ref(runtime, path)` 捕获 `OSError`（含 FileNotFoundError）→ `UsageError`，走既有 exit-2 通道；与 `_load_json_file`（:180-186）同构。
- 证据：
  - 黑盒复跑（r2-review §8 命令）：`python -m dataagent_data.interfaces.cli run parse_delimited_file --file nope.csv` → **exit 2**，stderr `usage error: --file: cannot read nope.csv: [Errno 2] No such file or directory: '…'`，stdout 空，无 traceback（r2 为 exit 1 + FileNotFoundError traceback）。
  - 回归测试 `tests/test_unified_cli.py::test_file_hook_missing_file_is_usage_error`。
- 同步：`unified.py` 已字节同步进 runtime / data / application / governance 四个 bundle 的 vendored 树（diff -rq 验证一致）。

## D9（P2）：`gov confirm` 非法载荷 → 结构化 schema error（exit 2）

- 位置：`packages/capabilities/dataagent-governance/src/dataagent_governance/interfaces/cli.py:111-128`
- 改法：`_confirm_criteria` 把 `CriteriaConfirmation.model_validate` 与 `body["criteria_id"]`/`body["criteria_revision"]` 取键移入前置 try：`ValidationError` → stderr `confirm: invalid confirmation record: …` + exit 2（与 `_policy_apply` 同构）；`KeyError` → stderr `confirm: missing required field: …` + exit 2（同一缺陷类：非法载荷不再抛 traceback）。
- 证据：
  - 黑盒复跑：`confirm bad.json`（confirmation 缺 `criteria_digest`/`authority_ref`，`DATAAGENT_CONFIRMERS=user:boss`）→ **exit 2**，stderr `confirm: invalid confirmation record: 6 validation errors for CriteriaConfirmation`，无 traceback（r2 为 exit 1 + pydantic traceback）。
  - 同类：缺顶层 `criteria_id` → exit 2 `confirm: missing required field: criteria_id`。
  - 回归测试 `tests/interfaces/test_mcp_cli.py::test_cli_confirm_invalid_confirmation_is_usage_error`、`::test_cli_confirm_missing_criteria_id_is_usage_error`。
- 同步：gov bundle 的 vendored `cli.py` 已同步（diff -rq 一致）。

## 其余缺陷处置

| ID | r3 状态 | 说明 |
|-|-|-|
| D2 | partial | r3 新增代码（D8/D9 的 try/except）使 CC>10 占比 25.68%→25.77%（阈 7.3%）；CC>25 保持 0.0%（阈 1.1%，达标）。既有 enforcement/invoke/tabular 组合复杂度留待后续轮 |
| D3 | open | 默认超时与在途取消不在 W1 方案范围，保持 open |

## 机器测量与测试

```sh
cd /Users/payne/Vibe/AgentOS
# 快照
python3 skills/code-landing-quality/scripts/snapshot.py packages/capabilities/dataagent-runtime
#   → sha256:78c93a64…（67 文件）

# 五套测试
(cd packages/capabilities/dataagent-runtime && .venv/bin/python -m pytest -p no:warnings)      # 102 passed（+1：D8 回归）
(cd packages/capabilities/dataagent-data && .venv/bin/python -m pytest -p no:warnings)         # 654 passed
(cd packages/capabilities/dataagent-application && .venv/bin/python -m pytest -p no:warnings)  # 203 passed
(cd packages/capabilities/dataagent-governance && .venv/bin/python -m pytest -p no:warnings)  # 123 passed（+2：D9 回归）
(cd packages/capabilities/dataagent-cli && python3 -m unittest discover -s tests)              # 12 OK

# 机器测量（dataagent-runtime）
python3 skills/code-landing-quality/scripts/quality_run.py --repo . --package packages/capabilities/dataagent-runtime
#   重复率 2.21%（53/2402；包内 20、跨包 33）、裸 except/吞错 0/0、
#   CC>10 25.77%、CC>25 0.0%、bundle 漂移「一致」
# data/app/gov 三包 vendored 树经 diff -rq 与源码逐一比对：全部一致

# 评分（自评，R13=unknown）
python3 skills/code-landing-quality/scripts/score_landing.py \
  --result docs/research/dataagent-2026-11-03/12-cli-build/r3-runtime.score.json
#   总分 89.0（B）；闸门 GATE-UNKNOWN（R13）；未关闭 P2：D2 partial、D3 open

# 轮次对比
python3 skills/code-landing-quality/scripts/round_diff.py \
  docs/research/dataagent-2026-11-03/12-cli-build/r2-tester-runtime.score.json \
  docs/research/dataagent-2026-11-03/12-cli-build/r3-runtime.score.json
#   D8/D9 open→fixed，保持关闭 5，无回归、无新缺陷
```

## 变更文件清单

| 文件 | 变更 |
|-|-|
| `packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py` | D8：`_build_payload` 的 `--file` 分支捕获 `OSError` → `UsageError` |
| `packages/capabilities/dataagent-runtime/tests/test_unified_cli.py` | +`test_file_hook_missing_file_is_usage_error` |
| `packages/capabilities/dataagent-governance/src/dataagent_governance/interfaces/cli.py` | D9：`_confirm_criteria` 捕获 `ValidationError`/`KeyError` → exit 2 |
| `packages/capabilities/dataagent-governance/tests/interfaces/test_mcp_cli.py` | +2 个 D9 回归测试 |
| `packaging/bundle/src/…`（runtime/data/application/governance 四包） | vendored `unified.py`、gov `cli.py` 字节同步 |
| `docs/research/…/12-cli-build/r3-fixes.md`、`r3-runtime.score.json`、`r3.score.txt`、`README.md`、`12-unified-cli-build-plan.md` | 本记录与登记 |
