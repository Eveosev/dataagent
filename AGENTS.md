# AgentOS 工作约定

## 与 mint / iface 对比前，必须先确认 agent-kernel 是否为最新

`packages/agent-kernel` 是独立 git 仓库（origin 指向 `agent-kernel.git`），本目录不在其版本控制内，不会自动跟随上游。
因此**每次需要与 Mint（`agentcpm/iface-*` 制品、Mint CLI）或 iface 契约做对比、取证、出结论之前**，先执行：

```bash
cd packages/agent-kernel
git fetch origin --prune
test "$(git rev-list --count HEAD..@{u})" -eq 0 || git pull --ff-only
bash scripts/sync-iface-packages.sh --check
```

- 落后（`rev-list --count` 非 0）就先 `git pull --ff-only` 再对比；工作区脏时先处理脏文件，不要强拉。
- `--check` 失败说明 `packages/iface-*` 与 `kernel/iface/src` 漂移，以 `kernel/iface/src` 为准。
- 结论中记录 `git rev-parse HEAD`，便于复核。

## iface 契约位置

- 权威源：`packages/agent-kernel/kernel/iface/src/`
- 分发包（0.1.2，生成 + 校验）：`packages/agent-kernel/packages/iface-*`
- `packages/kernel-iface/`：0.1.0 历史冻结快照，已过时，**不得作为对比基线**，仅作 0.1.0 发布史证据（见其 `DEPRECATED.md`）。
- Mint Hub `agentcpm/iface-*@0.1.0`：早于两者内容，引用前核 digest。

详见根 `README.md` 的「iface 契约：位置与对比流程」。

## DataAgent / FDE Agent 文档

### 位置

- 当前设计与实施：`docs/research/dataagent-2026-11-03/`，入口 `README.md`；飞书为发布副本，链接见该 README 的文件表。
- 能力包：`packages/capabilities/dataagent-*`；包与方案文档的对应见根 `README.md`「DataAgent 能力包」。
- 历史版本（`docs/design/dataagent-*-v0.1/`、`docs/research/dataagent-2026-11-01/`、`docs/research/dataagent-2026-11-02/spec/`）不作为当前基线；v0.2 冻结在 `docs/research/dataagent-2026-11-02/sources/freeze-v0.2-2026-11-03/`。
- 计数以总 Catalog `catalog/atomic-capability-catalog.json` 为准（18 个模块 / 141 个能力组 / 458 项原子；S0 数据层 32 项）。

### 生成物

`00–04` 与 `catalog/` 为生成物，改 `tools/build.py` 后重新生成，不手改；细节见目录 `README.md`「生成与同步」。

### 写作

- 直接阐述：给定义、结构、表格；不写论证段、反面定义、口号式标题、元叙述与复述。
- 文档自身版本只写在文首 frontmatter；正文、标题、链接标签不写 `v0.x`、`rNNNN`、`本版`。飞书以文首 yaml 代码块表示。
- 不写指向本文档自身的链接。
- 设计面向通用能力；具体项目（如令才）只作为应用举例。
- 保留可核对的事实：路径、数字、`agent-kernel@<sha>`。

### 实施与评审记录

- 方案文档只保留方案与记录索引；每轮修复、评审、优化方案写入方案同名目录（如 `06-data-layer-build/` 下 `rN-fixes.md`、`rN-review.md`、`rN-plan.md`），并在方案文档的索引表与目录 `README.md` 的文件表中登记。
- 新增文档编号前先 `ls` 确认编号未被占用。
- 评审结论区分“已修复 / 部分修复 / 新缺陷”，附复现输入与位置（`file:line`）；不以测试全绿代替结论。

### 飞书同步

- 推送前先拉取线上版本与本地比对，合并用户的线上修改后再推送；总规划只做定点替换与插入，不整篇覆盖。
- `lark-cli` 在沙箱内会 TLS 失败，需在沙箱外执行；`@file` 参数须为工作目录下的相对路径。
