# RSI Toolkit MintHub 发布与 Mint Agent 调用实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 RSI Toolkit 的 Mint 控制包、运行时包和 Skill 发布为可从 MintHub 安装的 registry 包，使 Mint 控制 Agent 能通过 `self-evolve` Skill 调用 RSI 服务执行、查看和审查进化任务。

**Architecture:** MintHub 负责分发 `skill`、`mcp` 和 `bundle` 包；RSI Python sidecar 继续作为独立服务运行。发布层保留五个可独立校验和升级的制品，但用户入口只有两条：控制工程安装一个 `rsi-toolkit` bundle（由 registry 自动拉取控制 MCP 和 `self-evolve` Skill），被评估的运行时工程安装一个 runtime 组合（由 registry 自动拉取 `rsi-runtime` 和 `learned-assets`）。包安装后通过环境变量连接已启动的 RSI 服务，发布和 operator approval 仍留在可信服务侧。

**Tech Stack:** Mint CLI/Core、MintHub registry、TOML package manifests、Python 3.13 RSI service、官方 MCP SDK stdio-to-streamable-HTTP bridge、现有 Mint conformance probes。

**Spec:** [docs/dev/rsi_toolkit/plugin-architecture.md](/Users/payne/Vibe/AgentOS/apps/plugins/rsi-toolkit/docs/design/plugin-architecture.md)、[docs/mint/README.md](/Users/payne/Vibe/AgentOS/docs/mint/README.md)、[apps/plugins/rsi-toolkit/docs/design/mint-report.md](/Users/payne/Vibe/AgentOS/apps/plugins/rsi-toolkit/docs/design/mint-report.md)。

## Global Constraints

- 首次公开包必须使用已拥有并验证过的 MintHub scope；`local/` 只能继续用于本地开发，不能作为发布命名空间。
- 所有 registry 依赖必须使用已发布的 scope/name/version，不能保留相对路径依赖；包版本发布后不可覆盖，只能递增版本。
- 包、lock、README、测试输出和证据中不得出现模型 Key、MintHub token、RSI agent/operator/runtime token 或 Bearer 值。
- `rsi-control` 和 `self-evolve` 只能安装在控制工程；评估工程只能安装 `rsi-runtime` 和 `learned-assets`。
- 第一阶段明确声明 Python RSI sidecar 需要预先启动；在 Mint Core 能可靠托管 sidecar 前，不宣称 `mint add` 会自动启动服务。
- 当前实测基线是 Mint CLI 0.1.10、Core 0.1.6、Python 3.13；发布前必须重新记录目标机器的实际版本。
- `rsi-toolkit` 继续使用 AGPL-3.0-only，并随包保留 LICENSE、ORIGIN 和 THIRD_PARTY_NOTICES 的来源信息。
- 只有干净工程完成安装、Skill 加载、MCP 调用和真实服务返回结构化结果后，才标记为 MintHub 可消费。
- 五个 registry 制品是维护和权限边界；控制用户不得被要求手工安装五次，文档默认只展示 `mint add "$MINT_SCOPE/rsi-toolkit@$RSI_RELEASE_VERSION"`。

## Review Focus

- registry 发布拒绝 path-only dependency：在 manifest 和 lock 中验证依赖全部解析到同一 owned scope 的固定版本。
- Core 0.1.6 不直接启用 streamable-http：验证 bundle 安装后是否能自动注册 bridge；若不能，交付必须包含可复制的 post-install setup，不得声称单条 `mint add` 已接通 MCP。
- 控制面与运行时隔离：运行时工程不能获得 `evolution__run`、`publish` 或 operator approval 能力。
- Skill 调用入口：先用实际 CLI help 确认是否存在 `mint agent`/`--skill`；若不存在，使用当前支持的 `mint chat`/headless 路径并在文档中写出实测命令。
- 可复现的升级与失败行为：锁定安装、缺失环境变量、错误服务 URL、服务停止、卸载和版本升级都必须有可解释结果。

## File Map

- Modify: `apps/plugins/rsi-toolkit/plugins/mint/rsi-control/mint.toml` — registry MCP 包名称、固定 API/依赖版本和能力声明。
- Modify: `apps/plugins/rsi-toolkit/plugins/mint/rsi-runtime/mint.toml` — registry runtime MCP 包名称和只读能力声明。
- Modify: `apps/plugins/rsi-toolkit/plugins/mint/self-evolve/mint.toml` and `SKILL.md` — registry Skill 元数据、实际工具调用说明和用户可见触发语句。
- Modify: `apps/plugins/rsi-toolkit/plugins/mint/learned-assets/mint.toml` and `SKILL.md` — registry runtime Skill 元数据和 recall 说明。
- Modify: `apps/plugins/rsi-toolkit/plugins/mint/rsi-toolkit/mint.toml` and `README.md` — registry bundle 依赖、控制/运行时安装边界和 bridge/service 前置条件。
- Modify: `apps/plugins/rsi-toolkit/plugins/mint/install.py` — 保留本地安装兼容性，并在 registry 消费路径需要时支持无源码 checkout 的 bridge 安装。
- Create: `apps/plugins/rsi-toolkit/service/toolkit/mint_install.py` and modify `apps/plugins/rsi-toolkit/service/toolkit/cli.py` — 在已安装的 RSI service wheel 中提供 `rsi-toolkit mint-install`，使 registry 用户无需源码 checkout 也能完成 Core 0.1.6 bridge 注册。
- Create: `apps/plugins/rsi-toolkit/conformance/mint/registry-install-probe.py` — 在 disposable `MINT_HOME` 和干净 Mint 工程中执行 registry 安装、验证、Skill/MCP 调用和控制/运行时隔离检查。
- Create: `apps/plugins/rsi-toolkit/conformance/mint/registry-release-manifest.json` — 记录包名、版本、依赖、源文件哈希、构建产物哈希、CLI/Core 版本和测试证据引用；不写入任何凭据。
- Modify: `apps/plugins/rsi-toolkit/README.md` and `apps/plugins/rsi-toolkit/plugins/mint/rsi-toolkit/README.md` — 发布后的安装、服务启动、环境变量、调用和卸载说明。
- Modify: `docs/mint/README.md` and `docs/dev/rsi_toolkit/mint-report.md` — MintHub 发布结果、已知 Core 限制和真实消费证据。

## Task 1: 冻结 MintHub 包拓扑和版本

**Files:**
- Read: `apps/plugins/rsi-toolkit/plugins/mint/*/mint.toml`
- Read: `docs/mint/README.md:187-245`
- Create: `apps/plugins/rsi-toolkit/conformance/mint/registry-release-manifest.json`

**Interfaces:**
- Consumes: MintHub owned scope、当前 CLI/Core 版本、现有五个本地 Mint package manifests。
- Produces: 一张固定的 registry package matrix，供后续 manifest 修改、发布顺序和 clean install 使用。

- [ ] **Step 1: 检查发布身份和 CLI 支持**

运行：

```sh
mint --version
mint core info
mint --help
mint add --help
mint pack --help
mint publish --help
mint agent --help
```

记录实际支持的 `mint agent`、Skill 选择参数、package hooks/entrypoint 和 registry endpoint。若 `mint agent` 不存在，记录当前可用的 `mint chat` 或 headless 命令作为唯一验收入口。

- [ ] **Step 2: 确认 owned scope 和未占用版本**

在 MintHub 控制台确认发布 scope、`publish-new`/`publish-update` 权限及五个包名是否已存在。将解析结果写入 release manifest 的 `scope`、`packages`、`publish_order` 和 `compatibility` 字段；不把 token 写入文件。

- [ ] **Step 3: 固定包拓扑**

采用以下拓扑。Task 1 完成后设置 `MINT_SCOPE` 和 `RSI_RELEASE_VERSION`，后续命令直接使用这两个变量：

| 包 | kind | 依赖/用途 |
|---|---|---|
| `$MINT_SCOPE/rsi-control` | `mcp` | 控制工具，连接 `/mcp/control` |
| `$MINT_SCOPE/self-evolve` | `skill` | 调用 control MCP 的 Skill |
| `$MINT_SCOPE/rsi-toolkit` | `bundle` | 聚合 `rsi-control` + `self-evolve` |
| `$MINT_SCOPE/rsi-runtime` | `mcp` | 只读 recall，连接 `/mcp/runtime` |
| `$MINT_SCOPE/learned-assets` | `skill` | 调用 runtime recall 的 Skill |

控制 bundle 和运行时组合保持分离，不能用一个 bundle 同时授予控制和 runtime 权限。

- [ ] **Step 4: 验证并提交 release manifest**

运行：

```sh
python -m json.tool apps/plugins/rsi-toolkit/conformance/mint/registry-release-manifest.json
```

确认每个包有明确 owner、版本、license、API 兼容范围、发布顺序和 clean install 入口后提交一次独立变更。

## Task 2: 把本地包转换为 registry-ready manifests

**Files:**
- Modify: `apps/plugins/rsi-toolkit/plugins/mint/rsi-control/mint.toml`
- Modify: `apps/plugins/rsi-toolkit/plugins/mint/rsi-runtime/mint.toml`
- Modify: `apps/plugins/rsi-toolkit/plugins/mint/self-evolve/mint.toml`
- Modify: `apps/plugins/rsi-toolkit/plugins/mint/learned-assets/mint.toml`
- Modify: `apps/plugins/rsi-toolkit/plugins/mint/rsi-toolkit/mint.toml`
- Test: `apps/plugins/rsi-toolkit/conformance/mint/registry-install-probe.py`

**Interfaces:**
- Consumes: Task 1 的 scope、版本和 package matrix。
- Produces: 五个不含 path dependency、可被 MintHub 解析的 package 目录，以及 `load_manifests(root)`/`assert_registry_ready(manifests, scope, version)` 两个 probe helper。

- [ ] **Step 1: 写 registry metadata 失败检查**

在 `registry-install-probe.py` 中先写可独立运行的 manifest parser 和失败断言：

```python
def assert_registry_ready(manifests, scope, version):
    assert all(item["package"]["name"].startswith(scope + "/") for item in manifests.values())
    assert all("path" not in dependency for item in manifests.values()
               for dependency in item.get("dependencies", {}).values())
    assert set(manifests["rsi-toolkit"]["dependencies"]) == {scope + "/rsi-control", scope + "/self-evolve"}
    assert all(item["package"]["version"] == version for item in manifests.values())
```

先运行 probe，确认当前 `local/` 名称和相对 path dependency 被报告为失败；manifest 修改后同一断言必须通过。

- [ ] **Step 2: 修改包名和固定依赖**

将 `local/*` 替换为 Task 1 解析出的 owned scope 名称；将 bundle 依赖改为已发布包的精确版本或 MintHub 支持的最窄兼容范围。保留 `api` 兼容约束、AGPL license、MCP URL 环境变量和 capability reason。

- [ ] **Step 3: 验证包内容边界**

检查 `rsi-control` 包只包含 MCP manifest 和 bridge 所需的公开代码，`self-evolve` 只包含 Skill；确认没有 service state、模型配置、私有 benchmark、凭据或用户项目路径进入包。

- [ ] **Step 4: 运行本地 pack/manifest 检查**

运行：

```sh
mint --offline --json pack apps/plugins/rsi-toolkit/plugins/mint/rsi-control --out /private/tmp/rsi-control-pack
mint --offline --json pack apps/plugins/rsi-toolkit/plugins/mint/rsi-runtime --out /private/tmp/rsi-runtime-pack
mint --offline --json pack apps/plugins/rsi-toolkit/plugins/mint/self-evolve --out /private/tmp/self-evolve-pack
mint --offline --json pack apps/plugins/rsi-toolkit/plugins/mint/learned-assets --out /private/tmp/learned-assets-pack
mint --offline --json pack apps/plugins/rsi-toolkit/plugins/mint/rsi-toolkit --out /private/tmp/rsi-toolkit-pack
```

预期：四个叶子包 pack 成功；bundle 不再因为 path-only dependency 被拒绝。若 bundle 仍被拒绝，先修正依赖版本，再进入发布阶段。

## Task 3: 解决 Mint Core 的 MCP bridge 消费路径

**Files:**
- Modify: `apps/plugins/rsi-toolkit/plugins/mint/install.py`
- Modify: `apps/plugins/rsi-toolkit/plugins/mint/rsi-toolkit/README.md`
- Create: `apps/plugins/rsi-toolkit/service/toolkit/mint_install.py`
- Modify: `apps/plugins/rsi-toolkit/service/toolkit/cli.py`
- Create/Modify: `apps/plugins/rsi-toolkit/conformance/mint/registry-install-probe.py`

**Interfaces:**
- Consumes: Mint Core 对 bundle `.mcp.json`、package hooks、native/plugin entrypoint 和环境变量展开的实际行为。
- Produces: 一条可复现的 registry 安装后 MCP 调用路径；若 Core 不支持自动 bridge，明确的两步安装路径。

- [ ] **Step 1: 先验证原生自动注册能力**

在 disposable 工程中执行（`MINT_SCOPE` 和 `RSI_RELEASE_VERSION` 来自 Task 1 的实际 registry 结果）：

```sh
mint init /private/tmp/rsi-mint-registry-probe --name "$MINT_SCOPE/rsi-probe" --no-preset
mint --registry https://mint-hub.ea.modelbest.co add "$MINT_SCOPE/rsi-toolkit@$RSI_RELEASE_VERSION"
mint verify
mint tree
```

检查包安装后 `.mcp.json`、Skill 目录、lock 和实际 Core MCP server 列表。不要把“manifest 被接受”当作“工具已可调用”。

- [ ] **Step 2: 如果 Core 支持 hooks/entrypoint，改为 declarative setup**

将 bridge 放入可分发包，使用 Mint 支持的相对路径和 `python`/native entrypoint；bridge 只读取 `RSI_CONTROL_MCP_URL`、`RSI_AGENT_TOKEN`，不读取源码 checkout，不嵌入 token。新增 probe 断言 bridge 进程可以启动、发现 `evolution__capabilities` 并转发一次 `evolution__catalog`。

- [ ] **Step 3: 如果 Core 仍不支持 HTTP MCP 自动桥接，保留 post-install setup**

保持 `install.py` 为 registry 消费后的 setup 命令：从已安装包或可复制资源取得 bridge，写入项目 `.mint/rsi-transport/bridge.py`，合并 `.mcp.json`，保留其他 server，拒绝 symlink 目标，并将 URL/token 只写成 `${...}` 引用。README 明确写出：

```sh
mint add "$MINT_SCOPE/rsi-toolkit@$RSI_RELEASE_VERSION"
rsi-toolkit mint-install --project /absolute/project --python /absolute/python --yes
```

`rsi-toolkit mint-install` 必须从已安装 wheel 的资源复制 bridge，不能从源码 checkout 读取文件；它只能修改目标工程的 `.mint/rsi-transport/bridge.py` 和 `.mcp.json`。如果目标 Core 后续支持 declarative bridge，则保留该命令作为兼容入口，并在 probe 中确认两条路径的行为一致。

- [ ] **Step 4: 添加失败边界测试**

覆盖缺失 URL、缺失 token、错误 endpoint、已有不相关 `.mcp.json` server、symlink `.mcp.json`、runtime 工程存在 control 包和 bridge 启动失败；所有错误都应在安装阶段或 MCP 调用阶段明确返回。

## Task 4: 固定 RSI service 的分发和运行前置条件

**Files:**
- Read/verify: `apps/plugins/rsi-toolkit/service/pyproject.toml`
- Modify: `apps/plugins/rsi-toolkit/service/toolkit/cli.py`
- Create/Modify: `apps/plugins/rsi-toolkit/service/toolkit/mint_install.py`
- Modify: `apps/plugins/rsi-toolkit/README.md`
- Modify: `apps/plugins/rsi-toolkit/plugins/mint/rsi-toolkit/README.md`
- Modify: `docs/mint/README.md`
- Modify: `apps/plugins/rsi-toolkit/conformance/mint/registry-release-manifest.json`

**Interfaces:**
- Consumes: 现有 `rsi-toolkit serve --config`、`/mcp/control`、`/mcp/runtime` 和 Python wheel 构建入口。
- Produces: Mint 包与 sidecar 的明确版本关系、启动命令、health/readiness 检查和停止语义。

- [ ] **Step 1: 构建服务制品**

运行：

```sh
cd apps/plugins/rsi-toolkit/service
uv build
python -m zipfile -l dist/*.whl
```

确认 wheel/sdist 含 `control`、`connectors`、`benchmarks`、`toolkit`、`toolkit.mint_install`、bridge 资源、公开 benchmark 数据、LICENSE 和第三方声明，不含 state、evidence、token 或用户项目文件。

- [ ] **Step 2: 固定 sidecar 启动合同**

文档必须给出完整流程：创建 Python 3.13 环境、安装 wheel、生成外部 state/config、设置三类 token、启动 `rsi-toolkit serve`、检查 `/health` 和 `/ready`、设置 Mint 环境变量、停止服务。说明 readiness 不代表 provider/host 已连通。

- [ ] **Step 3: 明确单服务和多 target 边界**

要求控制工程只绑定一个 target-scoped agent token；operator token 不进入 Mint 子进程；runtime 工程只能使用 runtime token。记录 service package 版本与 Mint package 版本的兼容矩阵。

## Task 5: 完成 Skill 调用体验和 Mint Agent 入口

**Files:**
- Modify: `apps/plugins/rsi-toolkit/plugins/mint/self-evolve/SKILL.md`
- Modify: `apps/plugins/rsi-toolkit/plugins/mint/learned-assets/SKILL.md`
- Modify: `apps/plugins/rsi-toolkit/plugins/mint/rsi-toolkit/README.md`
- Modify: `apps/plugins/rsi-toolkit/conformance/mint/registry-install-probe.py`

**Interfaces:**
- Consumes: Task 3 的实际 MCP server ID、Task 4 的服务 URL/token 环境变量和 CLI 可用入口。
- Produces: 用户可以明确指定 `self-evolve` Skill，并看到真实 RSI run 的结构化状态。

- [ ] **Step 1: 固定 Skill 触发语义**

在 `self-evolve/SKILL.md` 中写明：用户说“使用 self-evolve skill 运行 RSI”“对指定 target 做一轮 default/OPRO 进化”时，先调用 `evolution__capabilities`、`evolution__datasets`、`evolution__catalog`，再调用 `evolution__run`；禁止请求 operator token，禁止把 `publish` 请求当成已发布。

- [ ] **Step 2: 验证显式 Skill 选择**

按 Task 1 记录的实际 CLI 命令执行一次显式 Skill 调用。若 CLI 支持 `--skill self-evolve`，将该命令写入 README；若不支持，使用已验证的 Skill loader/`mint chat` 路径，并在 prompt 中明确写“使用 `self-evolve` Skill”。不发明未经验证的 `mint agent` 参数。

- [ ] **Step 3: 运行真实 control 调用**

启动本地服务后让 Mint Agent 完成只读链路：

```text
使用 self-evolve skill，读取当前 RSI target 的 capabilities、datasets 和 catalog，报告可用 learner；不要启动实验。
```

记录 MCP tool call、结构化返回、模型使用量和最终文本。随后执行一次受限的 `run`，轮询 `status`，调用 `review`，不自动调用 operator-only publish/apply。

- [ ] **Step 4: 验证 runtime 安全边界**

在第二个干净工程只安装 `$MINT_SCOPE/rsi-runtime` + `$MINT_SCOPE/learned-assets`，确认 `evolution_recall__recall` 可调用，而 `evolution__run`、`evolution__publish` 不可见或被拒绝。

## Task 6: 发布前验证、实际发布和 clean install 验收

**Files:**
- Modify: `apps/plugins/rsi-toolkit/conformance/mint/registry-install-probe.py`
- Modify: `apps/plugins/rsi-toolkit/conformance/mint/README.md`
- Modify: `apps/plugins/rsi-toolkit/docs/design/mint-report.md`
- Modify: `docs/mint/README.md`
- Update: `apps/plugins/rsi-toolkit/conformance/mint/registry-release-manifest.json`

**Interfaces:**
- Consumes: Tasks 1–5 的包、服务、Skill 和 bridge。
- Produces: 可复现的 MintHub release evidence，以及安装后真实调用结论。

- [ ] **Step 1: 做发布前干运行**

使用标准输入登录，不把 token 放进命令参数或日志：

```sh
mint --registry https://mint-hub.ea.modelbest.co login --token-stdin
mint publish apps/plugins/rsi-toolkit/plugins/mint/rsi-control --dry-run
mint publish apps/plugins/rsi-toolkit/plugins/mint/rsi-runtime --dry-run
mint publish apps/plugins/rsi-toolkit/plugins/mint/self-evolve --dry-run
mint publish apps/plugins/rsi-toolkit/plugins/mint/learned-assets --dry-run
mint publish apps/plugins/rsi-toolkit/plugins/mint/rsi-toolkit --dry-run
```

按依赖顺序发布叶子包，再发布 bundle；干运行输出必须显示 registry dependency，而不是 path dependency。

- [ ] **Step 2: 发布并核对包页**

实际上传前核对 scope、版本、license、README、依赖、capabilities、MCP server ID 和包内容。发布后在 MintHub 包页确认五个版本和依赖解析成功，记录包 URL、版本、归档 SHA-256 和发布时间。实际上传是不可覆盖的外部发布动作，使用发布者授权 token 执行。

- [ ] **Step 3: 从 registry 做锁定安装**

在新的 `MINT_HOME` 和新的控制工程中执行：

```sh
mint init /private/tmp/rsi-mint-clean --name "$MINT_SCOPE/rsi-clean" --no-preset
mint add "$MINT_SCOPE/rsi-toolkit@$RSI_RELEASE_VERSION"
mint verify
mint --locked install
```

若目标 CLI 支持离线缓存，再执行 `mint --frozen install`；否则记录不能离线复现的原因。检查 lock 中全部包来自 registry、没有 `local/` 或本机绝对路径。

- [ ] **Step 4: 运行完整 control/runtime 验收**

在 service 已启动且环境变量仅注入子进程所需 token 的情况下：

1. 控制 Agent 读取 `self-evolve` Skill 并调用 capabilities/datasets/catalog。
2. 控制 Agent 启动一轮小预算 default 或 OPRO run，并读取 status/review。
3. 运行时 Agent 只调用 recall 和 learned-assets。
4. 关闭 service 后验证调用失败明确，不会伪造成功或自动重放未知 run。
5. 升级到下一包版本后执行 `mint update --dry-run`、`mint --locked install`，确认旧 lock 和配置可解释。

- [ ] **Step 5: 生成证据并更新文档**

将命令、CLI/Core 版本、包版本、MCP 调用、失败边界、service 前置条件和已知限制写入 `registry-release-manifest.json`、`conformance/mint/README.md`、`docs/mint/README.md` 和产品 README。所有证据先执行 credential scan，再写入仓库或指定云盘。

## Verification Commands

最终合并前至少运行：

```sh
cd apps/plugins/rsi-toolkit/service
uv run pytest tests connectors/agentcpm/tests ../samples/synthetic-sql/tests -q
cd ..
python conformance/mint/check_skills.py
python conformance/mint/registry-install-probe.py --help
python evidence-viewer/scan-credentials.py .
```

在真实 registry 发布后，必须再次从干净工程执行 Task 6 的 lock install 和 Agent 调用；本地 pack 或 `publish --dry-run` 通过不能代替线上消费验收。

## Release Gate

发布交付必须同时满足：

- 五个包均有 owned scope、固定版本和 registry dependency；
- bundle 安装不会把 control 工具带入 runtime 工程；
- bridge/HTTP MCP 的实际调用经过真实 Core 验证；
- 指定 `self-evolve` Skill 能触发 capabilities、datasets、catalog、run、status、review 链路；
- service sidecar 的启动、停止、token 和 target scope 说明完整；
- clean install、升级、锁定安装、缺环境变量和服务不可用都有证据；
- 包、lock、README、日志和证据没有凭据；
- MintHub 包页、归档哈希、版本和 release manifest 相互一致。

