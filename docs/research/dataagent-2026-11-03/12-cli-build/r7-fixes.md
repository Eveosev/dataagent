# r7 修复记录：r6-review 两项阻断（D16、D5 残余）处置

## 背景

r6 独立验收（[r6-review.md](r6-review.md)）判不可验收（79.0 / C，GATE-P1 + GATE-CHECKLIST）：D12–D15 已修复，但发现 **D16 新增 P1**（无 pin 回退回归）与 **D5 残余**（恰 32,768 B JSON + print 换行 → stdout 32,769 B）。本轮（r7）修复两项并按 handoff 补齐「真实 stdout 精确字节边界」回归后重新送审。自评 **93.1 / 100（A，可验收，无闸门）**（[r7.score.txt](r7.score.txt)）。

| ID | 级 | 问题 | 位置（r6 行号） |
|-|-|-|-|
| D16 | P1 | mint.lock 存在但无该层 pin 时，已安装层被误拒：`data list` exit 3，同目录 doctor 却 exit 0（doctor/dispatch 解析不一致；r6 引入的回归，pre-r6 为 exit 0 / 32 行） | `bin/dataagent:51-71` |
| D5 | P2 | 摘要上限未计入 `print` 追加的换行：合法输入产生恰 32,768 B JSON 时 stdout 达 32,769 B | `unified.py:674-678`、`:776` |

改动前快照：`/tmp/agentos-snapshots/pre-r7-20261106-050234.tar.gz`；改动后 `dataagent-runtime@sha256:8a7692b415f87eed92aa13c5afed968cf6a916f72d46e94a966c304f24e8ac66`（67 文件）。

## D16 fixed（P1 → 关闭）

**根因**：r6 为 D13 修复在 `resolve_dir` 加入 `[ -n "$ver" ] || die "… without a readable version"`，但 `pinned_version` 对「mint.lock 存在、无该层条目」也返回成功（空串），于是无 pin 的已装层被误判为「锁了但不可读」→ exit 3。

**方案**（`bin/dataagent:47-73`）：

- `pinned_version` 改为「无锁 / 无该层条目 / 版本不可读 → `return 1`」（空输出即非 pin），只在该层确有可读 pin 时输出版本；
- `resolve_dir` 消费序：pin 已装 → pin 目录；**无 pin → 最高已装版本**（r6 die 移除）；pin 未装 → `die` exit 3（D13 语义不变）；
- `doctor_cmd`（`:138-150`）同步为同一消费序（原 `[ -n "$ver" ]` 双保险分支随 `pinned_version` 收紧语义一并简化），governance 策略探针目录解析（`:175-178`）同改。

**黑盒复现（review 原例，`/tmp/r7-mint` 真实三层 venv 软链）**：

```sh
printf '…name = "dataagent/governance-layer"\nversion = "0.1.0"…' > mint.lock   # 仅 pin governance
$ r6bin data list   # exit 3  "mint.lock pins dataagent/data-layer without a readable version"
$ dataagent data list   # r7: exit 0，stdout 32 行（与 pre-r6 / doctor 一致）
$ dataagent gov policy apply policy.json && dataagent doctor   # exit 0，报 data-layer@0.1.0，configured
# D13 语义保持：锁 data-layer 0.2.0 且未装 → dispatch / doctor 均 exit 3（MISSING pinned 0.2.0）
```

**回归测试**（cli +2，12→17 全 OK）：`test_lock_without_layer_pin_falls_back`（无该层 pin → dispatch exit 0 且层进程实跑 + doctor 同解析同绿）、`test_lock_unreadable_pin_falls_back`（无 version 行的条目同样回退不 die）；既有 `test_pinned_version_missing_exits_3` / `test_doctor_pinned_version_missing_exits_3` 锁定 D13 语义，均通过。

## D5 re-fixed（P2 → 关闭，r6 修复不完整的收口）

**根因**：`_fit_summary.fits` 只检查 `len(json) ≤ SUMMARY_LIMIT`，而 `_emit` 用 `print(json.dumps(...))` 输出，追加 1 字节换行——JSON 恰 32,768 B 时 stdout 为 32,769 B。

**方案**（`unified.py:677-681`）：`fits()` 计入换行（`encoded + 1 ≤ SUMMARY_LIMIT`），上限语义明确为「整条 stdout 行（JSON + `\n`）≤ 32 KiB」，docstring 同步记录 r6-review D5；`data` 截断标记的 `"reason": "summary exceeds 32 KiB"` 含义不变。

**黑盒（真实子进程管道实测，`/tmp/r7-d5/driver.py`，同一 `data_root` 消除 result_path 长度差）**：

```sh
# 先以 256 B blob 校准固定开销，再取恰 32,768 B JSON 的 blob 长度 32587：
$ r6代码 driver.py 32587 | wc -c   # 32769  ← review 原例
$ r7代码 driver.py 32587 | wc -c   #   241  （data.truncated=true，边界真实命中）
$ r7代码 driver.py 32586 | wc -c   # 32768  （少 1 字节：不截断，JSON+\n 恰用满预算）
```

（r6 代码取自 `git show b12887f:…/unified.py`，PYTHONPATH 注入同 venv。）

**回归测试**（runtime +1，111→112 全通过）：`test_summary_boundary_counts_newline`——测试内校准（invocation_id / result_path 定长、JSON 随 blob 每字符 +1 B）后断言：恰 32,768 B JSON 输入 stdout ≤ 32,768 且 `data.truncated` 为真（边界真实命中，不会因远离边界而平凡通过）；少 1 字节输入不截断且 `len(stdout) == SUMMARY_LIMIT`（精确字节边界，含换行）。

## 分发同步

源 `src/dataagent_runtime/interfaces/unified.py` → 四份 vendored 副本（runtime/data/application/governance `packaging/bundle/src/…`）`cmp` 逐字节一致；`test_bundle_sync` 各层套件通过。

## 复跑命令与结果

```sh
cd /Users/payne/Vibe/AgentOS
(cd packages/capabilities/dataagent-runtime && .venv/bin/python -m pytest -p no:warnings -o addopts="")       # 112 passed
(cd packages/capabilities/dataagent-data && .venv/bin/python -m pytest -p no:warnings -o addopts="")         # 654 passed
(cd packages/capabilities/dataagent-application && .venv/bin/python -m pytest -p no:warnings -o addopts="")  # 203 passed
(cd packages/capabilities/dataagent-governance && .venv/bin/python -m pytest -p no:warnings -o addopts="")   # 123 passed
(cd packages/capabilities/dataagent-cli && python3 -m unittest discover -s tests)                           # 17 tests OK
python3 skills/code-landing-quality/scripts/snapshot.py packages/capabilities/dataagent-runtime
# sha256:8a7692b415f87eed92aa13c5afed968cf6a916f72d46e94a966c304f24e8ac66  67 files
python3 skills/code-landing-quality/scripts/quality_run.py --repo . --package packages/capabilities/dataagent-runtime \
    --fill docs/research/dataagent-2026-11-03/12-cli-build/r7-runtime.score.json \
    --out docs/research/dataagent-2026-11-03/12-cli-build/r7-runtime.quality.md
python3 skills/code-landing-quality/scripts/score_landing.py --result …/r7-runtime.score.json   # 93.1 / A / 无闸门
python3 skills/code-landing-quality/scripts/round_diff.py …/r6-runtime.score.json …/r7-runtime.score.json
# 新缺陷 1（D16，本轮已 fixed）；未修复 1（D3）、部分修复 1（D2），其余 13 条保持关闭；无回归、无未复核
```

机器测量（[r7-runtime.quality.md](r7-runtime.quality.md)）：重复率 **2.13%**（53/2489）、裸 except 0 / 吞错 0、CC>10 **28.32%**、CC>25 **0.0%**、bundle 一致。

## 其余缺陷（按既定处置，非本轮闸门）

- **D2 partial**：CC>10 28.24% → **28.32%**（r7 新增 fits 换行计数与 pinned_version 回退分支的小幅增量）；CC>25 仍 0.0%，A5.2 保持 1。
- **D3 open**：默认超时 / 在途取消仍属方案范围外（W1 无该项），保持 open。
- D1、D4、D6–D15 共 13 条保持关闭（本轮套件 + 黑盒逐项复跑复证，见 r7-runtime.score.json defects.fix_evidence）。
