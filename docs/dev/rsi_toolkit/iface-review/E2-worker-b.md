---
title: 附录 E2：Worker B 执行方案（分发与平台）
date: 2026-10-28
status: proposed
parent: E-execution-overview.md
---

# 附录 E2：Worker B 执行方案（分发与平台）

> **2026-11-02 更新**：`packages/kernel-iface` 已冻结为 0.1.0 历史快照，勿作对比基线；iface 契约现以
> `packages/agent-kernel/kernel/iface/src` 为权威源，可读副本为 `packages/agent-kernel/packages/iface-*`（0.1.2）。
> 对比前先同步 agent-kernel，见 AgentOS 根 `README.md`。

**职责**：固定 IFace 权威基线；定义并校验包清单；生成契约包；构建能力 bundle 和不依赖 pip 的启动器；在真实 mint 工程中完成 M1 分发探针。

分工、文件所有权和同步点见[附录 E](E-execution-overview.md)，设计依据见[附录 A](A-first-batch-packages.md) A.3–A.5。

**工作目录**：`apps/plugins/rsi-toolkit`，分支 `iface/b-distribution`。下文路径都相对这个目录，新代码统一放在 `packaging/` 下。

**本机工具**：`~/.mint/bin/mint`（0.1.11）。不要用 PATH 上的 launcher，因为它会重置 `MINT_HOME`。

**全程约束**：
- 只用 `local/` scope，不登录，不发布到 MintHub。
- 用户端的任何步骤都不能执行 pip。
- 构建工具只依赖 Python 标准库。

## B0 文档修订（0.5 天，可随时做）

**方案 B**（AgentOS `docs/dev/rsi_toolkit/2026-10-28-iface-modularization-and-minthub.md`）：
- 文首加评审结论的链接。
- 阶段编号改为附录 C 的编号。
- “7 个状态包”改为 6 个。
- “并行方案 B”改为“方案 A”。
- `rsi.host/v1` 改为“旧边界，不进入首批”。
- 包清单改为附录 A 的首批 5 包加后续 5 包。

**平台笔记**（`2026-10-28-mint-platform-notes.md`）：
- “mcp 为路线图”改为实测结论：线上已有 4 个 mcp 包。
- “Python 不能用 plugin”改为：native 包加启动器已有先例，见 `wujiahe/knowledge-local`。
- 补充两条：`graph-loop` 使用的键是 `component_protocols`；0.1.12 二进制里检索不到 `loop/next`。

**取舍说明**（`2026-10-28-iface-plan-rationale.md`）：文首注明“对比与分工以评审文档为准”。

**生成器 README**（`mint-iface/README.md`）：文首标注“已由 RSI 仓库 `packaging/contracts/` 取代”。

## B1 IFace 权威基线（0.5 天，没有前置依赖）

1. 在临时目录拉取线上的 10 个 `agentcpm/iface-*@0.1.0`：

   ```bash
   ~/.mint/bin/mint pull agentcpm/iface-types@0.1.0 agentcpm/iface-store@0.1.0 ...   # 共 10 个
   ~/.mint/bin/mint inspect agentcpm/iface-store@0.1.0
   ```

   需要写 `~/.mint` 缓存。沙箱拒绝写入时，申请权限后再执行。

2. 写 `packaging/iface-baseline.toml`，每个包记录：名称、版本、manifest digest、签名 keyid、`provides.interfaces`。

3. 写一份漂移报告 `packaging/iface-baseline-drift.md`，把线上制品与本地 `packages/kernel-iface` 快照逐包比较：
   - `mint.toml` 的 kind 和 provides；
   - `schema.json` 的方法串；
   - README 列出但 trait 中不存在的方法（附录 D D.1 已列出，这里需要逐项复核）。

   这份报告交给用户，用于和 kernel 维护方沟通。

**验收**：基线文件覆盖全部 10 个包；`mint verify`（或 `inspect` 的输出）能核对上面记录的 digest。

## B2 清单 schema 与校验器（1 天，同步点 S0）

1. 实现 `packaging/manifest.py`，提供两个功能：
   - 按附录 E E.4 的字段校验 `package.toml` 和 `iface.toml`；
   - 由 `[[implements]]` 生成 `provides.interfaces`。
2. 校验规则：
   - `depends` 里只能写 RSI 包，并且不能成环。
   - `[[implements]]` 只能引用 5 个已冻结的 `rsi-*.data` 契约，并且 `evidence` 指向的路径必须存在。
   - `[[consumes]]` 只能引用 `iface-baseline.toml` 中登记的包和版本。
   - `[[proposes]]` 必须指向 `contracts/proposed/` 下存在的文件。A2 完成之前，这一条只给警告。
3. CLI：`python3 packaging/manifest.py check modules/<pkg>`，失败时返回非零退出码，并逐条报告。
4. 测试 `packaging/tests/test_manifest.py`：用 fixture 模块分别覆盖每条规则的正例和负例。
5. 把 schema 写进附录 E E.4，请 A 确认，完成同步点 S0。

**验收**：测试全部通过；附录 A A.3 中首批 5 包的设计，都能用 v0 字段完整表达（A 确认）。

## B3 契约包 `rsi-iface-data`（1 天，没有前置依赖）

1. 新建 `packaging/contracts/build_iface_data.py`，取代 AgentOS `docs/dev/rsi_toolkit/mint-iface/gen_contract_packages.py`。改动如下：
   - **只输出一个包**：`local/rsi-iface-data`，`kind = "bundle"`。
   - **包内容**：
     - `schemas/` 下放 5 个 schema，不含 `host.v1.json`；
     - `CONTRACT.md`；
     - `skills/rsi-iface-data/SKILL.md`，内容说明怎么 pull、怎么实现、怎么声明。
   - **`mint.toml` 的 provides**：`provides.interfaces = ["rsi-trace.data", "rsi-experience.data", "rsi-evaluator.data", "rsi-recall.data", "rsi-component.data"]`，`provides.skills = ["rsi-iface-data"]`。
   - **README** 只教 `mint pull`。
   - **source-ref** 写入 `mint.toml` 的元数据和 `ORIGIN.md`，包含：RSI 仓库身份、完整 commit SHA、`subdir = "contracts"`、每个 schema 的 sha256。工作区有未提交改动时拒绝生成。
2. 在 `contracts/README.md` 中把 `host.v1.json` 标为 deprecated，说明它将由 `runtime-executor/v1` 取代。这一句需要先告知 A，由 A 确认。
3. 执行打包：

   ```bash
   ~/.mint/bin/mint --offline --json pack <out>/rsi-iface-data --out <out>/packed
   ```

**验收**：
- `pack` 成功。
- 包内 schema 的 sha256 与仓库中的文件一致。
- `provides.interfaces` 使用 `.data` 名。
- 包中不出现 `host` 和 `mint add`。

## B4 能力 bundle 构建器（1.5 天；先用 fixture 模块开发，S2 之后改用真实模块）

1. 新建 `packaging/build_bundle.py modules/<pkg> --out <dir>`，按以下步骤构建：
   - 先调用 B2 的校验，不通过就停止。
   - 生成 `mint.toml`，字段如下：
     - `name = "local/<pkg>"`，`kind = "bundle"`；
     - `[dependencies]` 由 `depends` 换算，每个依赖都写 `path:` 指向兄弟包的构建目录（本轮全部在本地）；
     - `provides.interfaces` 由 B2 生成；
     - `provides.skills = ["<pkg>"]`。
   - 复制 `src/<namespace>` 到 `lib/<namespace>`；复制 `iface.toml`；把 `SKILL.md` 放到 `skills/<pkg>/SKILL.md`。
   - 写 `release.json`，内容包括：包身份、`lib/` 目录树的 sha256 清单、source-ref。
   - **不生成** wheel，不生成 `setup.py`。
2. 构建守卫：
   - `lib/` 中出现 `.so`、`.pyd` 或 `*.dist-info` 时，构建失败。
   - 用 AST 检查 `lib/` 的顶层 import：只允许导入标准库、本包命名空间，以及 `depends` 中声明的命名空间；`optional_third_party` 中的包只允许出现在函数体内的延迟导入里。
3. 开发阶段用 `packaging/tests/fixtures/modules/` 中的两个假模块（`fx-base`、`fx-app`），不必等 A。

**验收**：
- 两个 fixture bundle 都能 `mint --offline pack` 成功。
- 守卫的负例会失败：放入 `.so`、顶层导入未声明的第三方包。

## B5 启动器与依赖闭包（1 天，与 B4 并行）

1. 新建 `packaging/launcher/rsi-launch.py`，即附录 A A.5 中的模板。要求：
   - 以 `python3 -I` 运行；
   - 按 `closure.json` 拼出 `sys.path`；
   - 依赖缺失时给出明确的报错并退出；
   - 不读取 PYTHONPATH 和 site-packages 中的用户包。
2. 应用 bundle 构建（`build_bundle.py --app --entry <module:func>`）：
   - 从 `depends` 递归算出依赖闭包，写 `closure.json`，每项记录 name、version、`lib/` 的 digest；
   - 把启动器复制到 `bin/`。
3. 启动时校验：每个依赖 `lib/` 的 digest 必须与 `closure.json` 一致，不一致就拒绝启动。用 `--no-verify` 可以跳过，仅限开发时使用。

**验收**：用 fixture 的 `fx-app` 依赖 `fx-base`，下面三种情况都要验证：
- 启动成功；
- 删掉 `fx-base` 后，启动给出明确的缺依赖报错；
- 改动 `fx-base` 的一个文件后，启动拒绝运行。

## B6 M1 分发探针（1.5 天，依赖同步点 S2）

在临时目录新建干净的 mint 工程，使用 A 交付的 `rsi-foundation` 和 `rsi-evaluation`，以及 B5 构建的探针应用 `rsi-probe`（入口调用 `rsi_evaluation` 做一次最小评测）。

```bash
~/.mint/bin/mint init probe --name local/probe --no-preset
cd probe
~/.mint/bin/mint add path:<out>/rsi-iface-data      # 契约包也用 path 方式；pull 需要仓库，留到发布时再验证
~/.mint/bin/mint add path:<out>/rsi-probe
~/.mint/bin/mint tree && ~/.mint/bin/mint why local/rsi-foundation
python3 -I .mint/packages/local/rsi-probe@0.1.0/bin/rsi-launch.py
~/.mint/bin/mint remove local/rsi-probe --dry-run && ~/.mint/bin/mint remove local/rsi-probe
~/.mint/bin/mint lock --check && ~/.mint/bin/mint verify
```

需要逐项记录的结论：

| 问题 | 记录内容 |
| --- | --- |
| `mint add` 是否递归展开 `[dependencies]`（尤其是 `path:` 依赖） | `tree` 的输出，以及 `.mint/packages/` 的目录列表 |
| 兄弟包的目录名是否稳定为 `<name>@<version>` | 目录列表；以及二次 `mint install` 之后是否保持不变 |
| 启动器能否在不跑 pip 的情况下完成调用 | 启动器的 stdout，以及进程环境中没有 pip 的证据 |
| `remove` 是否卸载孤儿依赖、是否有残留 | 卸载前后的目录对比 |
| `lock` 和 `verify` 是否覆盖 `lib/` 的内容 | 篡改一个 `lib/` 文件后，`verify` 的结果 |
| bundle 能否按平台分发 | `mint pull --help` 显示有 `--platform` 和 `--all-platforms`；用一个 fixture bundle 试声明平台字段，记录 `pack` 是否接受、产出的 manifest 里有没有平台层 |

**结果写入**：`conformance/mint/dist-probe-2026-10.json`（机器可读）和 `conformance/mint/dist-probe-2026-10.md`（结论和命令）。

**分支决策**：
- `mint add` 不展开依赖时，按附录 E E.6 启用退路方案：应用 bundle 内嵌依赖的 `lib/`。改动 `build_bundle.py --app --embed-deps`，然后重跑探针。
- bundle 不支持按平台分发时，在结论中写明：应用层的编译型依赖改走 `plugin/native` 路线（附录 A A.5 路线 2），留到 M5 处理。

## B7 上游平台问题包（0.5 天，在 B6 之后）

把附录 B B.4 末尾的 Mint 平台问题，和 B1、B6 的实测证据合成一份清单 `packaging/upstream-questions.md`，交给用户去沟通。每个问题都写成“现象、证据（命令和输出摘要）、我方的需要、建议的答案”。清单至少包括：
- 实现包也写 `provides.interfaces` 是否符合 Mint 预期（不阻塞）；
- `[dependencies]` 的递归展开方式，以及目录布局是否稳定；
- bundle 的按平台制品；
- `mint run --json` 的 NDJSON 事件 schema 能否作为稳定接口（L-E），这是附录 B 中 C7 的前置问题；
- 本地快照 `kind=iface` 与线上 bundle 不一致的问题，由谁修正。

## B8 M1 退出材料（0.5 天）

- 在附录 C 中补充 B 侧的执行记录：已完成任务、各项验收命令的输出摘要、探针结论，以及是否启用了退路方案。
- 列出 M5 的输入条件：
  - 应用层编译型依赖的交付路线（CI 按平台构建，或改用 `plugin/native`）；
  - stdio MCP 入口的拉起方式；
  - `rsi-toolkit` 与 `rsi-runtime` 两个应用的 bundle 结构；
  - `mint_distribution.py`、`mint_bootstrap.py` 如何迁到新构建器。

## 不做的事

- 不改 `service/` 下任何非 Mint 打包的源码（归 A 所有）。如果需要 A 配合，在同步点提出。
- 不改 `contracts/*.json` 的内容。
- 不登录 MintHub，不执行 publish，不使用 `agentcpm` scope。
- 不让任何用户侧步骤执行 pip；构建期也不需要 pip，因为首批包只依赖标准库。
