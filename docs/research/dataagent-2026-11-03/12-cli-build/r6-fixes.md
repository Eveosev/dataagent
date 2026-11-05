# r6 修复记录：r5-review 后续探针 5 项缺陷处置

## 背景

r5 验收（[r5-review.md](r5-review.md)）判可验收（93.1 / A），但 Reviewer 在相同源码快照上的补充探针发现 **5 项缺陷（4×P1 + 1×P2）**，补充评分 79.0（C）/ GATE-P1 + GATE-CHECKLIST，判定不可验收。本轮（r6）修复全部 5 项并补回归后重新送审。

| ID | 级 | 问题 | 位置 |
|-|-|-|-|
| D12 | P1 | `--ref` 无法把富句柄复用到 VersionedRef 字段：候选链验证失败后仍返回不兼容对象（`extra_forbidden`）；CriteriaRef 同样受影响 | `unified.py:346-356`（r5 行号） |
| D13 | P1 | mint.lock 锁定版本未安装时静默回退执行其他已装版本，应 exit 3 | `bin/dataagent:61-65`（r5 行号） |
| D14 | P1 | doctor 缺策略仍 exit 0（策略检查不更新最终 status），后续 `--authorize` 才 exit 3 | `bin/dataagent:151-170`（r5 行号） |
| D15 | P1 | 合法 proposal-only 输入被判 `no input given`（输入判定漏算 `--proposal-file`） | `unified.py:142-143`（r5 行号） |
| D5 | P2 | 32 KiB 摘要兜底只限句柄数量、不复检编码大小：合法长 criteria ID 的单条 40,012 B 句柄产生 40,431 B stdout | `unified.py:657-666`（r5 行号） |

改动前快照：`/tmp/agentos-snapshots/pre-r6-20261106-043147.tar.gz`；改动后 `dataagent-runtime@sha256:4c55f3057bd9dc22b399ebab400f3791848f21bb1e9ee1830981cc35205faef0`（67 文件）。

## D12 fixed（P1 → 关闭）

**方案**：`_pick_chain_candidate`（`unified.py:360-378`）接收句柄字符串，填充偏好序变为：

1. 候选链（匹配节点→各级容器）中第一个通过 `field_type.model_validate` 的对象——对象模型字段（如 `FileRef`）仍取整包装对象；
2. 句柄字符串本身——`VersionedRef` 等接受字符串形的身份字段无论存储对象多富都能填（与 `--set` 同一值域）；
3. 两者皆不匹配 → `UsageError`（exit 2，`does not fit field type 'FileRef'`），**不再静默返回不兼容对象**。

`_resolve_handle` 返回值相应放宽为 `Any`（对象或字符串形）。

**黑盒复现（review 原例）**：

```sh
# 表句柄来自 CSV 解析（富 TableRef），进 VersionedRef 字段：
$ dataagent-data … run parse_delimited_file --file sales.csv --set delimiter=,   # exit 0，handles=[table:324d9e0c…@sha256:…]
$ dataagent-governance … policy apply policy.json                                # "tenant:default@r1"
$ dataagent-governance … run check_access_scope --ref resource_ref=<表句柄>      # r5: exit 2 extra_forbidden → r6: exit 0
#   data.decision.resource_ref 与句柄逐字相等，decision=allow；--set 同句柄结果一致
$ dataagent-governance … run evaluate_business_acceptance --ref criteria_ref=criteria:…@r1
#   r6: payload 收到 'criteria:…@r1' 字符串形（其余必填缺失才报 schema error，与 D12 无关）
```

**回归测试**（runtime +3）：`test_ref_rich_handle_fills_versioned_ref_field`（富句柄→VersionedRef 字符串形）、`test_ref_incompatible_handle_is_usage_not_schema_error`（不兼容句柄→exit 2 而非静默不兼容值）、`test_ref_rich_handle_still_fills_object_field`（对象模型字段仍取整对象）。

## D13 fixed（P1 → 关闭）

`resolve_dir`（`bin/dataagent:56-71`）：mint.lock 有 pin 但该版本未安装 → `die` exit 3（`mint.lock pins dataagent/<pkg>@<ver> but that version is not installed`），**不再回退最高已装版本**；无 pin 时仍取最高已装（§5.1 语义不变）。`doctor_cmd` 同步：报告 `MISSING pinned <ver>` 并计入最终 status（`bin/dataagent:133-141`）。

**黑盒**（`/tmp/r6-mint`，真实三层 venv 软链）：锁 0.2.0、仅装 0.1.0 → `dataagent data list` **exit 3**、stdout 空（未执行任何层进程）；`doctor` **exit 3** 且 `MISSING pinned 0.2.0`；移除锁 → dispatch exit 0（无锁回退语义保持）。

**回归测试**（cli +2）：`test_pinned_version_missing_exits_3`（含「层进程未运行」断言）、`test_doctor_pinned_version_missing_exits_3`。

## D14 fixed（P1 → 关闭）

`doctor_cmd` 策略探针（`bin/dataagent:172-201`）改为退出码协议：内嵌 python `import` 失败 exit 2、`policy.load` 失败 exit 1、成功 exit 0；shell 侧 `none` 与 `check failed` 均 `status=3`，计入最终退出码。

**黑盒**（真实三层 venv、fresh data_root、`DATAAGENT_ENFORCEMENT_MODE=enforce`）：无策略 → `policy:   none (run: dataagent gov policy apply <policy.json>)` + **exit 3**（r5 为 exit 0）；`gov policy apply` 后 → `policy:   configured` + **exit 0**。

**回归测试**（cli +1，另有既有 1 项改造）：`test_doctor_missing_policy_exits_3`；`test_doctor_all_layers_present_exits_0` 改为显式「策略已配置」前提（fake 探针加 `DATAAGENT_FAKE_POLICY` 标记）。`FAKE_PYTHON` 相应支持 `-c` 探针协议。

## D15 fixed（P1 → 关闭）

`_parse_params`（`unified.py:142-155`）：无输入判定加入 `proposal_file`，usage 文案同步列出 `--proposal-file`。

**黑盒**：`gov run draft_acceptance_criteria --proposal-file proposal.json`（单独）→ **exit 0**（`criteria:875c094e4e25@r1` 草稿铸出；r5 为 exit 2 `no input given`）；stage1（`--set delivery_target=…`）仍 `needs_input`。

**回归测试**（runtime +1）：`test_proposal_file_alone_is_valid_input`（`TwoPhaseInput.value` 放宽为可选，使 proposal-only 路径可达）。

## D5 re-fixed（P2 → 关闭，r2 修复不完整的补全）

`_fit_summary`（`unified.py:660-715`）兜底阶段：逐句柄裁剪（>200 字符走 `_clip_value` 同一规则）后**循环复检编码大小**，仍超限则从尾部逐个丢弃句柄，最终回落到最小记录标识（status + invocation_id + 单条 summary_clipped + 截断的 result_path）——返回值**保证** ≤ 32 KiB。

**黑盒**（review 原例：合法长 criteria ID）：`gov run draft_acceptance_criteria --proposal-file proposal.json --set existing_criteria_id=<40,000 字符>` → exit 0、**stdout 634 B**（r5 为 40,431 B）、句柄裁剪为 239 字符、`result_path` 内完整 40,009 字符 id 保留。

**回归测试**（runtime +1）：`test_summary_single_oversized_handle_clipped`。

## 其余缺陷（与前几轮处置一致，非本轮闸门）

- **D2 partial**：CC>10 26.56% → **28.24%**（新增 `_pick_chain_candidate`/`_fit_summary` 分支；CC>25 仍 0.0% 达标，A5.2 保持 1）。存量组合复杂度留待后续轮。
- **D3 open**：默认超时/在途取消仍属方案范围外（W1 无该项），保持 open。
- D1/D4/D6–D11 全部保持关闭（本轮逐项复跑复证，见 r6-runtime.score.json defects.fix_evidence；D9 复跑需 `DATAAGENT_CONFIRMERS`，与 review 环境一致）。

## 分发同步

四包 vendored `unified.py`（runtime/data/application/governance 的 `packaging/bundle`）`cmp` 逐字节一致；runtime `test_bundle_sync` 通过（111 passed 内含）。

## 复跑命令与结果

```sh
cd /Users/payne/Vibe/AgentOS
(cd packages/capabilities/dataagent-runtime && .venv/bin/python -m pytest -p no:warnings -o addopts="")      # 111 passed（+5）
(cd packages/capabilities/dataagent-data && .venv/bin/python -m pytest -p no:warnings -o addopts="")         # 654 passed
(cd packages/capabilities/dataagent-application && .venv/bin/python -m pytest -p no:warnings -o addopts="")   # 203 passed
(cd packages/capabilities/dataagent-governance && .venv/bin/python -m pytest -p no:warnings -o addopts="")    # 123 passed
(cd packages/capabilities/dataagent-cli && python3 -m unittest discover -s tests)                            # 15 OK（+3）
python3 skills/code-landing-quality/scripts/snapshot.py packages/capabilities/dataagent-runtime
# sha256:4c55f3057bd9dc22b399ebab400f3791848f21bb1e9ee1830981cc35205faef0  67 files
python3 skills/code-landing-quality/scripts/quality_run.py --repo . \
  --package packages/capabilities/dataagent-runtime \
  --fill docs/research/dataagent-2026-11-03/12-cli-build/r6-runtime.score.json \
  --out    docs/research/dataagent-2026-11-03/12-cli-build/r6-runtime.quality.md
#   111 passed；重复率 2.13%（53/2486）；裸 except 0 / 吞错 0；CC>10 28.24% / CC>25 0.0%；bundle 一致
python3 skills/code-landing-quality/scripts/score_landing.py \
  --result docs/research/dataagent-2026-11-03/12-cli-build/r6-runtime.score.json   # 93.1 / A，无闸门
python3 skills/code-landing-quality/scripts/round_diff.py \
  docs/research/dataagent-2026-11-03/12-cli-build/r5-runtime.score.json \
  docs/research/dataagent-2026-11-03/12-cli-build/r6-runtime.score.json --fail-on-regression  # rc=0，无退化
```

自评 **93.1 / 100（A，可验收，无闸门）**（[r6.score.txt](r6.score.txt)、[r6-runtime.score.json](r6-runtime.score.json)）。R13 维持 green（r6 相对基线 tag 的改动均为缺陷修复型增量，旧 wire 由 `dataagent-data/tests/test_interfaces.py` 654 passed 锁定）；r5-review §6 建议清理的 R13 evidence 过期表述（「0.1.0 从未发布」）已同步更正。
