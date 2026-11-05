---
round: r2
date: 2026-11-06
subject: dataagent-runtime 统一 CLI 内核 + 三层 interfaces/cli.py 接入 + dataagent-cli 分发器 + dataagent-s0 依赖
plan: ../12-unified-cli-build-plan.md（r1，2026-11-06）
rubric: 2.1 sha256:5e65f6c6006a
snapshot:
  dataagent-runtime: sha256:ae8b738b6379901126e0c4de409e1ee422df5213f79c3aa930db9a31d8cbdd94
facts_ref: dataagent-runtime@sha256:ae8b738b6379901126e0c4de409e1ee422df5213f79c3aa930db9a31d8cbdd94
verdict: 不可验收
score: 89.0（B）
---

# 第 2 轮验收：统一 CLI

## 0. 结论

**功能面 W1–W4 全部落地**：设计 §5.3 的命令与参数、摘要/全文双通道、needs_input、外发剥离、退出码 0/1/2/3、身份只取宿主 env、三层接入、分发器 `link`/`setup`/`doctor` 均经独立黑盒复跑通过；全量测试 101 + 654 + 203 + 121 + 12 全绿，D1 重复率 2.21%（r1 13.84%）。

**rubric 仍不可验收，唯一闸门是 GATE-UNKNOWN（R13）**。开发者把 R13 记 `na`（"无已发布基线"）以获得"无闸门"，但仓库标准 `docs/standards/code-landing-rubric.md:240` 明确"无基线记 unknown"，`:279` 进一步写明"R13 在没有已发布基线的仓库里恒为 unknown……缺基线就不是可交付状态"。按标准记 unknown 后总分被封顶 **89.0**，开发者自评 **93.1 / 可验收不可复现**。

本轮另有 2 条新 P2（D8 `--file` 缺文件抛 traceback、D9 `gov confirm` 非法载荷抛 traceback），以及遗留的 D2 partial（CC>10 仍 25.68%）、D3 open（无默认超时）。无 P0/P1；这些 P2 不改变闸门结论。

## 1. 基线

| 项 | 实测 | 命令 |
|-|-|-|
| 快照 | `sha256:ae8b738b6379…`（67 文件），与 r2-fixes / 自评一致 | `python3 skills/code-landing-quality/scripts/snapshot.py packages/capabilities/dataagent-runtime` |
| runtime 测试 | **101 passed** | `(cd packages/capabilities/dataagent-runtime && .venv/bin/python -m pytest -p no:warnings)` |
| data 测试 | **654 passed** | 同法，`dataagent-data` |
| application 测试 | **203 passed** | 同法，`dataagent-application` |
| governance 测试 | **121 passed** | 同法，`dataagent-governance` |
| dispatcher 测试 | **12 OK** | `(cd packages/capabilities/dataagent-cli && python3 -m unittest discover -s tests)` |
| 重复率 | **2.21%**（53/2399 行；包内 20、跨包 33；15 组） → D1 green | `quality_run.py --repo . --package packages/capabilities/dataagent-runtime` |
| 复杂度 | CC>10 **25.68%**（阈 7.3%，A5.1 仍 0）；CC>25 **0.0%**（阈 1.1%，达标） | 同上（ast 计数，radon 未安装） |
| 裸 except / 吞错 | 0 / 0 | 同上 |
| bundle 漂移 | runtime / data / app / gov 四包均"一致" | 同上（逐包） |
| 打包 | `uv build` 成功产出 wheel + sdist；wheel 22 文件，含 `interfaces/unified.py`，0 个 `.pyc` | `uv build -o /tmp/da-runtime-dist-r2` + `unzip -l` |
| 依赖锁定 | `uv lock --check` → Resolved 13 packages（rc=0） | 同包目录 |

## 2. 方案清单

共 22 条（r2 方案新增"记录"表行）：**done 17 / partial 0 / not_done 0 / na 5 / waived 0**，完成率 100%。
r1 的两条 partial 本轮复跑通过：

| id | r1 | r2 | 证据 |
|-|-|-|-|
| `W1共享内核实现（dataage#99a1de` | partial | **done** | `probe_overflow2.py` stdout **1,524 B** ≤ 32,768 B（r1 42,680 B）；`inference_request` 落盘 80 条 samples 完整 |
| `W1共享内核实现（dataage#7cf8d0` | partial | **done** | `probe_detail_egress.py` summary 与 `--detail full` 均无 `statement`/`fields` |

其余 15 条 W1–W4 条目与 5 条元数据/记录行判 `done` / `na`，逐条证据见 [r2-tester-runtime.score.json](r2-tester-runtime.score.json) 的 `checklist.items`。

## 3. 缺陷

| ID | 级 | 状态 | 与上轮对比 | 复现（输入 → 期望 / 实际） | 位置 |
|-|-|-|-|-|-|
| D1 | P2 | fixed | 已修复 | `quality_run` → 期望 ≤3%；r1 13.84% → **r2 2.21%**（53/2399；跨包 33） | `.../adapters/sqlite.py:90` 等 |
| D2 | P2 | partial | 部分修复 | ast CC → 期望 CC>10 ≤7.3%、CC>25 ≤1.1%；实际 **25.68% / 0.0%**（CC>25 达标，CC>10 仍超阈） | `.../enforcement.py:255 CC=25`、`invoke.py:299 CC=24` 等 |
| D3 | P2 | open | 未修复 | 长耗时 op 经 `dataagent <layer> run` → 期望非空默认超时且可取消；实际 `invoke.py:353` 只拒绝已过期 deadline，不取消在途工作 | `.../interfaces/unified.py:330-354` |
| D4 | P2 | fixed | 已修复 | AST 吞错扫描 → 期望 0 处；r1 4 处 → **r2 0/0** | `.../unified.py`、`sqlite.py`、`gold_ledger.py` |
| D5 | P2 | fixed | 已修复 | `probe_overflow2.py`：needs_input + 80×500B samples → 期望 stdout ≤32,768 B；r1 42,680 B → **1,524 B** | `.../interfaces/unified.py:593-601`（r2 `_fit_summary`） |
| D6 | P2 | fixed | 已修复 | `dataagent bogus` → 期望 usage 含 `dataagent gov policy apply <file>`；r2 实跑第 14 行为正确文本 | `dataagent-cli/bin/dataagent:188-189` |
| D7 | P2 | fixed | 已修复 | `probe_detail_egress.py`：enforce + `egress_decision_ref=None` → 期望两条 stdout 通道一致剥离；r2 summary/full 的 `statement` 均 False | `.../interfaces/unified.py:623-629` |
| **D8** | P2 | **open** | 新登记 | `run parse_delimited_file --file nope.csv` → 期望 exit 2 usage（或 failed JSON）、无 traceback；实际 **exit 1 + FileNotFoundError traceback，stdout 空** | `.../interfaces/unified.py:487`（`_build_payload` → `hooks.make_file_ref`） |
| **D9** | P2 | **open** | 新登记 | `gov confirm <file>` 的 `confirmation` 缺 `criteria_digest`/`authority_ref` → 期望 exit 2 schema error；实际 **exit 1 + pydantic ValidationError traceback** | `dataagent-governance/src/.../interfaces/cli.py:115` |

D8/D9 均为输入校验边界上的未捕获异常（失败可见、非静默错误），按 P2 登记；D8 使 L2.4 由 1 降为 0（两轮对比中唯一的规则退化）。若要求 CLI 对任意 argv 都只输出结构化错误，则应在 `_build_payload` 捕获 `OSError`、在 `confirm` 包住 `ValidationError`（预期退出码 2）。

## 4. 分数

`score_landing.py --result r2-tester-runtime.score.json` 输出：

| 闸门 | 封顶 | 触发项 |
|-|-|-|
| **GATE-UNKNOWN** | **89** | **R13** |

| 硬规则 | 依据 | 灯 |
|-|-|-|
| R01 依赖方向 | A | green |
| R03 依赖无环 | A | green |
| D1 重复率硬阈 | A | **green**（2.21%） |
| V1 版本同步 | A | green |
| E1 错误码登记 | A | na |
| R13 破坏性变更升 major | A | **unknown** |
| R14 契约对齐 | A | green |

| 维度 | 权重 | 得分率 | 已判定 |
|-|-|-|-|
| 规模与重复率 | 6 | 100.0% | 2/2 |
| 依赖与独立性 | 6 | 100.0% | 3/3 |
| 抽象度 | 4 | 100.0% | 1/1 |
| 内聚 | 4 | 100.0% | 1/1 |
| 复杂度 | 7 | 42.9% | 3/3 |
| 功能自足 | 5 | 100.0% | 2/2 |
| 契约面（信息轴） | 0 | 0.0% | 1/1 |
| 可替换性 | 4 | 100.0% | 2/2 |
| 可装载性 | 6 | 100.0% | 3/3 |
| 错误语义 | 5 | 100.0% | 1/2 |
| 演进性 | 4 | 100.0% | 2/2 |
| 契约对齐 | 4 | 100.0% | 2/2 |
| 能力面落地 | 6 | 0.0% | 0/3 |
| 语义正确性 | 12 | 80.0% | 4/5 |
| 安全与治理 | 12 | 100.0% | 4/5 |
| 健壮性与资源 | 6 | 50.0% | 2/3 |
| 测试有效性 | 6 | 100.0% | 3/3 |
| 发布与溯源 | 3 | 100.0% | 2/2 |

- 总分 **89.0 / 100（B）**，证据覆盖 100%；原始分 91.1，被 GATE-UNKNOWN 封顶到 89。按验收条件"总分 ≥80 且无闸门"，结论 **不可验收**。
- 得 0：A5.1（CC>10 25.68%）、L2.4（D8）、L4.2（D3）。
- 不适用（profile runtime 允许）：A10.2、L1.1、L1.2、L1.3、L2.5、L3.5、L4.1。

## 5. 与上一轮对比

`round_diff.py r1-runtime.score.json r2-tester-runtime.score.json`：

| 项 | r1 | r2 |
|-|-|-|
| 分数 | 59.0（E） | 89.0（B） |
| 闸门 | GATE-RED + GATE-CHECKLIST + GATE-UNKNOWN | GATE-UNKNOWN |
| 清单 | 15 done / 2 partial / 4 na | 17 done / 0 partial / 5 na |
| 缺陷 | 7 条 P2 | 9 条 P2（fixed 5 / partial 1 / open 3） |

缺陷变化：**已修复 5**（D1、D4、D5、D6、D7）；**部分修复 1**（D2）；**未修复 1**（D3）；**新缺陷 2**（D8、D9）；无回归。规则 0→1：A1.1、A5.2、A10.1、L2.1、L3.3；1→0：L2.4（D8）。

## 6. 开发者声明核对（r2-fixes.md）

| 声明 | 结论 | 依据 |
|-|-|-|
| D1 13.84% → 2.21%，GATE-RED 消除 | 已证实 | 复跑 quality_run：2.21%（53/2399），D1 green |
| #99a1de / D5：1,524 B ≤ 32 KiB，完整请求落盘 | 已证实 | 复跑 `probe_overflow2.py`；`.inference_request.json` 含 80 条 samples |
| #7cf8d0 / D7：summary 与 full 两条通道均剥离 | 已证实 | 复跑 `probe_detail_egress.py`：两条通道 `statement` 均 False |
| D4：吞错 0/0 | 已证实 | quality_run hygiene 0 / 0 |
| D6：usage 文本修正 | 已证实 | `sh bin/dataagent bogus` → rc 2，第 14 行正确 |
| D2 partial / D3 open 留待后续轮 | 已证实 | CC>10 25.68%；无默认 deadline |
| 全量测试 101 / 654 / 203 / 121 / 12 | 已证实 | §8 五条命令复跑 |
| bundle 四包一致 | 已证实 | 逐包 quality_run bundle_drift |
| **R13 记 na，93.1 可验收、无闸门** | **不成立** | `docs/standards/code-landing-rubric.md:240,279` 规定无基线恒为 unknown；改记 unknown 后 GATE-UNKNOWN、封顶 89 |
| 自评清单证据"app 179 / runtime 99" | 部分成立 | 实际 app 203 / runtime 101（r2-fixes 正文数字正确，score JSON 的 checklist evidence 未同步） |
| `doctor` 检查策略且缺失退 3 | 存疑（P2 文档口径） | 无策略时实跑 doctor 输出 `policy: none` 且 **exit 0**；方案 W3 文字"（缺失退 3）"与实现不一致，需产品确认"策略缺失"是否属环境缺失 |

## 7. 未测量

| 规则 | 测量需要的条件 |
|-|-|
| R13 破坏性变更升 major | 已发布基线（git tag / Mint Hub 制品）。当前 AgentOS 非 git 仓库、dataagent-runtime 0.1.0 从未发布，故按标准记 **unknown**，GATE-UNKNOWN 封顶 89。要转 green：先发布一个基线制品；或由标准 owner 给出**带日期的硬规则豁免**（skill 允许"hard rules only"记录 dated exemption）。 |

## 8. 复跑命令

```sh
cd /Users/payne/Vibe/AgentOS
S=skills/code-landing-quality/scripts

# 快照 + 五套测试
python3 $S/snapshot.py packages/capabilities/dataagent-runtime    # sha256:ae8b738b…（67 文件）
(cd packages/capabilities/dataagent-runtime && .venv/bin/python -m pytest -p no:warnings)      # 101 passed
(cd packages/capabilities/dataagent-data && .venv/bin/python -m pytest -p no:warnings)         # 654 passed
(cd packages/capabilities/dataagent-application && .venv/bin/python -m pytest -p no:warnings)  # 203 passed
(cd packages/capabilities/dataagent-governance && .venv/bin/python -m pytest -p no:warnings)   # 121 passed
(cd packages/capabilities/dataagent-cli && python3 -m unittest discover -s tests)              # 12 OK

# 机器测量 / 评分 / 轮次对比
python3 $S/quality_run.py --repo . --package packages/capabilities/dataagent-runtime           # 2.21% / 吞错 0 / CC>10 25.68% / CC>25 0.0% / bundle ok
python3 $S/score_landing.py --result docs/research/dataagent-2026-11-03/12-cli-build/r2-tester-runtime.score.json  # 89.0，GATE-UNKNOWN
python3 $S/round_diff.py docs/research/dataagent-2026-11-03/12-cli-build/r1-runtime.score.json \
  docs/research/dataagent-2026-11-03/12-cli-build/r2-tester-runtime.score.json                 # 59→89，fixed 5 / partial 1 / open 1 / new 2

# D5 / D7 探针
PYTHONPATH=packages/capabilities/dataagent-runtime/src packages/capabilities/dataagent-runtime/.venv/bin/python \
  docs/research/dataagent-2026-11-03/12-cli-build/r1-repro/probe_overflow2.py    # 1,524 B ≤ 32 KiB
PYTHONPATH=packages/capabilities/dataagent-runtime/src packages/capabilities/dataagent-runtime/.venv/bin/python \
  docs/research/dataagent-2026-11-03/12-cli-build/r1-repro/probe_detail_egress.py # summary/full 均无 statement

# CLI 黑盒（临时工作区）
WS=/tmp/tester-r2-ws; mkdir -p $WS; cd $WS
printf 'region,amount\nAPAC,10\nEMEA,20\n' > sales.csv
export DATAAGENT_WORKSPACE=$WS DATAAGENT_DATA_ROOT=$WS/.dataagent
export DATAAGENT_HOST_SUBJECT_REF=user:tester DATAAGENT_HOST_PURPOSE=verification
PY=/Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-data/.venv/bin/python
$PY -m dataagent_data.interfaces.cli list | wc -l                                  # 32
$PY -m dataagent_data.interfaces.cli parse_delimited_file --help | grep -c '\$defs' # 0
$PY -m dataagent_data.interfaces.cli run parse_delimited_file --file sales.csv     # exit 0，handle + result_path
$PY -m dataagent_data.interfaces.cli run parse_delimited_file --file nope.csv      # D8：exit 1 + traceback（应为 2）
$PY -m dataagent_data.interfaces.cli run parse_delimited_file --input-file /tmp/smuggle.json  # context → exit 2

# 分发器（临时 mint 布局）
sh packages/capabilities/dataagent-cli/bin/dataagent doctor          # 缺层 exit 3；三层齐备 exit 0
sh packages/capabilities/dataagent-cli/bin/dataagent link            # 生成可执行 ./dataagent
sh packages/capabilities/dataagent-cli/bin/dataagent bogus           # exit 2，usage 第 14 行含正确文本

# gov confirm / policy apply（临时 data_root）
G=packages/capabilities/dataagent-governance/.venv/bin/python
$G -m dataagent_governance.interfaces.cli policy apply policy.json   # "tenant:default@r1"，exit 0
$G -m dataagent_governance.interfaces.cli confirm confirm.json       # draft→confirm→active，exit 0
```

## 9. 验收结论

**不可验收。** 阻断项：

1. **R13 / GATE-UNKNOWN**（唯一闸门）：开发者把 R13 记 `na` 不符合 `docs/standards/code-landing-rubric.md:240,279`（无基线记 `unknown`）。自评 93.1 / 无闸门不可复现；按标准为 **89.0（B）/ GATE-UNKNOWN**。清除路径：发布基线制品，或取得**带日期的硬规则豁免**（标准 owner 决策）。
2. （非阻断，P2）D8 / D9 未捕获异常：`--file <不存在>` 与 `confirm` 非法载荷应返回结构化 usage error（2），当前抛 traceback 后退出 1。
3. （非阻断，P2）D2 CC>10 25.68% 仍超阈；D3 无默认超时（均自 r1 遗留，方案范围未含 D3）。
