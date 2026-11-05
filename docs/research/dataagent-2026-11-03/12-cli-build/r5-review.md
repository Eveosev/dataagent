---
round: r5
date: 2026-11-06
subject: dataagent-runtime 第 5 轮验收（D10/D11 修复）
plan: docs/research/dataagent-2026-11-03/12-unified-cli-build-plan.md r1
rubric: 2.1 sha256:5e65f6c6006a
snapshot:
  dataagent-runtime: sha256:de2beca17c0508e8b1057f248f7faf2a9ae95ade04de16903fbb7850b3c79b1b
facts_ref: dataagent-runtime@sha256:de2beca17c0508e8b1057f248f7faf2a9ae95ade04de16903fbb7850b3c79b1b
verdict: 可验收
score: 93.1（A）
---

# 第 5 轮验收：dataagent-runtime（D10/D11 修复）

## 0. 结论

**可验收。** r4 的两个闸门均清除：P1 **D10 fixed**（`--set` 现在按 inputSchema 解析 `anyOf`/`$ref`/`$defs`，三层黑盒复现均 exit 0），清单 `#ceedd2` 因此判 **done**；P2 **D11 fixed**（r4 证据链的 tag object 已更正为实际 ref `20022e0a…`，带审计标注）。独立评分 **93.1 / 100（A）**，无闸门，与开发者自评同分（自评未抬分）。剩余 **P2**：D2 partial（CC>10 占比 26.56%）、D3 open（无默认超时/在途取消），均不封顶。

独立探针另核对：D10 不是"只修了 review 点名两例"——三层 **121 个标量字段 / 44 个 op** 全部经 `_coerce` 判型通过（其中无字面 `type`、r4 受影响面 **71 字段/33 ops**，与开发者声明一致）；残留拒绝项全部是数组/对象/`FileRef` 等模型，分工未变。

## 1. 基线

| 项 | 实测 |
|-|-|
| 测试 | runtime **106 passed**、data **654 passed**、application **203 passed**、governance **123 passed**、dataagent-cli **12 OK**（命令见 §8） |
| 快照 | `dataagent-runtime sha256:de2beca17c05…`（67 文件）；`git diff --stat fbe24d8 HEAD -- packages/capabilities` = 5 文件 +353/−36（4 份 vendored `unified.py` + 1 测试） |
| 重复率 / 吞错 | 2.17%（53/2447；包内 20、跨包 33）/ 裸 except 0 / 吞错 0 |
| 复杂度 | CC>10 LOC 占比 **26.56%**（阈 7.3%，A5.1=0）；CC>25 **0.0%**（达标） |
| bundle 漂移 | runtime 一致；data/application/governance/runtime 四份 vendored `unified.py` 与 runtime 源 **cmp 逐字节一致** |
| 打包 | `(cd packages/capabilities/dataagent-runtime && uv build -o /tmp/r5-dist)` 成功；wheel **22** files，含 `interfaces/unified.py`（29,314 B），0 `.pyc`；`uv lock --check` → Resolved 13 packages，rc=0 |
| 基线 tag | `git rev-parse dataagent-runtime-0.1.0` = **20022e0a…**（annotated）→ `^{commit}` = fbe24d8；tag 内 runtime 快照 = `78c93a64…`（67 文件，= r3 验收态）。r5 的改动在 tag 之后，属未发布增量（见 §7） |

## 2. 方案清单

共 25 条：**done 17 / partial 0 / not_done 0 / na 8 / waived 0**（完成率 100%）。

- `#ceedd2`（W1 `--set k=v` 按 schema 转换类型）由 **partial → done**：原两例复跑 exit 0，且三层判型审计覆盖 r4 的 63/30 全集；7 个必填 VersionedRef 字段可赋合法句柄（`task_ref`、`criteria_ref`、`evaluation_set_ref`、`resource_ref` 等），非法值由 `model_validate` 统一转 exit 2。
- 其余 16 条维持 done（r1–r4 已取证），本轮回归复核未发现退化；4 条元数据行 + 4 条记录行判 na。

## 3. 缺陷

| ID | 级 | 状态 | 与上轮对比 | 复现（输入 → 期望 / 实际） | 位置 |
|-|-|-|-|-|-|
| D10 | **P1** | **fixed** | open→fixed | `gov policy apply` 后 `run check_access_scope --set resource_ref=table@*` → 期望 exit 0 / **实际 exit 0**，`decision=allow`（`ad:c67a032c5d714c0f`）；`data run parse_delimited_file --file sales.csv --set delimiter=,` → exit 0，`data.delimiter=","`；`--set has_header=no` → false 生效 | `.../interfaces/unified.py:164-209`（`_resolve_kind`）、`:202-256`（`_coerce`）、`:459-466`（`_op_help`） |
| D11 | P2 | **fixed** | open→fixed | `git rev-parse dataagent-runtime-0.1.0` = `20022e0a…`；`r4-fixes.md:17` 与 `r4-runtime.score.json` R13 evidence 均已写 `20022e0a…`，并带「r5 更正（r4-review D11）」审计标注；`8544568c` 仅剩历史/审计语境 | `r4-fixes.md:17`；`r4-runtime.score.json` hard_rules.R13 |
| D2 | P2 | partial | 保持 partial | quality_run CC>10 → 期望 ≤7.3% / 实际 **26.56%**（r4 25.77%；新增 `_resolve_kind` CC=17）；CC>25 = 0.0% 达标 | `.../enforcement.py:255` 等 |
| D3 | P2 | open | 保持 open | `invoke.py:353` 仅在调用开始时拒绝已过期的 `ctx.deadline`；CLI `_build_context` 不注入默认 deadline，且无在途取消点 | `.../invoke.py:353`；`.../interfaces/unified.py:398-418` |
| D1 | P2 | fixed | 保持关闭 | quality_run 重复率 2.17%（53/2447） | `.../adapters/sqlite.py:90` 等 |
| D4 | P2 | fixed | 保持关闭 | 裸 except 0 / 吞错 0 | `.../interfaces/unified.py` 等 |
| D5 | P2 | fixed | 保持关闭 | `test_needs_input_summary_clipped_under_limit` 通过 | `.../unified.py:628-664` |
| D6 | P2 | fixed | 保持关闭 | `dataagent bogus` → 正确 usage + exit 2 | `dataagent-cli/bin/dataagent:188-189` |
| D7 | P2 | fixed | 保持关闭 | `test_egress_scrub_applies_to_detail_full` 通过 | `.../unified.py:692,708` |
| D8 | P2 | fixed | 保持关闭 | `run parse_delimited_file --file nope.csv` → exit 2，无 traceback（本轮复跑） | `.../unified.py:546-547` |
| D9 | P2 | fixed | 保持关闭 | `gov confirm` 非法 confirmation / 坏 JSON → exit 2，结构化 stderr（本轮复跑） | `governance/.../cli.py:113-123` |

D10 的独立覆盖面：三层 schema 审计（`/tmp/r5-probe/audit.py`，与产品实现独立判型）判出 **83/26（data）、28/13（app）、10/5（gov）= 121 字段/44 ops** 为标量，逐字段调用 `_coerce` **0 失败**、与产品 `_resolve_kind` **0 分歧**；其中顶部无字面 `type` 的受影响面 45/17、19/12、7/4 = **71 字段/33 ops**。负例：`action=write`（enum）→ 2 schema error、`resource_ref=not-a-ref` → 2、`budget_rows=ten` → 2、`has_header=maybe` → 2、`--set file_ref=...`（对象模型）仍拒。

## 4. 分数

```text
总分: 93.1 / 100    等级: A 可交付    结论: 可验收    证据覆盖: 100.0%

| 闸门 | 封顶 | 触发项 |
| — | — | 无 |

| 硬规则 | 依据 | 灯 |
| R01 依赖方向 | A | green |
| R03 依赖无环 | A | green |
| D1 重复率硬阈 | A | green |
| V1 版本同步 | A | green |
| E1 错误码登记 | A | na |
| R13 破坏性变更升 major | A | green |
| R14 契约对齐 | A | green |

方案清单：共 25 条，done 17 / partial 0 / not_done 0 / 未判定 0 / na 8 / waived 0；完成率 100.0%
缺陷：共 11 条；未关闭 P2 2（D2, D3）

得 0 的规则：A5.1（CC>10 26.56%）、L4.2（D3 无默认超时）
不适用：A10.2、L1.1、L1.2、L1.3、L2.5、L3.5、L4.1（profile=runtime 的 may_na）
```

R13 本轮判定：基线存在且可定位；r5 相对 tag 的改动为**增量**（`--set` 多接受一类值、help 类型渲染、4 项回归测试），旧 stdin/`--list`/`list`/help 契约保留并由 654/203/123 套件与 `test_interfaces.py` 16 项锁定，无破坏性 API 变更，故 0.1.0 无需升 major。

## 5. 与上一轮对比

`round_diff.py r4-tester-runtime.score.json r5-tester-runtime.score.json --fail-on-regression`（rc=0）：

- 分数：79（C，GATE-P1 + GATE-CHECKLIST）→ **93.1（A，无闸门）**。
- 缺陷：已修复 2（D10、D11）；未修复 1（D3）；部分修复 1（D2）；保持关闭 7（D1、D4–D9）。
- 规则：0→1 `L2.1`、`L6.2`；**无 1→0 退化**；无已判定→未测量。
- 清单：done 16/23 → **17/25**；无 done→未完成退化；新增 2 条（r4、r5 记录行，均 na）。

## 6. 开发者声明核对

| 声明（r5-fixes.md / r5-runtime.score.json） | 结论 | 依据 |
|-|-|-|
| D10 fixed：`_resolve_kind` 解析 anyOf/$ref/$defs；gov/data 两例 exit 0 | 已证实 | 黑盒复跑 exit 0 + `data.decision=allow`；`delimiter=","` |
| 三层 71 标量字段/33 ops 可 `--set`（data 45/17、app 19/12、gov 7/4） | 已证实 | 独立审计与声明逐层同数；全集 121/44 均判型通过 |
| 非法值仍 exit 2（enum/VersionedRef/int/bool） | 已证实 | 4 类负例均 2，stderr 结构化；无 traceback |
| 7 个必填 VersionedRef 字段可赋句柄 | 已证实 | `task_ref`/`criteria_ref`/`evaluation_set_ref`/`resource_ref` 等 `model_validate` 通过，`check_access_scope` 端到端 0 |
| D11 fixed：两处记录更正为 `20022e0a…` 并带审计标注 | 已证实 | grep + `git rev-parse`；`8544568c` 仅历史/审计语境 |
| 四包 vendored `unified.py` 字节同步 | 已证实 | `cmp` runtime/data/application/governance 4 份全 identical |
| 106/654/203/123/12 全绿 | 已证实 | 五套件独立复跑 |
| 自评 93.1 / A / 无闸门 | 已证实 | 独立结果文件同分、无闸门（`r5-tester.score.txt`） |
| D2 26.56%、D3 open 留待后续轮 | 已证实 | quality_run 26.56%；`invoke.py:353` 无默认 deadline/取消点 |
| 自评 R13 evidence 仍含「0.1.0 从未发布，无同版本不同制品问题」 | **部分成立** | r4 已建立「已发布基线」，该句为旧文本；R13 结论（无破坏性变更）不受影响，仅证据表述过期，未计入缺陷 |

## 7. 未测量 / 已知缺口

- 无未测量规则（覆盖 100%）。
- 非阻断缺口：
  1. **D2 partial**：CC>10 26.56% > 7.3%，A5.1=0；根因是既有 `enforcement.py`/`invoke.py` 组合复杂度，本轮新增 `_resolve_kind` CC=17。
  2. **D3 open**：无默认 deadline、在途不可取消；方案 W1 未含超时项。
  3. R13 基线 tag 仍仅本地（无 remote/制品库，owner 2026-11-06 批准的路径）；tag 内制品（r3 态）与 HEAD（r5 增量）不同，后续发布须重新评估版本号。
  4. 开发者自评 R13 evidence 的「0.1.0 从未发布」旧句未同步（见 §6），建议下轮清理。

## 8. 复跑命令

```sh
cd /Users/payne/Vibe/AgentOS
python3 skills/code-landing-quality/scripts/snapshot.py packages/capabilities/dataagent-runtime
# sha256:de2beca17c0508e8b1057f248f7faf2a9ae95ade04de16903fbb7850b3c79b1b  67 files
git rev-parse dataagent-runtime-0.1.0 'dataagent-runtime-0.1.0^{commit}'
# 20022e0a962ecd42fd575bd9b8872ca2f11c3f99 / fbe24d8f4263513a711fc96126ded588b9650f2c
git diff --stat fbe24d8 HEAD -- packages/capabilities      # 5 files, +353/-36
grep -rn "8544568c" docs/research/dataagent-2026-11-03/12-cli-build/  # 仅历史/审计语境

(cd packages/capabilities/dataagent-runtime && .venv/bin/python -m pytest -p no:warnings -o addopts="")   # 106 passed
(cd packages/capabilities/dataagent-data && .venv/bin/python -m pytest -p no:warnings -o addopts="")      # 654 passed
(cd packages/capabilities/dataagent-application && .venv/bin/python -m pytest -p no:warnings -o addopts="") # 203 passed
(cd packages/capabilities/dataagent-governance && .venv/bin/python -m pytest -p no:warnings -o addopts="")  # 123 passed
(cd packages/capabilities/dataagent-cli && python3 -m unittest discover -s tests)                         # 12 OK

python3 skills/code-landing-quality/scripts/quality_run.py --repo . \
  --package packages/capabilities/dataagent-runtime \
  --fill docs/research/dataagent-2026-11-03/12-cli-build/r5-tester-runtime.score.json \
  --out  docs/research/dataagent-2026-11-03/12-cli-build/r5-tester-runtime.quality.md
python3 skills/code-landing-quality/scripts/score_landing.py \
  --result docs/research/dataagent-2026-11-03/12-cli-build/r5-tester-runtime.score.json   # 93.1 / A
python3 skills/code-landing-quality/scripts/round_diff.py \
  docs/research/dataagent-2026-11-03/12-cli-build/r4-tester-runtime.score.json \
  docs/research/dataagent-2026-11-03/12-cli-build/r5-tester-runtime.score.json --fail-on-regression  # rc=0

(cd packages/capabilities/dataagent-runtime && uv lock --check && uv build -o /tmp/r5-dist)  # rc=0；wheel 22 files
# cmp：data/application/governance/runtime 四份 vendored unified.py 与 runtime 源一致

# CLI 黑盒（临时工作区）
WS=/tmp/r5-tester-ws; mkdir -p $WS; cd $WS
printf 'region,amount\nAPAC,10\nEMEA,20\n' > sales.csv
export DATAAGENT_WORKSPACE=$WS DATAAGENT_DATA_ROOT=$WS/.dataagent
export DATAAGENT_HOST_SUBJECT_REF=user:tester DATAAGENT_HOST_PURPOSE=verification
G=/Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-governance/.venv/bin/python
D=/Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-data/.venv/bin/python
$G -m dataagent_governance.interfaces.cli policy apply policy.json       # "tenant:default@r1", exit 0
$G -m dataagent_governance.interfaces.cli run check_access_scope --set resource_ref=table@*  # exit 0, allow
$D -m dataagent_data.interfaces.cli run parse_delimited_file --file sales.csv --set delimiter=,  # exit 0, delimiter=","
$D -m dataagent_data.interfaces.cli run parse_delimited_file --file sales.csv --set has_header=no  # exit 0
$G -m dataagent_governance.interfaces.cli run check_access_scope --set resource_ref=table@* --set action=write  # exit 2 schema error
$D -m dataagent_data.interfaces.cli run parse_delimited_file --file nope.csv   # exit 2，无 traceback（D8）
$G -m dataagent_governance.interfaces.cli confirm bad-confirm.json            # exit 2，无 traceback（D9）
$D -m dataagent_data.interfaces.cli parse_delimited_file --help | grep -c '\$defs'  # 0
```
