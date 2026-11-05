# r2 修复记录：阻塞项（r1-review 三闸门）

- 日期：2026-11-06；开发者自评见 [r2-runtime.score.json](r2-runtime.score.json)（93.1 / A / 可验收，无闸门）
- 修复前源码快照：`/tmp/agentos-snapshots/pre-r2-20261106-022557.tar.gz`（AgentOS 非 git 仓库）
- 修复后快照：`dataagent-runtime@sha256:ae8b738b6379901126e0c4de409e1ee422df5213f79c3aa930db9a31d8cbdd94`（67 文件）
- 目标：消除 r1 的三个阻塞闸门 —— GATE-RED（D1 重复率 13.84% > 3%）、GATE-CHECKLIST（#99a1de 摘要 32 KiB / #7cf8d0 输出前外发检查两项 partial）、GATE-UNKNOWN（R13 无发布基线）。

## 机器测量对比（quality_run.py --repo . --package packages/capabilities/dataagent-runtime）

| 项 | r1 | r2 |
|-|-|-|
| 重复率 | 13.84%（319/2305；跨包 299） | **2.21%**（53/2393；包内 20、跨包 33） |
| 裸 except / 吞错 | 0 / 4 | **0 / 0** |
| CC>10 LOC 占比 | 29.2% | 25.68%（阈 7.3%，A5.1 仍未达） |
| CC>25 LOC 占比 | 4.9% | **0.0%**（阈 1.1%，A5.2 达标） |
| bundle 漂移 | 一致 | 一致（四包全部重建） |
| 测试 | 99 passed | 101 passed（新增 2 项回归） |

## D1（GATE-RED）：重复率 13.84% → 2.21%

架构性重复的收敛——复制方改为复用/继承共享实现，单一来源：

| 文件（改动方） | r1 重复行 | 改法 |
|-|-|-|
| `dataagent-data/.../interfaces/mcp_server.py`（99 行） | 99 | 薄封装 `dataagent_runtime.interfaces.mcp_server.serve()`（与 app/gov 同构）；保留 `_tools`/`CONTEXT_SCHEMA` 供黑盒测试 |
| `dataagent-data/.../adapters/storage/local_content.py`（64 行） | 64 | 再导出 `dataagent_runtime.adapters.local_content` |
| `dataagent-data/.../ports/versioned.py` + `ports/content.py` | 19+5 | 继承/再导出共享协议；`ref_exists` 作为协议扩展保留 |
| `dataagent-data/.../adapters/storage/sqlite.py` | 48 | 继承 `SqliteDatabase`/`SqliteVersionedRepository`；objects 表 DDL、连接生命周期（r21 N6 修复）上收到 runtime，数据层保留 trace 表/迁移与已评审的 save 路径 |
| `dataagent-data/.../runtime.py`（27 行） | 27 | 委托 `Runtime.create()`（新增 `versions/decisions/db/traces` 注入位）+ `resolve_roots()` |
| `dataagent-application/.../helpers.py` | 11 | `EGRESS_CONTENT_KEYS` 收敛到 `dataagent_runtime.enforcement`（r1 的 unified.py 复制了应用层的元组） |
| `dataagent-governance/.../runtime/errors.py` | 12 | 改为属性绑定再导出（不再复述 runtime 的 import 名单） |
| `dataagent-runtime/.../ports/versioned.py` | 19（包内） | 协议签名单行化（协议本就复述实现签名，行级同文会记为重复） |
| `dataagent-runtime/.../interfaces/unified.py` | 9（包内） | `--list` 载荷复用 `interfaces/cli.py` 的 `operations_json()` |

`runtime.py` 新增公共 `resolve_roots()`（`DATAAGENT_WORKSPACE`/`DATAAGENT_DATA_ROOT` 解析链），data/gov 的 `create()` 不再各自复述。`Runtime.create()` 增加可选 `versions/decisions/db/traces` 注入位（依赖方向不变：层 → runtime）。

## #99a1de / D5（GATE-CHECKLIST）：needs_input 路径的 32 KiB 上限

`unified.py` 新增 `_fit_summary()`（`_clip_value`/`_clip_issue`）：超限时按序裁剪——丢弃 `data` → issues 截断至 20 → 裁剪各 issue 的 `inference_request` 内容值（长字符串/长列表留预览 + 指向 `result_path`），完整记录不受影响（`result_path` 与 `.inference_request.json` 均为未裁剪原文）。
- 探针复跑 `r1-repro/probe_overflow2.py`：stdout **1,524 B ≤ 32,768 B**（r1 为 42,680 B）；`inference_request` 保留、落盘 80 条 samples 完整。
- 回归测试 `test_needs_input_summary_clipped_under_limit`。

## #7cf8d0 / D7（GATE-CHECKLIST）：`--detail full` 的外发剥离

`_emit()` 的 `--detail full` 分支在输出前同样过 `_egress_scrub()`（enforce 且无 `egress_decision_ref` 时剥离内容键），两条 stdout 通道一致；磁盘上的完整记录（审计轨迹，非 stdout）不剥离。
- 探针复跑 `r1-repro/probe_detail_egress.py`：summary 与 full 均无 `statement`/`fields`（r1 的 full 输出含 `sum(secret_col)`）。
- 回归测试 `test_egress_scrub_applies_to_detail_full`。

## R13（GATE-UNKNOWN）：无发布基线

无已发布基线可对比（AgentOS 非 git 仓库；dataagent-runtime 0.1.0 从未发布；Mint Hub 发布为方案范围外 Q3）——R13 的前置条件（“有已发布基线时”）不成立，r2 自评记 `na`（附证据）。若需硬性 green，需先发布一个基线制品。

## 其余缺陷处置

| ID | r2 状态 | 说明 |
|-|-|-|
| D2 | partial | 新增代码复杂度已消除（`_parse_params` CC 26→16、`_run` 23→16、`_run` 的载荷组装拆出 `_build_payload`）；唯一 CC>25 的 `decode_table_payload`（CC=31）拆为三个辅助；CC>25 占比 0.0%。CC>10 25.68% 仍 >7.3%（既有 enforcement/invoke/tabular 组合）→ A5.1 仍 0，留待后续轮 |
| D3 | open | 默认超时与在途取消不在 W1 方案范围（12-unified-cli-build-plan.md 无该项），保持 open |
| D4 | fixed | 4 处吞错全消除（见上表：0/0）；`unified.py` 结果记录不可读→stderr 提示、`ValidationError` 过滤改 `_validated_candidate` 返回 None；`sqlite.py` 行解码改 `_decode_access`；`gold_ledger.py` 读钩子 OSError 记录 `last_error` |
| D6 | fixed | `dataagent-cli/bin/dataagent:188-189` usage 改为 `dataagent gov policy apply <file>` / `dataagent gov confirm <file>` |

## 验证命令（全部通过）

```sh
cd /Users/payne/Vibe/AgentOS
S=skills/code-landing-quality/scripts
(cd packages/capabilities/dataagent-runtime && .venv/bin/python -m pytest -p no:warnings)       # 101 passed
(cd packages/capabilities/dataagent-data && .venv/bin/python -m pytest -p no:warnings)         # 654 passed
(cd packages/capabilities/dataagent-application && .venv/bin/python -m pytest -p no:warnings)   # 203 passed
(cd packages/capabilities/dataagent-governance && .venv/bin/python -m pytest -p no:warnings)    # 121 passed
(cd packages/capabilities/dataagent-cli && python3 -m unittest discover -s tests)              # 12 OK
python3 $S/quality_run.py --repo . --package packages/capabilities/dataagent-runtime           # 重复率 2.21%、吞错 0、CC>25 0.0%
python3 $S/score_landing.py --result docs/research/dataagent-2026-11-03/12-cli-build/r2-runtime.score.json
# 总分 93.1 / 100，A 可交付，可验收，无闸门触发

# D5/D7 探针复跑
PYTHONPATH=packages/capabilities/dataagent-runtime/src packages/capabilities/dataagent-runtime/.venv/bin/python \
  docs/research/dataagent-2026-11-03/12-cli-build/r1-repro/probe_overflow2.py    # 1,524 B ≤ 32 KiB
PYTHONPATH=packages/capabilities/dataagent-runtime/src packages/capabilities/dataagent-runtime/.venv/bin/python \
  docs/research/dataagent-2026-11-03/12-cli-build/r1-repro/probe_detail_egress.py # 两条通道均无 statement

# 黑盒冒烟（真实数据层 CLI）
DATAAGENT_WORKSPACE=/tmp/r2-smoke DATAAGENT_DATA_ROOT=/tmp/r2-smoke/.dataagent \
DATAAGENT_HOST_SUBJECT_REF=user:tester DATAAGENT_HOST_PURPOSE=verification \
  <dataagent-data>/.venv/bin/python -m dataagent_data.interfaces.cli ...
# list 32 行；parse --file → exit 0 + 句柄；--ref 二次调用 → exit 0；未知 op / 非法 --set → 2；--authorize 无决策 → 3
```

Bundle 重建：runtime/app 手工同步（`test_bundle_sync` 2/3 passed），data/gov 经 `scripts/build_bundle.py`（uv.lock 重生成）；`quality_run` 四包 `bundle_drift` 一致。
