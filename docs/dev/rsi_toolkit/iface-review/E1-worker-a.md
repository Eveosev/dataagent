---
title: 附录 E1：Worker A 执行方案（源码与契约）
date: 2026-10-28
status: proposed
parent: E-execution-overview.md
---

# 附录 E1：Worker A 执行方案（源码与契约）

**职责**：让 RSI 源码具备可拆分的条件，迁出首批 4 个能力包的代码，并写出通用能力契约草案。分工、文件所有权和同步点见[附录 E](E-execution-overview.md)；设计依据见[附录 A](A-first-batch-packages.md)、[附录 B](B-capability-contracts.md) 和[附录 D](D-verification-evidence.md)。

**工作目录**：`apps/plugins/rsi-toolkit`，分支 `iface/a-source`。下文路径都相对于这个目录。

**全程不变的门**：每个任务结束时，下面这条命令都要通过：

```bash
cd service && .venv/bin/python -m pytest -q
```

## A0 文档与清单修订（0.5 天，可随时做）

1. 在方案 A（AgentOS `docs/superpowers/specs/2026-10-28-rsi-iface-modularization-design.md`）文首加评审结论链接。阶段编号旁注明“以附录 C 为准”。
2. 修改 AgentOS `docs/architecture/rsi-toolkit-modules.toml`：
   - evaluation-kit 的 `depends_on` 改为 `["content-store", "paired-evidence"]`；
   - component-runner 去掉对 measurement-evidence 的依赖；
   - 新增 `contracts-runtime` 和 `execution-port` 两个模块；
   - 每个模块增加 `publish_package` 字段，取值按附录 A A.2 的映射表。

**验收**：清单用 `python3 -c "import tomllib; tomllib.load(open(...,'rb'))"` 能解析；模块数是 15，并且每个模块都有 `publish_package`。

## A1 M0-pre 源码解耦（2–3 天，阻塞 A3）

### A1.1 包初始化改为懒加载

- `service/rsi/__init__.py` 和 `service/control/__init__.py` 改用 PEP 562 的 `__getattr__` 按需导入。`__all__` 和对外名字保持不变。
- 新增测试 `service/tests/test_import_closure.py`。每条用例在子进程里执行 `python -I -c "import X; print(sorted(sys.modules))"`，然后断言：

| 导入目标 | 不得出现在 `sys.modules` 中 |
| --- | --- |
| `rsi.promotion` | `rsi.store`、`control.*`、`harness.learners.*`、`yaml`、`jsonschema` |
| `control.redaction` | `control.controller`、`harness.*` |
| `harness.store.cas` | `rsi.*`、`control.*` |
| `connectors.common.host` | `rsi.*`、`control.*`、`harness.*` |

### A1.2 断开 rsi 对 toolkit 的依赖

依赖方向应当是 toolkit 作为应用层依赖 rsi，而不是反过来。所以不移动 `toolkit/suite_verifier`，而是把 rsi 用到的 toolkit 能力先下沉到暂存位置，让 rsi 不再导入 toolkit：

- `toolkit/contracts.py`（schema loader）下沉，被 `rsi/store.py`、`rsi/experience.py`、`rsi/components.py` 使用。
- `toolkit/model.py` 下沉，被 `rsi/runtime.py` 延迟导入。
- `toolkit/m0_legacy.py` 中的 trace 归一函数下沉，被 `rsi/learning.py`、`rsi/legacy.py` 使用。
- 暂存位置是 `service/_staging/`。A3 时这些代码会整体移进 `modules/`。
- 原位置保留 re-export。

**验收**：`rg -n "^from toolkit|^import toolkit" service/rsi` 没有结果；增加一条 import-closure 用例，断言导入 `rsi.store` 时不会加载任何 `toolkit.*`。

### A1.3 指纹去掉模块路径

- `rsi/evaluation.py:257-262` 的 `evaluator_fingerprint` 拆成两个版本：
  - **v2**：由 `evaluator.contract()["id"]`、版本、`evaluate` 源码 digest 和 contract 组成，不包含 `__module__`。
  - **v1**：保留原函数，命名为 `evaluator_fingerprint_v1`，并新增一张 `LEGACY_MODULE_ALIASES` 表，记录“新类路径 → 旧模块名”。
- `qualification_matches`（`:352`）的匹配规则：
  - 记录是 v1 时，用别名表把类映射回旧模块名，再按 v1 计算并比较；
  - 记录是 v2 时，直接比较。
  - 新写入的记录一律用 v2。
- `control/evidence.py:81` 的 `verifier_description` 按同样方式处理。`_check_measurement`（`control/controller.py:288`）同时接受 v1 和 v2。

新增测试 `service/tests/test_fingerprint_migration.py`，覆盖三种情况：

1. 用当前代码生成一条 v1 qualification，然后模拟类被搬到新命名空间（登记别名），断言仍能匹配。
2. v2 指纹在模块路径变化后保持不变。
3. 评测器源码一改，v1 和 v2 都必须不再匹配。

这是一次**数据格式变更**。在执行记录里写明：已有数据库里的 qualification 不需要迁移，靠别名表兼容。

### A1.4 合入

- 提交 PR 并合入 `iface/a-source`，通知 B rebase，完成同步点 S1。

## A2 通用能力契约草案（1–1.5 天，与 A1 并行）

- 按附录 B 的 C1–C7，写出 `contracts/proposed/<name>.v1.json` 和 `contracts/proposed/<name>.CONTRACT.md`。7 个名字分别是 blob、index、evaluation、evidence、asset、workspace-staging、runtime-executor。
- JSON 部分描述类型、方法、错误码、状态枚举。状态复用 `iface-types` 的 `RequestState`、`Verdict`，错误复用 `Error{category, code, message}`。
- CONTRACT.md 写清幂等、取消、`Unknown`、原子性语义，并附上“要问开发者的问题”。
- 每份草案标 `status: contract-proposed`，不能被 `[[implements]]` 引用。
- C1 的 canonical JSON 规则写死为现有算法（`harness/util.py:15-16`），并补一条：禁止 NaN 和 Infinity。

**验收**：7 份 JSON 都能解析；附录 B 中每条“要问开发者的问题”都出现在对应的 CONTRACT.md 里。产出交给用户，用于上游沟通。

## A3 迁移 `rsi-foundation` 与 `rsi-evaluation`（3–4 天，依赖 S0、S1）

### A3.1 `modules/rsi-foundation`

- **`rsi_foundation.content`**：来自 `harness/store/cas.py`、`harness/util.py` 里的 canonical 和 sha256，以及 `rsi/store.py` 中的私有 CAS 子类。
- **`rsi_foundation.contracts`**：
  - 来自 `_staging` 里的 schema loader；
  - 新写一个**标准库子集校验器**，只支持附录 A A.3 列出的关键字和 `date-time` 格式，遇到不支持的关键字直接报错；
  - 5 个 schema 作为包数据内置；
  - `RecallPolicy` 等共享 DTO 从 `rsi/experience.py` 迁入。
- **`rsi_foundation.evidence`**：来自 `control/redaction.py`、`rsi/redact.py`，以及 `control/evidence.py` 的通用部分。`verifier_description` 依赖 `benchmarks`，留在 control。
- **测试**：
  - 迁入 `test_m0_contracts`；
  - 新增差分测试：对 `contracts/examples/v1/*`（11 个）和 `contracts/invalid/v1/*`（8 个），子集校验器与 jsonschema 的判定必须完全一致。jsonschema 只在开发环境使用；
  - 新增 redact 和 rsi CAS 的单元测试；
  - 增加一个 digest 回归用例：用现有 CAS 数据确认 digest 不变。

### A3.2 `modules/rsi-evaluation`

- **来源**：`rsi/evaluation.py:18-391`（不含 `ExperimentService`）、`rsi/judge.py`、`rsi/promotion.py:11-71`。
- **约束**：
  - judge 只依赖一个注入的模型 Protocol，不导入 `rsi-model-client`；
  - YAML 套件仍然延迟导入 pyyaml，在 `package.toml` 里登记为 `optional_third_party`。
- **测试**：迁入 `test_rsi_evaluation`、`test_rsi_judge`，以及 `test_rsi_promotion` 中的纯函数用例。

### A3.3 两个包都要做的事

- 原路径保留 re-export，例如 `rsi.evaluation` 从 `rsi_evaluation` 重新导出，`harness.store.cas` 从 `rsi_foundation.content` 重新导出。
- 填写 `package.toml`、`iface.toml`、`SKILL.md`：
  - `rsi-evaluation`：`implements rsi-evaluator.data`，`proposes evaluation/v1`；
  - `rsi-foundation`：`proposes blob/v1` 和 `evidence/v1`。
- 交给 B 的清单校验器检查，完成同步点 S2。

### A3 验收

- 隔离测试：只把本包和声明的依赖放进 `sys.path`，测试全部通过。

```bash
python3 -I -m pytest modules/rsi-foundation/tests
python3 -I -m pytest modules/rsi-evaluation/tests
```

  （由各包 `tests/conftest.py` 按 `package.toml` 拼接 `sys.path`。`rsi-foundation` 的差分测试在没有 jsonschema 时跳过。）
- `rg -n "^(from|import) (rsi|control|harness|toolkit|connectors)\b" modules/*/src` 没有结果。
- 全量测试通过；`test_fingerprint_migration` 通过。

## A4 迁移 `rsi-model-client` 与 `rsi-execution`（2 天，依赖 S2）

- **`modules/rsi-model-client`**：
  - 来源：`_staging` 中的 model 和 network 代码。`toolkit/proxy.py` 不迁移；
  - `iface.toml`：`consumes agentcpm/iface-model@0.1.0`；
  - 测试：迁入 `test_toolkit_launcher` 中与模型相关的用例；新增替换测试，让同一个调用方分别使用真实客户端（指向本地桩 HTTP 服务）和替身模型。
- **`modules/rsi-execution`**：
  - 来源：`connectors/common/host.py`，包括 `Host` Protocol、`normalize_result`、`safe_path` 和 `stage_assets`；
  - 新增 RuntimeExecutor 的 DTO：`ExecRequest`、`ExecResult`、`CancelAck`；
  - 新增两种 staging 策略：`common` 是现有行为；`strict` 从 `MintHost._stage` 的规则复制过来，`MintHost` 本身暂不改动；
  - `iface.toml`：`proposes runtime-executor/v1` 和 `workspace-staging/v1`；
  - 测试：迁入 `test_common_host`；新增两种策略的负例（`..`、绝对路径、symlink、`.git`、`.mint`）；新增替换测试，让同一个调用方分别使用两种替身宿主。

**验收**：与 A3 相同的隔离测试、导入检查和全量测试。两个替换测试都通过。

## A5 M1 退出材料（0.5 天）

- 更新附录 C 中 A 侧的执行记录：已完成的任务、每项验收命令及其输出摘要、出现过的行为变更（应当为零，否则逐条列出）。
- 列出 M2 和 M3 的输入条件：
  - `rsi.worker` 和 `RSI_ROOT` 的硬编码点；
  - `0001_core.sql` 的拆分方案；
  - `Store.tx` 的 savepoint 与锁设计；
  - 3 处直接写 SQL 的清理方案。

## 不做的事

- 不改 `MintHost`、`SeatbeltMintHost`、`PilotDeckHost` 的行为，这些留到 M4。
- 不改 Selector 的降级策略，不改 staging 的默认规则。
- 不改 `contracts/*.json` 中已冻结的数据契约；确有必要时，先通知 B 和用户。
- 不碰 Mint 打包相关的文件（归 B 所有）。
