# r9 修复记录：r8-reviewer D16/D17（真实 Mint 清单解析 + 锁解析表作用域/等价形）处置

## 背景

r8 补充评审（[r8-reviewer-supplement.md](r8-reviewer-supplement.md)）判不可验收（79.0 / C，GATE-P1 + GATE-CHECKLIST），两项 P1 阻断（[handoff](../../12-unified-cli-build-plan.md)「补齐 CLI artifacts.layout；修复锁解析的表作用域与 TOML 等价形，禁止绕过 pin；新增真实 Mint 清单解析和嵌套依赖锁回归后重新送审」）：

| ID | 问题（均为 review 实测） | 位置 |
|-|-|-|
| **D17 新增** | CLI 清单 `[artifacts]` 缺必填 `layout`，真实 Mint（本机 0.1.26）分别以 CLI、preset 为 path 依赖执行 `mint lock --dry-run --offline -y` 双双 **exit 1** `missing field \`layout\``，安装链路在清单解析阶段即阻断（Mint [Artifacts 定义](../../agent-kernel/mint/crates/mint-manifest/src/lib.rs#L599-L604) 无 serde 默认值；整个表缺省与表内字段缺省语义不同） | [mint.toml:15-16](../../packages/capabilities/dataagent-cli/mint.toml#L15-L19)、[preset mint.toml:21](../../packages/capabilities/dataagent-s0/mint.toml#L21)（preset 因 CLI 依赖连带不可解析） |
| **D16 partial** | ① `awk` 把任何 `[` 行当条目边界但不记录表作用域：`[[package.requires]]` 依赖边的 `name` 被当包 pin（该边只有 `req` 无 `version`），依赖边先于真实包条目时首匹配即「不可读」，后续真实 pin 不再读取 → dispatch/doctor **双双 exit 3**（同输入 r7 exit 0 / 32 行，回归）；② 正则只认裸 `name\|version` 键、字符串按首个引号切片：引号键 / 转义 name（`\u002f`）pin 0.1.0 被当「无 pin」→ **exit 0 执行 0.2.0（锁被绕过）**；转义 dot 的 version（`\u002e`）→ 误拒已装版本 exit 3 | [bin/dataagent:73-101](../../packages/capabilities/dataagent-cli/bin/dataagent#L73-L101)（r8 版） |

本轮（r9）按 handoff 全项修复并重新送审。自评 **93.1 / 100（A，可验收，无闸门）**（[r9.score.txt](r9.score.txt)）。改动前快照：`/tmp/agentos-snapshots/pre-r9-20261106-054939.tar.gz`；改动后 `dataagent-runtime@sha256:8a7692b415f87eed92aa13c5afed968cf6a916f72d46e94a966c304f24e8ac66`（67 文件，**runtime 源零改动**）+ `dataagent-cli@sha256:7e5277c3…`（6 文件）。全部改动在 dataagent-cli（`bin/dataagent`、`mint.toml`、`tests/`）。

## D17 fixed（P1 → 关闭）

**方案**（[mint.toml:15-19](../../packages/capabilities/dataagent-cli/mint.toml#L15-L19)）：`[artifacts]` 补 `layout = "any"`（与仓库既有约定一致——`agent-kernel/mint/packages/{a2a-adapter,tool-text,agent-history}` 等平台无关 bin 均声明 any；本包唯一制品 `bin/dataagent` 是 POSIX sh 脚本，无按 target/flavor 分发），`bin = "dataagent"` 保留。

**黑盒**（真实 Mint 0.1.26，`/Users/payne/.mint/bin/mint`；证据 [install-chain.log](/Users/payne/.dsh/state/agent-teamwork/team/r9-fix-evidence/install-chain.log)）：

| 命令（独立 mkdtemp 项目） | r8 | r9 |
|-|-|-|
| `mint init --offline -y` | exit 0 | exit 0 |
| `mint add <repo>/dataagent-s0 --offline -y`（preset → 三层 bundle + CLI 全链路） | 清单解析即 exit 1 `missing field layout` | **exit 0**，安装 `dataagent/{preset-s0,cli,data-layer,application-layer,governance-layer}@0.1.0` 共 5 包，`cli@0.1.0/bin/dataagent` 随包落盘 |
| `mint lock --dry-run --offline -y`（全部清单重解析，reviewer 的原探针命令） | exit 1（同上） | **exit 0** |

**回归**：新增 [tests/test_manifest.py](../../packages/capabilities/dataagent-cli/tests/test_manifest.py) 4 项——`test_artifacts_section_is_complete`（tomllib 断言 `layout` 必在 `any/target/flavor-target` 内）、`test_no_python_dependency_declared`、`RealMintInstallTests::test_preset_add_installs_cli_package`（真实 `mint init`+`mint add` preset path，断言 5 包全部安装且 CLI 带 bin；mint/离线 core 不可用时 skip）、`RealMintInstallTests::test_lock_dry_run_reparses_cli_manifest`（add 后 `mint lock --dry-run --offline -y` exit 0）。

## D16 fixed（P1 → 关闭）

**根因**（两层）：① 表头行只被用作「上一条目结束」的边界，没有记录当前处于哪个表——`[[package.requires]]` 下的 `name`/`req` 与 `[[package]]` 下的 `name`/`version` 无法区分；② 键匹配用裸键正则、值按「首个同引号切片」，引号键（`"name" = …`）不识别、basic 字符串的转义序列（`\\ \" \b \f \n \r \t \uXXXX \UXXXXXXXX`）不解码，`"dataagent\u002fdata-layer"` 既不等于 `dataagent/data-layer` 也不等于任何目录名。

**方案**（[bin/dataagent:82-219](../../packages/capabilities/dataagent-cli/bin/dataagent#L82-L219)，仍为 POSIX sh + awk 单进程解析，无 Python 依赖；三态出口 0/1/2 与 `pin_status` 捕获、D13 fail-closed、无 pin 回退语义全部原样保留）：

- **表作用域**：表头行去注释、去空白后精确等于 `[[package]]` 或 `[package]` 才进入 `pkg` 模式（含 `[ package ]`、行尾注释等合法空白变体）；其余任何表头（`[[package.requires]]`、`[core]`、`[core.platforms.*]`、`[package.artifacts.any]`…）进入 `other` 模式，其 `name`/`version` 键一律忽略——依赖边只可能影响自己，不再污染真实包条目，也不再把合法锁整体判「不可读」。
- **键**：不再用正则匹配裸键，改为行内取首个 `=`、两侧去空白、剥去成对引号（`"name"` / `'name'` 同 `name`）；键引号不闭合视为坏键，fail-closed。
- **值**：完整 basic/literal 字符串扫描器——单行 `"…"`/`'…'` 与 `"""…"""`/`'''…'''`；basic 串解码全部合法转义（`\uXXXX`/`\UXXXXXXXX` 按码点转 UTF-8，`\/` 等非法转义 → 不可读）；闭引号后仅允许空白或 `#` 注释（`version = "0.1.0" INVALID` 判不可读，与 tomllib 拒绝该行一致）。
- **fail-closed 扩围**：`pkg` 条目的 `name` 解析失败（无法排除「本条目即所查包」）或匹配条目的 version 不可读 → exit 2 → dispatch `die` exit 3 / doctor `LOCK unreadable`，绝不静默回退最高已装。

**黑盒**：直接复跑 **r8-reviewer 的 lock_probe.py 原脚本**（期望值由 tomllib 独立推导，真实仓库三层 venv python + wrapper 记录实际 exec 目录），[24 组合全 PASS](/Users/payne/.dsh/state/agent-teamwork/team/r9-fix-evidence/lock-results.json)：

| 输入（review 原例） | 期望 | r9 实测（dispatch / doctor） |
|-|-|-|
| standard / compact / indented / literal pin 0.1.0（双版本已装） | exec 0.1.0 | exit 0 / exec **0.1.0**（r8 已过，保持） |
| **引号键** `"name"`/`"version"` pin 0.1.0 | exec 0.1.0 | **exit 0 / exec 0.1.0**（r8 为 exec 0.2.0，绕过） |
| **转义 name** `dataagent\u002fdata-layer` pin 0.1.0 | exec 0.1.0 | **exit 0 / exec 0.1.0**（r8 为 exec 0.2.0，绕过） |
| **转义 version** `0\u002e1.0` | exec 0.1.0 | **exit 0 / exec 0.1.0**（r8 为 exit 3 误拒） |
| **`[[package.requires]]` 依赖边先于真实条目**（pin 0.1.0） | 忽略依赖边，exec 0.1.0 | **exit 0 / exec 0.1.0**（r8 为双双 exit 3；同输入 r7 为 exit 0 / 32 行，回归收口） |
| **仅依赖边提及本层**，无顶层 pin | 回退最高已装 0.2.0 | **exit 0 / exec 0.2.0**（r8 为双双 exit 3） |
| 依赖边后置于真实条目 | exec 0.1.0 | exit 0 / exec 0.1.0 |
| `version = "0.1.0" INVALID`（tomllib 拒绝） | 拒绝 | **exit 3 / 未执行**（r8 为 exit 0 执行） |
| 无 version 字段 / 空锁 / 无锁 / pin 未装 | exit 3 / 回退 / 回退 / exit 3 | 同 r8（D13 与无 pin 语义保持） |

另以 **真实 Mint 自动生成的 mint.lock**（`mint add` 产物：`v`/`resolver`/`generated_at` 头、`[core]` 表、多行 `deps` 数组、registry 包的 `[[package.requires]]` 与 `[package.artifacts.any]` 子表）直接 dispatch：exit 0、exec `data-layer@0.1.0`、doctor 同报——解析面与真实锁结构对齐。

**r8/r9 同输入对照**（[D16_pre_post_control.txt](/Users/payne/.dsh/state/agent-teamwork/team/r9-fix-evidence/D16_pre_post_control.txt)，r8 bin 取自 `git show ecf866d`）：

| 输入 | r8 | r9 |
|-|-|-|
| 引号键 pin 0.1.0 | rc=0 exec 0.2.0 | rc=0 exec **0.1.0** |
| 转义 name pin 0.1.0 | rc=0 exec 0.2.0 | rc=0 exec **0.1.0** |
| 转义 version 0.1.0 | rc=3 误拒 | rc=0 exec **0.1.0** |
| requires 先于真实条目 | rc=3 | rc=0 exec **0.1.0** |
| 仅依赖边 | rc=3 | rc=0 exec **0.2.0**（回退语义） |
| 行尾残留 `INVALID` | rc=0 执行 | **rc=3 未执行** |
| 标准 pin / pin 未装 | rc=0 exec 0.1.0 / rc=3 | 同（无回归） |

**回归测试**（cli 23→36 全 OK）：`test_dispatcher.py` 新增 9 项——`test_nested_requires_before_real_pin_uses_pin`、`test_nested_requires_only_falls_back`、`test_nested_requires_after_real_pin_uses_pin`、`test_real_mint_lock_shape_uses_pin`（真实生成锁形态）、`test_quoted_keys_pin_uses_pin`、`test_escaped_name_pin_uses_pin`、`test_escaped_version_pin_uses_pin`、`test_escaped_pin_missing_exits_3`（转义形不构成绕过：pin 0.2.0 未装仍 exit 3）、`test_trailing_garbage_version_fails_closed`；既有 23 项全部保持通过（含 D13 两条与无 pin 回退、不可读 fail-closed 四条）。

## 其余缺陷（按既定处置，非本轮闸门）

D2 partial（CC>10 28.32%，runtime 源本轮零改动）、D3 open（默认 deadline/在途取消），留待后续轮。

## 复跑命令与结果

```sh
cd /Users/payne/Vibe/AgentOS
(cd packages/capabilities/dataagent-runtime && .venv/bin/python -m pytest -p no:warnings -o addopts="")       # 112 passed
(cd packages/capabilities/dataagent-data && .venv/bin/python -m pytest -p no:warnings -o addopts="")          # 654 passed
(cd packages/capabilities/dataagent-application && .venv/bin/python -m pytest -p no:warnings -o addopts="")   # 203 passed
(cd packages/capabilities/dataagent-governance && .venv/bin/python -m pytest -p no:warnings -o addopts="")    # 123 passed
(cd packages/capabilities/dataagent-cli && python3 -m unittest discover -s tests)                             # 36 tests OK
python3 /tmp/r9-lock-probe.py                    # reviewer 24 组合 lock_probe 全 PASS（→ r9-fix-evidence/lock-results.json）
sh /tmp/r9-install-chain.sh                      # 真实 mint init+add+lock 全链路 exit 0（→ install-chain.log）
sh /tmp/r9-control.sh                            # r8/r9 同输入对照（→ D16_pre_post_control.txt）
python3 skills/code-landing-quality/scripts/snapshot.py packages/capabilities/dataagent-runtime packages/capabilities/dataagent-cli
# runtime sha256:8a7692b4…（67 文件，与 r8 相同）；cli sha256:7e5277c3…（6 文件）
python3 skills/code-landing-quality/scripts/quality_run.py --repo . --package packages/capabilities/dataagent-runtime --result docs/research/dataagent-2026-11-03/12-cli-build/r9-runtime.score.json
python3 skills/code-landing-quality/scripts/score_landing.py --result docs/research/dataagent-2026-11-03/12-cli-build/r9-runtime.score.json    # 93.1 / A / 无闸门
python3 skills/code-landing-quality/scripts/round_diff.py docs/research/dataagent-2026-11-03/12-cli-build/r8-runtime.score.json docs/research/dataagent-2026-11-03/12-cli-build/r9-runtime.score.json --fail-on-regression   # rc=0，无退化、无未复核
sh -n packages/capabilities/dataagent-cli/bin/dataagent   # rc=0
(cd packages/capabilities/dataagent-runtime && uv lock --check && uv build)   # 均 rc=0
```

`quality_run`：重复率 2.13%（53/2489 行）、CC>10 28.32%（D2 partial）、CC>25 0.0%、裸 except/吞错 0、四份 vendored `unified.py` 与 runtime 源逐字节一致（runtime 零改动，`cmp` 复核）。

## 变更文件

- 产品：`packages/capabilities/dataagent-cli/mint.toml`（+layout）、`packages/capabilities/dataagent-cli/bin/dataagent`（pinned_version 重写）
- 测试：`packages/capabilities/dataagent-cli/tests/test_dispatcher.py`（+9）、`packages/capabilities/dataagent-cli/tests/test_manifest.py`（新增 4）
- 记录：`12-cli-build/r9-fixes.md`、`r9-runtime.score.json`、`r9-runtime.quality.md`、`r9.score.txt`、README r9 行、build-plan 记录表 r9 行
