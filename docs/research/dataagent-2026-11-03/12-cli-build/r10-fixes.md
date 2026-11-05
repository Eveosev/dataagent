# r10 修复记录：r9-review D16 残余（等价 TOML pin 解析 + quoted-header missing-pin fail-open）处置

## 背景

r9 独立验收（[r9-review.md](r9-review.md)）判不可验收（79.0 / C，GATE-P1 D16 + GATE-CHECKLIST `#b9b374`），handoff：修复 D16 quoted/escaped 表头与键、多行/inline package 等价表示的 pin 解析和 missing-pin fail-open；补真实 Mint differential 回归后重新送审。

| 问题（均为 r9-review 实测，真实 Mint 0.1.26 与 tomllib 均接受） | r9 表现 | 位置 |
|-|-|-|
| `[["package"]]`、`[['package']]`、`[["pack\u0061ge"]]` 等引号/转义表头 pin 0.1.0 | 双双 exit 0、**exec 0.2.0，忽略 pin** | [bin/dataagent:183-205](../../packages/capabilities/dataagent-cli/bin/dataagent#L183-L205)（r9 版） |
| `"\u006eame"` 转义键 | 同上，绕过 | 同上 |
| `"vers\u0069on"` 转义 version 键 | 双双 exit 3，**误拒已装合法 pin** | 同上 |
| 多行 basic/literal name/version、`\` 续行 | 双双 exit 3，误拒 | [bin/dataagent:113-163](../../packages/capabilities/dataagent-cli/bin/dataagent#L113-L163)（r9 版） |
| `package = [{name=…, version=…}]` inline 数组 | 双双 exit 0、exec 0.2.0，绕过 | 同上 |
| **回归**：quoted 表头锁定未装 0.9.9 | r8 exit 3 未执行 → **r9 exit 0 exec 0.2.0**（fail-open） | [dispatch 回退](../../packages/capabilities/dataagent-cli/bin/dataagent#L231-L244)（r9 版） |

根因（一层）：r8/r9 的解析器是**逐行**的——表头去空白后与字面串精确比较、键按首个 `=` 切片剥引号、值扫描只看一行。每修一个格式变体就留下其它合法 TOML 等价类静默降级为「无 pin」。

本轮（r10）自评 **93.1 / 100（A，可验收，无闸门）**（[r10.score.txt](r10.score.txt)）。改动前快照：`/tmp/agentos-snapshots/pre-r10-20261106-062524.tar.gz`；改动后 `dataagent-runtime@sha256:8a7692b4…`（67 文件，**runtime 源零改动**）+ `dataagent-cli@sha256:03c900e7…`（6 文件）。全部产品改动在 `packages/capabilities/dataagent-cli/bin/dataagent` 的 `pinned_version`（三态出口 0/1/2、`pin_status` 捕获、D13 pin-未装 exit 3、无 pin 回退语义逐字保留）。

## D16 fixed：字符级 TOML 扫描器

**方案**（[bin/dataagent:47-556](../../packages/capabilities/dataagent-cli/bin/dataagent#L47-L556)，仍为 POSIX sh + 单进程 awk、无 Python 依赖、`LC_ALL=C` 保证两种 awk 下 `sprintf("%c")` 按字节）：不再按行猜测，而是把 mint.lock 整体读入后**单遍字符级扫描**，镜像 stdlib tomllib 文法回答唯一的问题——「顶层 `package` 条目里 name/version 是什么」：

- **表头与键是解码点路径**：`[ "package" ]`、`[["package"]]`、`[['package']]`、`[["pack\u0061ge"]]` 与 `[[package]]` 寻址同一顶层表；`"\u006eame" = …` 是 `name` 键；点路径子表（`[[package.requires]]`、`[core]`、`[package.artifacts.any]`）是别的表，其 name/version 永不构成 pin（r8 语义保留）。
- **值是完整 TOML 值**：basic/literal、单行与多行 `"""…"""`/`'''…'''`（前导换行裁剪、闭引号贪心 +2、`\` 续行连同首尾空白一并裁剪）、inline table 与数组（可跨行、可含注释）、数字/布尔/日期时间不透明 token（含 `1979-05-27 07:32:00` 空格形式）；name/version 非字符串 → 不可读。
- **根级 `package = [{…}]` 与 `[[package]]` 是同一数组**（tomllib 语义），条目逐个按 `[[package]]` 条目同样的 name/version 捕获与 flush 规则处理；inline 元素的嵌套表/数组不贡献 pin。
- **tomllib 重复键/覆写规则**：键路径注册表（`reg[]`，SUBSEP 连接）复刻——同路径二次赋值、标量下钻、表头声明已定义键、`[[t]]` 新元素作用域清理（`clear_sub`）均 → exit 2；inline table 每实例独立作用域。
- **fail-closed 扩围**：任何不可解析的锁（tomllib 拒绝的输入）、条目 name 非字符串（无法排除是本包）、匹配条目 version 不可读/为空、非容器 `package` 值、`package` 二次定义 → exit 2 → dispatch exit 3 / doctor `LOCK unreadable`。**没有「未支持但合法」这个状态**——等价形按语义读出，读不出的拒绝，绝不静默回退最高已装。

已知方向性偏差（仅非法输入，记录在案）：本机 tomllib（3.15）接受而 Mint/tomllib 1.0 拒绝的 TOML 1.1 形（如 `\e`/`\xHH` 转义、inline table 内换行）按 tomllib 处理；字符串内裸控制字符等少数非法形解析器比 tomllib 宽松（读出的 pin 只会等于或严于「无 pin」，不会绕过锁定版本）。

## 黑盒（证据 [r10-fix-evidence/](/Users/payne/.dsh/state/agent-teamwork/team/r10-fix-evidence/)）

1. **r9-review 原探针原样复跑**（`lock_probe.py`，仅证据目录改写，期望由 tomllib 独立推导，真实三层 venv wrapper 记录实际 exec 目录）：**24/24 PASS**（[lock-results.json](/Users/payne/.dsh/state/agent-teamwork/team/r10-fix-evidence/lock-results.json)）——standard/compact/indented/literal/引号键/转义 name/转义 version/requires 边（前置/仅边/后置）/行尾残留/空锁全部保持 r9 已过语义。

2. **r9-review 补充等价矩阵原样复跑**（`lock_edges.py`，每例先 tomllib 确认 + 真实 `mint list --offline --json` 复核 pin 0.1.0）：**24/24 PASS**（[lock-edges-results.json](/Users/payne/.dsh/state/agent-teamwork/team/r10-fix-evidence/lock-edges-results.json)）——quoted/literal/escaped 表头、escaped name/version 键、单行 triple、多行 name/version/literal、`\` 续行、inline package 数组（单行/跨行）dispatch+doctor 均 **exit 0 exec 0.1.0**（r9 为 exec 0.2.0 绕过 / exit 3 误拒）；Mint 报告与执行版本逐例一致。

3. **r8/r9/r10 同输入 missing-pin 对照**（`lock_controls.py`，7 种写法 × 3 个 bin × dispatch/doctor = 42 组合，[lock-control-results.json](/Users/payne/.dsh/state/agent-teamwork/team/r10-fix-evidence/lock-control-results.json)）：**r10 全部 exit 3、未执行**，doctor 报 `MISSING pinned 0.9.9`；42 组合中 14 个失败**全部归属 r8/r9 bin**（quoted/literal/escaped 表头、escaped 键、多行 version、inline 数组在 r9 为 exit 0 exec 0.2.0）——r9-review 的 fail-open 回归收口，D13 语义在全部等价形上恢复。

4. **tomllib 随机差分**（`lock_fuzz.py`，种子固定 20261106）：随机生成 1500 个合法锁（表头/键/值在上述全部等价类中随机组合，含 [core]/requires/inline 混排），期望由 tomllib 独立推导，**0 失败**（[lock-fuzz-results.json](/Users/payne/.dsh/state/agent-teamwork/team/r10-fix-evidence/lock-fuzz-results.json)）；`lock_fuzz_invalid.py` 另扫 600 个生成锁，凡 tomllib 拒绝者 dispatcher **全部 exit 3、未执行**（0 失败，[lock-fuzz-invalid-results.json](/Users/payne/.dsh/state/agent-teamwork/team/r10-fix-evidence/lock-fuzz-invalid-results.json)）。

5. **真实 Mint 安装链回归（D17 保持）**：CLI 套件含真实 `mint init`+`mint add <preset path> --offline -y` 安装 5 包与 `mint lock --dry-run` exit 0（test_manifest.py，未 skip）。

## 回归测试（cli 36→58 全 OK）

[test_dispatcher.py](../../packages/capabilities/dataagent-cli/tests/test_dispatcher.py) 新增 22 项：

- **DispatcherTests +18**：quoted/literal/escaped/spaced 表头、escaped name/version 键、单行 triple、多行 name/version/literal、`\` 续行、inline 数组（单行/跨行）各 1 项 `_pin_matrix`（dispatch+doctor 双断言）；`quoted_header_missing`/`inline_package_array_missing`/`escaped_header_missing` 三项 D13 回归（pin 0.9.9 未装 → exit 3 + doctor `MISSING pinned`）；`duplicate_key_lock_fails_closed`（tomllib 拒绝 → exit 3）；`real_mint_lock_escaped_and_inline`（真实锁形态 + 等价形混排）。
- **LockDifferentialTests +3**（tomllib 差分，stdlib 参考与 review 同源）：21 个合法等价变体 exec 版本 == tomllib 推导 pin；6 个 missing-pin 变体 exit 3；5 个非法锁（tomllib 拒绝，先断言）exit 3。
- **RealMintLockDifferentialTests +1**（真实 Mint 差分）：6 个代表性变体先 `mint list --offline --json` 取实际 pin，断言与 dispatcher 实际 exec 版本相等（mint 不可用时 skip）。

既有 36 项全部保持通过（含 D13 两条、无 pin 回退、不可读 fail-closed、D14 doctor、env scrub、link）。

## 其余缺陷（按既定处置，非本轮闸门）

D2 partial（CC>10 28.32%，runtime 源本轮零改动）、D3 open（默认 deadline/在途取消），留待后续轮；D17/D5/D13/D14 等既有 fixed 项经五套回归与上述探针保持。

## 复跑命令与结果

```sh
cd /Users/payne/Vibe/AgentOS
(cd packages/capabilities/dataagent-runtime && .venv/bin/python -m pytest -p no:warnings -o addopts="")       # 112 passed
(cd packages/capabilities/dataagent-data && .venv/bin/python -m pytest -p no:warnings -o addopts="")          # 654 passed
(cd packages/capabilities/dataagent-application && .venv/bin/python -m pytest -p no:warnings -o addopts="")   # 203 passed
(cd packages/capabilities/dataagent-governance && .venv/bin/python -m pytest -p no:warnings -o addopts="")   # 123 passed
(cd packages/capabilities/dataagent-cli && python3 -m unittest discover -s tests)                             # 58 tests OK
E=/Users/payne/.dsh/state/agent-teamwork/team/r10-fix-evidence
python3 $E/lock_probe.py          # r9-review 原矩阵 24/24 PASS
python3 $E/lock_edges.py         # 等价矩阵（Mint+tomllib 双参考）24/24 PASS
python3 $E/lock_controls.py      # r8/r9/r10 missing-pin 对照：r10 0 失败（14 失败全属 r8/r9）
python3 $E/lock_fuzz.py 1500     # tomllib 随机差分：0 失败
python3 $E/lock_fuzz_invalid.py  # tomllib 拒绝者全部 fail-closed：0 失败
python3 skills/code-landing-quality/scripts/quality_run.py --repo . \
  --package packages/capabilities/dataagent-runtime \
  --fill docs/research/dataagent-2026-11-03/12-cli-build/r10-runtime.score.json \
  --out docs/research/dataagent-2026-11-03/12-cli-build/r10-runtime.quality.md
python3 skills/code-landing-quality/scripts/score_landing.py --result docs/research/dataagent-2026-11-03/12-cli-build/r10-runtime.score.json   # 93.1 / A / 无闸门
python3 skills/code-landing-quality/scripts/round_diff.py \
  docs/research/dataagent-2026-11-03/12-cli-build/r9-runtime.score.json \
  docs/research/dataagent-2026-11-03/12-cli-build/r10-runtime.score.json --fail-on-regression   # rc=0
```

质量：重复率 2.13%（53/2489）、CC>10 28.32%（D2 partial 维持）、CC>25 0.0%、runtime 112 passed（独立 venv）；`uv lock --check` rc=0、`uv build` rc=0、`sh -n bin/dataagent` rc=0、四份 vendored `unified.py` `cmp` 逐字节一致。

## 变更文件

产品：`packages/capabilities/dataagent-cli/bin/dataagent`（`pinned_version` 重写：47-556）；测试：`packages/capabilities/dataagent-cli/tests/test_dispatcher.py`（36→58）；记录：`12-cli-build/r10-fixes.md`、`r10-runtime.score.json`、`r10-runtime.quality.md`、`r10.score.txt`、README r10 行、build-plan r10 行；证据：`team/r10-fix-evidence/`（探针脚本 + 结果 JSON + r8/r9 bin 存档）。
