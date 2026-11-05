---
round: r1
date: 2026-11-06
subject: dataagent-runtime 统一 CLI 内核 + 三层 interfaces/cli.py 接入 + dataagent-cli 分发器 + dataagent-s0 依赖
plan: ../12-unified-cli-build-plan.md（r1，2026-11-06）
rubric: 2.1 sha256:5e65f6c6006a
snapshot:
  dataagent-runtime: sha256:9240f8ec01c356ade9b4a783ddab0f616c2bfed3e7777d93fa7d2579e3ba41af
facts_ref: dataagent-runtime@sha256:9240f8ec01c356ade9b4a783ddab0f616c2bfed3e7777d93fa7d2579e3ba41af
verdict: 不可验收
score: 59.0（E）
---

# 第 1 轮验收：统一 CLI

## 0. 结论

功能面（W1–W4）全部落地，全量测试通过；rubric 不可验收。触发 3 个闸门：**GATE-RED（D1 重复率 13.84% > 3%）**、GATE-CHECKLIST（2 项 partial：摘要 32 KiB 上限、输出前外发检查）、GATE-UNKNOWN（R13 无发布基线）。7 条未关闭 P2，无 P0/P1。

与开发者的自评（[r1.score.json](r1.score.json)，同为 59.0）相比，功能结论一致，但本评审新增 3 条缺陷（D5–D7）、把 2 条清单项改判 partial，并修正了 D2/D4 的位置与计数、D1 的归因、A7.1 的公开名数量。

## 1. 基线

| 项 | 实测 | 命令 |
|-|-|-|
| 快照 | `sha256:9240f8ec01c3…`（67 文件），与 r1.score.json 一致 | `python3 skills/code-landing-quality/scripts/snapshot.py packages/capabilities/dataagent-runtime` |
| 测试 | runtime 99 passed；data 654 passed（1 warning）；application 203 passed；governance 121 passed；cli 12 OK | 见 §8 |
| 重复率 | **13.84%**（319/2305 行；包内 20、跨包 299；171 组；同级包 5 个） | `quality_run.py --repo . --package packages/capabilities/dataagent-runtime` |
| 重复率基线 | **19.26%**（338/1755 行；跨包 328），改动前快照实测 | `tar xzf /tmp/agentos-snapshots/pre-cli-20261106-013324.tar.gz -C /tmp/baseline-cli` 后同法测量 |
| 复杂度 | CC>10 占比 **29.2%**（阈 7.3%）、CC>25 占比 **4.9%**（阈 1.1%）；基线 26.95% / 3.87% | `quality_run.py`（radon 未安装，ast 计数） |
| bundle | runtime/data/application/governance 四份 `bundle_drift` 全部 `ok`；`test_bundle_sync` runtime 2 / app 3 passed | `quality_run.bundle_drift()`；`pytest tests/test_bundle_sync.py` |
| 打包 | `uv build` 产出 `dataagent_runtime-0.1.0-py3-none-any.whl`，含 `interfaces/unified.py`，0 个 `.pyc` | `uv build -o /tmp/da-runtime-dist3` + `unzip` |
| 最长连续重复块 | 32 行（`adapters/local_content.py`，< 200 行，A1.2 成立） | 5 行窗口 + 连续游程探针 |

### D1 基线对比（重点复核）

| 文件 | 基线重复行/总行 | 本轮重复行/总行 |
|-|-|-|
| `interfaces/cli.py` | 44 / 82 | 0 / 82（数据层旧拷贝已删） |
| `interfaces/unified.py` | — | 15 / 525（新文件） |
| `interfaces/mcp_server.py` | 94 / 156 | 94 / 156 |
| `adapters/local_content.py` | 64 / 73 | 64 / 73 |
| `adapters/sqlite.py` | 48 / 148 | 48 / 173 |
| `runtime.py` | 27 / 84 | 27 / 84 |
| `ports/versioned.py` | 19 / 25 | 19 / 25 |
| 合计（含包内） | 338 / 1755 = 19.26% | 319 / 2305 = 13.84% |

- 基线 19.26% **证实**；13.84% **证实**（与开发者记录一致）。
- 5.42pp 降幅的归因：删除数据层 CLI 副本消掉 44 行重复 ≈ **-2.51pp**；新增 525 行统一内核把分母从 1755 推到 2305 ≈ **-2.91pp**。开发者“删除旧拷贝后下降 5.4pp”只对了一半（见 §6）。
- 剩余跨包 299 行主要与 `dataagent-data` 同构（`mcp_server.py` 94、`local_content.py` 64、`sqlite.py` 48 行），属既有架构性复制，非本轮新增。
- rubric v2.1 的变更记录明确“A1.1/D1 改为全量口径（包内 + 同级包），去掉无法测量的新代码口径”，因此**基线更低不改变 D1 red**，硬规则仍封顶 59。

## 2. 方案清单

共 21 条：done 15 / partial 2 / not_done 0 / na 4 / waived 0（完成率 88.2%）。

| id | 行 | 判定 | 缺口 |
|-|-|-|-|
| `W1共享内核实现（dataage#99a1de` | 13 | **partial** | 摘要 32 KiB 只在 `data` 载荷路径成立；`needs_input` 的 `inference_request` 不按字节裁剪（D5） |
| `W1共享内核实现（dataage#7cf8d0` | 15 | **partial** | 剥离只作用于摘要；`--detail full` 在剥离前输出全文（D7） |

其余 W1 条目（参数解析、`--help`、`list`、needs_input、退出码、身份只取宿主 env）、W2（三层接入、bundle 重建、`confirm`/`policy apply`）、W3（分发器、`link`/`setup`/`doctor`、SKILL.md/mint.toml、s0 依赖）、W4（内核单测、三层冒烟、快照+评分）均有复跑证据，判 done；4 条元数据行判 na。

## 3. 缺陷

| ID | 级 | 状态 | 与上一轮对比 | 复现（输入 → 期望 / 实际） | 位置 |
|-|-|-|-|-|-|
| D1 | P2 | open | 新登记（首轮） | `quality_run` 全包扫描 → 期望 ≤3%；实际 13.84%（319/2305；跨包 299）。基线 19.26% | `dataagent-runtime/src/.../adapters/sqlite.py:90` 等 171 组 |
| D2 | P2 | open | 新登记（首轮） | ast CC → 期望 CC>10 占比 ≤7.3%、CC>25 ≤1.1%；实际 29.2% / 4.9%。最高 `tabular.py:118` CC=31、`unified.py:108 _parse_params` CC=26、`enforcement.py:234` CC=25、`invoke.py:299` CC=24、`unified.py:462 _run` CC=23 | `.../interfaces/unified.py:108,462`（**不是 `_emit`，`_emit` 实测 CC=14**） |
| D3 | P2 | open | 新登记（首轮） | 长耗时 op 经 `dataagent <layer> run` → 期望非空默认超时且可取消；实际无默认 deadline，`invoke.py:353` 只拒绝已过期 deadline，不取消在途工作 | `.../interfaces/unified.py:330-354` |
| D4 | P2 | open | 新登记（首轮） | AST 吞错扫描 → 期望 0 处；实际 4 处：`gold_ledger.py:136`（`except OSError: pass`）、`sqlite.py:194`、`unified.py:272`（`OSError/JSON`）、`unified.py:287`（`ValidationError`） | 同左 |
| D5 | P2 | open | 新登记（首轮） | `r1-repro/probe_overflow2.py`：`needs_input`，`inference_request.samples=80×500B` → 期望 stdout ≤32,768 B；实际 **42,680 B**（`data` 已替换为 truncated 标记，`issues` 仍带完整内容；enforce+egress 决策时同样） | `.../interfaces/unified.py:593-601` |
| D6 | P2 | open | 新登记（首轮） | `dataagent <任意非法调用>` 的 usage → 期望 `dataagent gov policy apply <file>`；实际打印 `dataagent <layer> gov policy apply <file>`（SKILL.md 与实现均正确） | `dataagent-cli/bin/dataagent:188-189` |
| D7 | P2 | open | 新登记（首轮） | `r1-repro/probe_detail_egress.py`：enforce + `inference_request.egress_decision_ref=None` → 期望两条输出路径一致剥离；实际摘要无 `statement`/`fields`，`--detail full` 输出 `sum(secret_col)` 与 `fields` | `.../interfaces/unified.py:557-560`（对照 `:360-380`） |

D6 不影响评分（无关联规则）；若宿主把 `--detail full` 定位为“仅供宿主/人工调试”，D7 可降级为文档说明，但当前 SKILL.md 把它列为模型可用参数，且方案 W1 的“输出前做外发检查”未写例外。

## 4. 分数

`score_landing.py --result r1-runtime.score.json` 输出：

| 闸门 | 封顶 | 触发项 |
|-|-|-|
| GATE-RED | 59 | D1 |
| GATE-CHECKLIST | 79 | `#99a1de`（L13）、`#7cf8d0`（L15） |
| GATE-UNKNOWN | 89 | R13 |

| 硬规则 | 依据 | 灯 |
|-|-|-|
| R01 依赖方向 | A | green |
| R03 依赖无环 | A | green |
| D1 重复率硬阈 | A | **red** |
| V1 版本同步 | A | green |
| E1 错误码登记 | A | na |
| R13 破坏性变更升 major | A | unknown |
| R14 契约对齐 | A | green |

| 维度 | 权重 | 得分率 | 已判定 |
|-|-|-|-|
| 规模与重复率 | 6 | 33.3% | 2/2 |
| 依赖与独立性 | 6 | 100.0% | 3/3 |
| 抽象度 | 4 | 100.0% | 1/1 |
| 内聚 | 4 | 100.0% | 1/1 |
| 复杂度 | 7 | 14.3% | 3/3 |
| 功能自足 | 5 | 100.0% | 2/2 |
| 契约面（信息轴） | 0 | 0.0% | 1/1 |
| 可替换性 | 4 | 100.0% | 2/2 |
| 可装载性 | 6 | 100.0% | 3/3 |
| 错误语义 | 5 | 0.0% | 1/2 |
| 演进性 | 4 | 100.0% | 2/2 |
| 契约对齐 | 4 | 100.0% | 2/2 |
| 能力面落地 | 6 | 0.0% | 0/3 |
| 语义正确性 | 12 | 70.0% | 4/5 |
| 安全与治理 | 12 | 72.7% | 4/5 |
| 健壮性与资源 | 6 | 50.0% | 2/3 |
| 测试有效性 | 6 | 100.0% | 3/3 |
| 发布与溯源 | 3 | 100.0% | 2/2 |

- 总分 **59.0 / 100（E）**，证据覆盖 100%，依据等级 A 46.0% / B 41.4% / C 12.6%。原始分 75.9（judged weight 87），先被 GATE-RED 封顶到 59；即使不触发闸门，75.9 也低于 80 的验收线。
- 得 0：A1.1、A5.1、A5.2、A10.1、L2.1、L3.3、L4.2。
- 不适用（profile runtime 允许）：A10.2、L1.1、L1.2、L1.3、L2.5、L3.5、L4.1。

## 5. 与上一轮对比

r1 是首轮，无 r0 结果，`round_diff.py` 无输入（不适用）。与同一快照的开发者自评 [r1.score.json](r1.score.json) 对比：

| 项 | 开发者自评 | 本评审 | 说明 |
|-|-|-|-|
| 总分 | 59.0 | 59.0 | 同一快照；均被 D1 封顶 |
| 清单 | 17 done / 4 na | 15 done / 2 partial / 4 na | 新增 D5/D7 证据 |
| 缺陷 | 4 P2 | 7 P2 | 新增 D5（摘要上限）、D6（usage 文本）、D7（全文通道 egress） |
| D2 位置 | `_parse_params/_emit` | `_parse_params/_run` | `_emit` 实测 CC=14 |
| D4 计数 | 3×`ValidationError`+1 | 2×`ValidationError`+1×`OSError/JSON`+1×`pass` | AST 扫描 |
| D1 归因 | 删除旧拷贝 -5.4pp | -2.51pp 删重复、-2.91pp 分母增长 | 数字未变，归因修正 |
| 规则 | L2.1=1、L3.3=1、A7.1“约 8 名” | L2.1=0、L3.3=0、A7.1=27 名 | 见 §3/§6 |

## 6. 开发者声明核对

开发者记录（[r1-fixes.md](r1-fixes.md)）在验收前已存在；下表的每条结论都以命令复跑为准，不以记录本身为证据。

| 声明 | 结论 | 依据 |
|-|-|-|
| W1 参数解析（`--input-file/--set/--set-json/--file/--ref/--proposal-file/--authorize`） | 已证实 | `pytest tests/test_unified_cli.py` 22 passed；真实 CLI 跑 CSV、`--ref` 二次调用、`--authorize` 无决策退 3 |
| `--help` 扁平参数表、`list` 每行一 op | 已证实 | 三层实跑：data 32 行 / app 13 行 / gov 6 行；help 无 `$defs` |
| 摘要 ≤32 KiB | 部分成立 | 大数据载荷路径通过；`needs_input` 大 `inference_request` 42,680 B（D5） |
| 输出前外发检查 | 部分成立 | 摘要路径通过；`--detail full` 未剥离（D7） |
| 退出码 0/1/2/3 | 已证实 | 实跑：ok 0、failed 1、用法 2、无决策 3；data `test_interfaces.py` 断言 catalog 缺失退 3 |
| 身份只取宿主 env | 已证实 | `--input-file` 带 `context` → 2；`--set subject_ref` 非 schema 字段 → 2；`tests/test_unified_cli.py::test_input_file_cannot_smuggle_context` |
| 三层接入 + bundle 重建 | 已证实 | 四包 `bundle_drift` ok；`test_bundle_sync` runtime 2 / app 3 passed |
| `confirm <file>` / `policy apply <file>` | 已证实 | 实跑 `policy apply` → `"policy:local@r1"` 退 0，坏 JSON 退 2；gov `test_mcp_cli.py` 10 passed |
| 分发器 `link`/`setup`/`doctor` | 已证实 | `link` 生成可执行 `./dataagent`、拒绝覆盖非 launcher（2）；`doctor` 缺层退 3；`setup` 对三层执行 `uv sync --frozen`（伪 uv 记录 3 次）；`test_dispatcher.py` 12 OK |
| 全量测试数字 | 部分成立 | runtime 99、gov 121 对；app 实测 **203**（记录写 179）；data **654 passed, 1 warning** |
| D1 19.26%→13.84%，“删除旧拷贝后下降 5.4pp” | 部分成立 | 两个数字证实；5.4pp 中仅 2.51pp 来自删重复，2.91pp 来自分母增长 |
| D2 `_parse_params/_emit` 26/23 | 部分成立 | 23 属于 `_run`；`_emit` CC=14 |
| D4 “3 处 `except ValidationError: continue` + 1 处 gold_ledger” | 不成立 | 实为 2 处 `ValidationError`、1 处 `OSError/JSON`、1 处 `pass`；总数 4 对 |
| A7.1 “约 8 名” | 不成立 | `__all__` 27 名（含 `__version__`），19 个生产文件 |
| `dataagent-cli` 12 项 | 已证实 | `python3 -m unittest discover -s tests` 12 OK |

## 7. 未测量

| 规则 | 测量需要的条件 |
|-|-|
| R13 破坏性变更升 major | 已发布基线（Mint Hub 制品或 git tag）。AgentOS 非 git 仓库、dataagent-s0 未发布，本轮记 unknown（封顶 89，低于 D1 的 59，不改变结论） |

其余规则均已判定；A10.2/L1.x/L2.5/L3.5/L4.1 按 profile runtime 记 na，理由见 §4。

## 8. 复跑命令

```sh
cd /Users/payne/Vibe/AgentOS
S=skills/code-landing-quality/scripts

# 快照 + 测试
python3 $S/snapshot.py packages/capabilities/dataagent-runtime
(cd packages/capabilities/dataagent-runtime && .venv/bin/python -m pytest -p no:warnings)      # 99 passed
(cd packages/capabilities/dataagent-data && .venv/bin/python -m pytest -p no:warnings)        # 654 passed
(cd packages/capabilities/dataagent-application && .venv/bin/python -m pytest -p no:warnings) # 203 passed
(cd packages/capabilities/dataagent-governance && .venv/bin/python -m pytest -p no:warnings)  # 121 passed
(cd packages/capabilities/dataagent-cli && python3 -m unittest discover -s tests)             # 12 OK

# 机器测量 + 评分
python3 $S/quality_run.py --repo . --package packages/capabilities/dataagent-runtime
python3 $S/score_landing.py --result docs/research/dataagent-2026-11-03/12-cli-build/r1-runtime.score.json

# D1 基线（与 current 同法：duplicate_rate(pkg, peers)）
rm -rf /tmp/baseline-cli && mkdir /tmp/baseline-cli
tar xzf /tmp/agentos-snapshots/pre-cli-20261106-013324.tar.gz -C /tmp/baseline-cli
# 基线实测 19.26%（338/1755；跨包 328）

# D5 / D7 探针（无副作用，写 /tmp/probe-root*）
PYTHONPATH=packages/capabilities/dataagent-runtime/src \
  packages/capabilities/dataagent-runtime/.venv/bin/python \
  docs/research/dataagent-2026-11-03/12-cli-build/r1-repro/probe_overflow2.py   # 42,680 B > 32 KiB
PYTHONPATH=packages/capabilities/dataagent-runtime/src \
  packages/capabilities/dataagent-runtime/.venv/bin/python \
  docs/research/dataagent-2026-11-03/12-cli-build/r1-repro/probe_detail_egress.py  # 全文含 statement

# CLI 黑盒
cd /tmp/tester-ws
export DATAAGENT_WORKSPACE=/tmp/tester-ws DATAAGENT_DATA_ROOT=/tmp/tester-ws/.dataagent
export DATAAGENT_HOST_SUBJECT_REF=user:tester DATAAGENT_HOST_PURPOSE=verification
PY=/Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-data/.venv/bin/python
$PY -m dataagent_data.interfaces.cli list | wc -l                       # 32
$PY -m dataagent_data.interfaces.cli run parse_delimited_file --file sales.csv --set has_header=true   # exit 0, handle
$PY -m dataagent_data.interfaces.cli run profile_table_structure --ref table_ref=table:06fea51e…@sha256:06fea51e…  # exit 0
$PY -m dataagent_data.interfaces.cli run nope                            # exit 2
$PY -m dataagent_data.interfaces.cli run parse_delimited_file --set has_header=maybe   # exit 2
$PY -m dataagent_data.interfaces.cli run parse_delimited_file --file ../outside/secret.csv  # exit 1, path traversal denied
```
