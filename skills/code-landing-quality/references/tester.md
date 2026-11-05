# 验收模式（Tester）

开发者按方案完成一个版本后，Tester 用本流程独立评测，产出该轮的评审记录。评分口径与开发者自检使用同一份 rubric；区别在于 Tester 要独立取证、核对上一轮缺陷，并核对开发者的声明。

## 1. 输入与产出

| 项 | 内容 |
|-|-|
| 输入 | 方案路径与 frontmatter 版本；被测包列表及各自的 profile；上一轮的 `*.score.json`（首轮没有） |
| 产出目录 | 方案同名目录，例如 `06-data-layer-build/` |
| 产出文件 | `rN-review.md`；每个包一份 `rN-<pkg>.score.json`；每个包一份 `rN-<pkg>.quality.md` |
| 登记 | 在方案文档的记录索引表和目录 `README.md` 的文件表中各加一行 |

`N` 取下一个未被占用的轮次号，先 `ls` 确认。

## 2. 独立性

- 第 9 步之前，不读开发者本轮的 `rN-fixes.md`、自评分数或总结。
- 不改源码、测试和 fixtures。探针脚本与临时数据放在 `$TMPDIR`。
- 测试全绿只能作为一条证据，不能代替探针。
- 每条判定都要能被第三方按记录复跑：写明命令或输入，不写“已验证”。

## 3. 流程

```bash
S=skills/code-landing-quality/scripts
D=docs/research/<方案目录>/<方案同名目录>
PKG=packages/capabilities/<pkg>

# 0. 仓库约定的前置同步（AgentOS：与 Mint/iface 对比前，按 AGENTS.md 检查 agent-kernel，并记录 HEAD sha）

# 1. 冻结输入
python3 $S/snapshot.py $PKG
python3 $S/score_landing.py --template > $D/rN-<pkg>.score.json      # 填 scope / profile / round / date / facts_ref

# 2. 机器测量并预填
python3 $S/quality_run.py --repo . --package $PKG --fill $D/rN-<pkg>.score.json --out $D/rN-<pkg>.quality.md

# 3. 方案清单
python3 $S/plan_checklist.py <plan.md> --into $D/rN-<pkg>.score.json
python3 $S/plan_checklist.py <plan.md> --previous <上一轮清单 JSON>   # 方案改版时查看条目增删

# 4–7. 探针、上轮缺陷复核、填规则（见下文）

# 8. 评分与轮次对比
python3 $S/score_landing.py --result $D/rN-<pkg>.score.json
python3 $S/round_diff.py $D/r(N-1)-<pkg>.score.json $D/rN-<pkg>.score.json --fail-on-regression
```

### 第 3 步：清单判定

每条清单条目填 `verdict` 和 `evidence`：

| verdict | 条件 | evidence |
|-|-|-|
| `done` | 已实现，且有探针或测试证明 | `file:line` + 复跑命令或探针 |
| `partial` | 部分实现 | 缺的部分 |
| `not_done` | 未实现 | 检索过的位置 |
| `na` | 条目不是需求（流程描述、背景、引用） | 理由 |
| `waived` | 本版本明确不做 | `waiver: {by, date, reason}` |

清单未完成时，L2.1 不得判 1。

### 第 4 步：探针

按 [probes.md](probes.md) 逐条规则执行。只要有失败的探针，就登记一条缺陷：

```json
{
  "id": "D3",
  "severity": "P0",
  "status": "open",
  "title": "decoy 聚合满足口径守卫",
  "location": "src/pkg/planning/expressions.py:1322",
  "rules": ["L2.2", "L2.3"],
  "first_seen": "r5",
  "repro": {
    "input": "SELECT region, 0 AS total, sum(amount) AS decoy …",
    "expected": "rejected: caliber_mismatch",
    "actual": "status=ok, total=0"
  }
}
```

缺陷 id 一经分配就跨轮固定。同一问题在后续轮次沿用原 id，不另编新号。

### 第 5 步：严重级

| 级 | 判定条件 | 对总分的影响 |
|-|-|-|
| P0 | 错误结果以成功状态交付、落库或外发；门禁可被调用方绕过；数据丢失或损坏；主链路不可用 | 未关闭时封顶 59；不可豁免 |
| P1 | MUST 未满足但失败可见；并发、资源或超时缺陷需特定条件才触发；合法客户端按契约调用会失败 | 未关闭时封顶 79 |
| P2 | 健壮性、可维护性、文档漂移，不影响结果正确性与安全 | 不封顶，但所关联的规则判 0 |

拿不准时按更高一级登记，并在 `title` 中写明降级需要满足的条件。

### 第 6 步：复核上一轮缺陷

- 上一轮中状态为 `open`/`partial` 的缺陷，逐条重跑原复现：通过则改为 `fixed` 并填 `fix_evidence`，未通过则保持原状态。
- 上一轮中状态为 `fixed` 的 P0/P1，全部重跑一次，用于发现回归。
- 上一轮的缺陷不得从本轮列表中删除；`round_diff.py` 会把缺失的条目标为“未复核”。

### 第 7 步：填剩余规则

- 预填的规则（`measured_by: quality_run`）不手改。对测量有异议时，在 `rN-review.md` 中说明。
- 其余规则逐条判 `1`/`0`，并附 evidence。判 0 要写明为什么不是 1；判 1 要给出复跑命令。
- 判 `na` 时：规则必须在所选 profile 的 `may_na` 内，并在 `na_reason` 中写出 `applies_when` 不成立的证据，例如“grep `httpx|requests|urllib` 0 处”。
- 未测的规则保持 `null`，并在报告中写出测量它需要什么。

### 第 9 步：核对开发者声明

评分完成后，再读开发者的 `rN-fixes.md`，逐条标注：

| 结论 | 含义 |
|-|-|
| 已证实 | 声明的修复可复现 |
| 部分成立 | 复现输入通过，但等价变形仍然失败 |
| 不成立 | 原复现仍然失败 |
| 未声明 | 本轮发现的问题不在开发者的声明中 |

## 4. 验收结论

| 条件 | 结论 |
|-|-|
| 评分无效（判定矛盾、版本不符） | 修正结果文件，不出结论 |
| 有闸门触发，或总分 <80 | 不可验收；列出按闸门影响排序的修复项 |
| 总分 ≥80 且无闸门 | 可验收；附已知缺口（P2、不适用项、C/D 级依据占比） |

旧评审中的 10 分制分数（如 7.0/10）与本 rubric 不可换算。跨轮趋势只比较同一 rubric 版本下的结果。

## 5. `rN-review.md` 模板

```markdown
---
round: rN
date: YYYY-MM-DD
subject: <包或层> 第 N 轮验收
plan: <方案文件> <frontmatter version>
rubric: <version> sha256:<12 位>
snapshot:
  <pkg>: sha256:<…>
facts_ref: agent-kernel@<sha>
verdict: 可验收 | 不可验收
score: <total>（<grade>）
---

# 第 N 轮验收：<包或层>

## 0. 结论

一句话结论；触发的闸门；未关闭的 P0/P1 数量。

## 1. 基线

| 项 | 实测 |
|-|-|
| 测试 | <passed/failed>，复跑命令 |
| 快照 | <digest> |
| 重复率 / 复杂度 | … |

## 2. 方案清单

done x / partial x / not_done x / na x / waived x；列出未完成的条目（id + 原文 + 缺口）。

## 3. 缺陷

| ID | 级 | 状态 | 与上轮对比 | 复现（输入 → 期望 / 实际） | 位置 |
|-|-|-|-|-|-|

## 4. 分数

score_landing.py 的输出：闸门表、硬规则表、维度表、得 0 与未测量的规则。

## 5. 与上一轮对比

round_diff.py 的输出：已修复 / 部分修复 / 未修复 / 回归 / 新缺陷 / 未复核。

## 6. 开发者声明核对

| 声明（rN-fixes 中的节号） | 结论 | 依据 |
|-|-|-|

## 7. 未测量

| 规则 | 测量需要的条件 |
|-|-|

## 8. 复跑命令

（第 3 节中的命令，替换为实际路径）
```
