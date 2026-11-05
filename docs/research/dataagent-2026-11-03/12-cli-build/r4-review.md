---
round: r4
date: 2026-11-06
subject: dataagent-runtime 第 4 轮验收（R13 基线建立）
plan: docs/research/dataagent-2026-11-03/12-unified-cli-build-plan.md r1
rubric: 2.1 sha256:5e65f6c6006a
snapshot:
  dataagent-runtime: sha256:78c93a64776a5dbc4ad45fd9c3f9f849d5d105b300f08179445fcaa2f9e1f400
facts_ref: agent-kernel@698ac1b2e89a8199c69f415d090d03167d24818e
verdict: 不可验收
score: 79.0（C）
---

# 第 4 轮验收：dataagent-runtime（R13 基线建立）

## 0. 结论

**不可验收。** R13 的基线本身可核（tag ref → commit `fbe24d8`，tag 内 runtime 与 r3 验收态逐字节一致，tag 后无产品代码变更），但本轮独立探针新发现 **P1 缺陷 D10**：`--set` 无法处理 `anyOf` / `$ref` 的标量字段（63 个字段、30 个 op，含必填的 `check_access_scope.resource_ref`），与计划 W1「`--set k=v` 按 inputSchema 转换类型」不符；清单条目 `#ceedd2` 因此判 partial。触发 **GATE-P1** 与 **GATE-CHECKLIST**，总分封顶 **79.0（C）**。另有 P2：D11（r4 证据链引用的 tag object 已失效）、D2（CC>10 占比）、D3（无默认超时）。

开发者自评的 93.1 / A / 无闸门在其自身结果文件上可复现（`score_landing.py --result r4-runtime.score.json` 输出 93.1），但该结果把 `#ceedd2` 判 done 且缺陷表无 D10；以独立探针复测后不成立。

## 1. 基线

| 项 | 实测 |
|-|-|
| 测试 | `runtime 102 passed in 0.45s`；`data tests/test_interfaces.py 16 passed`；全量 data 654 / application 203 / governance 123 / dataagent-cli 12 OK |
| 快照 | `dataagent-runtime sha256:78c93a64776a5dbc4ad45fd9c3f9f849d5d105b300f08179445fcaa2f9e1f400`（67 文件），与 r3 相同 |
| 重复率 / 复杂度 | 2.21%（53/2402；包内 20、跨包 33）/ CC>10 25.77%、CC>25 0.0% |
| bundle 漂移 | runtime 一致（test_bundle_sync 2 passed）；application 3 passed；data/governance 源与 bundle 仅差 vendored `dataagent_contracts`/`dataagent_runtime` |
| 打包 | `uv lock --check` rc=0（Resolved 13 packages）；`uv build` 成功；wheel 22 files，含 `interfaces/unified.py`，0 个 `.pyc` |

### R13 基线证据链（独立复核）

```sh
git rev-parse dataagent-runtime-0.1.0
# 20022e0a962ecd42fd575bd9b8872ca2f11c3f99（annotated tag）
git rev-parse 'dataagent-runtime-0.1.0^{commit}'
# fbe24d8f4263513a711fc96126ded588b9650f2c
git archive fbe24d8 packages/capabilities/dataagent-runtime | tar -x -C /tmp/r4-tag-verify
python3 skills/code-landing-quality/scripts/snapshot.py /tmp/r4-tag-verify/packages/capabilities/dataagent-runtime
# sha256:78c93a64776a5dbc4ad45fd9c3f9f849d5d105b300f08179445fcaa2f9e1f400  67 files（= r3 验收态 = 当前工作树）
git diff --stat fbe24d8 -- packages/capabilities        # 空
git diff --name-status fbe24d8 HEAD                     # 验收时仅 5 个 docs 路径（README/r4-fixes/r4-runtime.score.json/r4.score.txt/plan）
git fsck --no-dangling                                  # rc=0（无损坏）；git fsck --unreachable 列出旧 tag 8544568c（D11）
```

结论：基线存在、可定位、tag 后无产品代码变更；`pyproject` 与 `packaging/bundle/mint.toml` 均为 `0.1.0`，与 tag 名一致；旧 stdin 模式与 `--list` 旧 JSON 实跑可用（`--list` 32 项）。R13 判 green，但**证据须以实际 ref `20022e0a` 为准**：r4 记录引用的 `8544568c` 已是 unreachable tag（见 D11）。tag 仅在本地仓库（无 remote/制品库），该路径由 owner 2026-11-06 批准。

## 2. 方案清单

共 23 条：done 16 / partial 1 / not_done 0 / na 6 / waived 0（完成率 94.1%）。

未完成条目：

| ID | 原文（节选） | 缺口 |
|-|-|-|
| `W1共享内核实现（dataage#ceedd2` | 内核按 inputSchema 解析 argv 参数：`--input-file`、`--set k=v`（按 schema 转换类型）、`--set-json`、`--file`、`--ref`、`--proposal-file`、`--authorize` | 6 个 flag 实跑通过；`--set` 仅对 schema 属性带字面 `type` 的字段生效（`unified.py:158`），`anyOf`/`$ref` 标量被拒（D10），探针统计 63 字段/30 ops |

其余 16 条 done 均有实跑或测试证据（见结果文件 checklist 的 `evidence` 字段）。

## 3. 缺陷

| ID | 级 | 状态 | 与上轮对比 | 复现（输入 → 期望 / 实际） | 位置 |
|-|-|-|-|-|-|
| D10 | **P1** | open | 新缺陷 | `dataagent gov run check_access_scope --set resource_ref=table@*` → 期望 exit 0 mint 决策 / 实际 exit 2 `usage error: --set resource_ref: field is not a scalar; use --set-json ...`；`data --set delimiter=,`、`--set budget_rows=10` 同。`--set-json` 可用 | `packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py:158`（help 类型显示见 `:405-407`） |
| D11 | P2 | open | 新缺陷 | `git rev-parse dataagent-runtime-0.1.0` → 期望与 r4-fixes 声明的 `8544568c…` 相同 / 实际 ref=`20022e0a…`；`8544568c` 是 unreachable tag，其 message 内 digest 为 68 位畸形串；tag 于 03:42:32→03:42:38 重建，记录未同步 | `docs/research/dataagent-2026-11-03/12-cli-build/r4-fixes.md:17`；`r4-runtime.score.json` hard_rules.R13 |
| D2 | P2 | partial | 部分修复 | quality_run CC>10 LOC 占比 → 期望 ≤7.3% / 实际 25.77%（CC>25 0.0% 达标） | `packages/capabilities/dataagent-runtime/src/dataagent_runtime/enforcement.py:255` 等 |
| D3 | P2 | open | 未修复 | 无默认 deadline、在途工作不可取消 | `packages/capabilities/dataagent-runtime/src/dataagent_runtime/invoke.py` |
| D1 | P2 | fixed | 保持关闭 | quality_run 重复率 2.21%（53/2402） | `.../adapters/sqlite.py:90` 等 |
| D4 | P2 | fixed | 保持关闭 | quality_run 裸 except 0 / 吞错 0 | `.../interfaces/unified.py` 等 |
| D5 | P2 | fixed | 保持关闭 | needs_input 摘要 32 KiB 裁剪测试通过 | `.../interfaces/unified.py:593-601` |
| D6 | P2 | fixed | 保持关闭 | `bin/dataagent` 无参/未知层 → 正确 usage + exit 2 | `packages/capabilities/dataagent-cli/bin/dataagent:188-189` |
| D7 | P2 | fixed | 保持关闭 | `test_egress_scrub_applies_to_detail_full` 通过 | `.../interfaces/unified.py:623-629` |
| D8 | P2 | fixed | 保持关闭 | `run parse_delimited_file --file nope.csv` → exit 2，无 traceback | `.../interfaces/unified.py:484-490` |
| D9 | P2 | fixed | 保持关闭 | `gov confirm` 非法 confirmation → exit 2，无 traceback | `packages/capabilities/dataagent-governance/src/dataagent_governance/interfaces/cli.py:111-128` |

D10 受影响面（独立探针统计，按 schema 判型后逐字段调用 `_coerce`）：data 39 字段/15 ops、app 18 字段/11 ops、gov 6 字段/4 ops，合计 **63 字段/30 ops**；其中 7 个为必填字段（`append_task_event.task_ref`、`append_invocation_record.task_ref`、`append_user_correction.task_ref/target_ref`、`evaluate_business_acceptance.criteria_ref/evaluation_set_ref`、`check_access_scope.resource_ref`）。降级为 P2 需要：设计明确 `--set` 只覆盖字面 `type` 标量，且 `--help` 不再把 `anyOf`/`$ref` 标量渲染为可 `--set` 的 `<object>`/`<VersionedRef>`。

## 4. 分数

```text
总分: 79.0 / 100    等级: C 可演示    结论: 不可验收    证据覆盖: 100.0%
（raw 88.5，封顶 79.0）

| 闸门 | 封顶 | 触发项 |
| GATE-P1 | 79 | D10 |
| GATE-CHECKLIST | 79 | W1共享内核实现（dataage#ceedd2 |

硬规则：R01 green / R03 green / D1 green / V1 green / E1 na / R13 green / R14 green

方案清单：共 23 条，done 16 / partial 1 / not_done 0 / 未判定 0 / na 6 / waived 0；完成率 94.1%
缺陷：共 11 条；未关闭 P1 1（D10）；P2 3（D2, D3, D11）

得 0 的规则：A5.1（CC>10）、L2.1（清单未完成）、L4.2（无超时）、L6.2（本轮记录引用失效 tag object）
不适用（出分母）：A10.2、L1.1、L1.2、L1.3、L2.5、L3.5、L4.1
```

## 5. 与上一轮对比

`round_diff.py r3-runtime.score.json r4-tester-runtime.score.json`：

- 快照未变（`sha256:78c93a64776a`）：结论差异只能来自判定变化——本轮新增 D10，并把 `#ceedd2` 从 done 改为 partial。
- 缺陷：新缺陷 2（D10 P1、D11 P2）；未修复 1（D3）；部分修复 1（D2）；保持关闭 7（D1、D4–D9）。
- 规则：1→0 退化 `L2.1`（因清单 partial）与 `L6.2`（本轮记录引用失效 tag object，D11）；无其他退化。
- 方案清单：done 17/22 → 16/23；`#ceedd2` done→partial；新增 1 条（r2 记录行，na）。
- 分数：r3 89（B，GATE-UNKNOWN）→ r4 79（C，GATE-P1 + GATE-CHECKLIST）。R13 由 unknown 转 green 已证实，但被新的 P1/清单闸门取代。

## 6. 开发者声明核对

| 声明（r4-fixes.md） | 结论 | 依据 |
|-|-|-|
| 产品代码与 r3 零改动、快照 `78c93a64…` | 已证实 | `snapshot.py` 67 文件同 digest；`git diff fbe24d8 -- packages/capabilities` 空 |
| 基线 tag → commit `fbe24d8` | 已证实 | `git rev-parse 'dataagent-runtime-0.1.0^{commit}'` |
| tag object `8544568c…` | **不成立** | 实际 ref `20022e0a…`；`8544568c` 为 unreachable tag，见 D11 |
| tag 内 runtime 快照 = r3 验收态 | 已证实 | tag 树提取后 `snapshot.py` 同 digest |
| r1–r3 无破坏性变更（旧 stdin / `--list` 保留） | 已证实 | 实跑旧 stdin → ok；`--list` 32 项；`test_interfaces.py` 16 passed |
| 102 passed / 16 passed | 已证实 | 复跑输出见 §8 |
| score_landing 93.1 / A / 无闸门 | 部分成立 | 在 `r4-runtime.score.json` 上确为 93.1；但该结果 `#ceedd2`=done 且无 D10，独立探针复测后为 79.0 / C |
| D2、D3 仍为 P2 留待后续 | 已证实 | quality_run 25.77%；invoke 无 deadline |
| R13 green | 已证实（附 D11 更正） | 基线以实际 ref `20022e0a` 为准；tag 后无产品变更 |

## 7. 未测量

无（覆盖 100%）。R13 的残余局限：基线 tag 仅在本地 git 仓库，无 remote 与制品库；后续轮次须以 `git rev-parse dataagent-runtime-0.1.0`（当前 `20022e0a`）为基线复核，不能用记录中的 `8544568c`。

## 8. 复跑命令

```sh
cd /Users/payne/Vibe/AgentOS
python3 skills/code-landing-quality/scripts/snapshot.py packages/capabilities/dataagent-runtime
git rev-parse dataagent-runtime-0.1.0 'dataagent-runtime-0.1.0^{commit}'
git cat-file tag dataagent-runtime-0.1.0
git fsck --unreachable
git diff --name-status fbe24d8 HEAD

(cd packages/capabilities/dataagent-runtime && .venv/bin/python -m pytest -p no:warnings)                 # 102 passed
(cd packages/capabilities/dataagent-data && .venv/bin/python -m pytest tests/test_interfaces.py -p no:warnings)  # 16 passed
(cd packages/capabilities/dataagent-data && .venv/bin/python -m pytest -p no:warnings)                   # 654 passed
(cd packages/capabilities/dataagent-application && .venv/bin/python -m pytest -p no:warnings)            # 203 passed
(cd packages/capabilities/dataagent-governance && .venv/bin/python -m pytest -p no:warnings)             # 123 passed
(cd packages/capabilities/dataagent-cli && python3 -m unittest discover -s tests)                        # 12 OK

python3 skills/code-landing-quality/scripts/quality_run.py --repo . \
  --package packages/capabilities/dataagent-runtime \
  --fill docs/research/dataagent-2026-11-03/12-cli-build/r4-tester-runtime.score.json \
  --out docs/research/dataagent-2026-11-03/12-cli-build/r4-tester-runtime.quality.md
python3 skills/code-landing-quality/scripts/score_landing.py \
  --result docs/research/dataagent-2026-11-03/12-cli-build/r4-tester-runtime.score.json   # 79.0 / C
python3 skills/code-landing-quality/scripts/round_diff.py \
  docs/research/dataagent-2026-11-03/12-cli-build/r3-runtime.score.json \
  docs/research/dataagent-2026-11-03/12-cli-build/r4-tester-runtime.score.json

# D10 复现（DATAAGENT_DATA_ROOT 指向临时目录，DATAAGENT_HOST_SUBJECT_REF/PURPOSE 由宿主注入）
# 未安装分发器时用各层模块入口，argv 相同：
(cd packages/capabilities/dataagent-governance && .venv/bin/python -m dataagent_governance.interfaces.cli \
   run check_access_scope --set resource_ref=table@*)                  # exit 2（期望 0）
(cd packages/capabilities/dataagent-data && .venv/bin/python -m dataagent_data.interfaces.cli \
   run parse_delimited_file --file sales.csv --set delimiter=,)        # exit 2（期望 0）
# 等价可用写法：--set-json resource_ref='"table@*"' / --set-json delimiter='","'  → exit 0
```
