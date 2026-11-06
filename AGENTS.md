# DataAgent 工作约定

## 仓库

- 本仓库：DataAgent / FDE Agent 的能力包、方案与实施记录，GitHub `Eveosev/dataagent`（private）。
- 在 AgentOS 宿主（`Eveosev/agentos`）中以 submodule 挂载于 `domains/dataagent/`。
- 仓内路径与拆分前的 AgentOS 根一致：`packages/capabilities/dataagent-*`、`docs/research/dataagent-*`、`docs/research/fde-agent-2026-11-02`、`docs/design/dataagent-*-v0.1`。拆分前的提交与 tag 保留原 SHA（`fbe24d8`、`dataagent-runtime-0.1.0` → tag 对象 `20022e0a`）。

## 与 mint / iface 对比前，必须先确认 agent-kernel 是否为最新

agent-kernel 不在本仓库内；挂载于 AgentOS 时位于 `../../packages/agent-kernel`，只 pull、不提交。每次与 Mint（`agentcpm/iface-*` 制品、Mint CLI）或 iface 契约做对比、取证、出结论之前：

```bash
cd ../../packages/agent-kernel
git fetch origin --prune
test "$(git rev-list --count HEAD..@{u})" -eq 0 || git pull --ff-only
bash scripts/sync-iface-packages.sh --check
```

- `--check` 失败说明 `packages/iface-*` 与 `kernel/iface/src` 漂移，以 `kernel/iface/src` 为准。
- 结论中记录 `agent-kernel@<git rev-parse HEAD>`。
- iface 契约位置见 AgentOS `README.md`「iface 契约：位置与对比流程」。

## 文档位置

- 当前设计与实施：`docs/research/dataagent-2026-11-03/`，入口 `README.md`；飞书为发布副本，链接见该 README 的文件表。
- 能力包：`packages/capabilities/dataagent-*`；包与方案文档的对应见本仓 `README.md`「能力包」。
- 历史版本（`docs/design/dataagent-*-v0.1/`、`docs/research/dataagent-2026-11-01/`、`docs/research/dataagent-2026-11-02/spec/`）不作为当前基线；v0.2 冻结在 `docs/research/dataagent-2026-11-02/sources/freeze-v0.2-2026-11-03/`。
- 计数以总 Catalog `catalog/atomic-capability-catalog.json` 为准（18 个模块 / 141 个能力组 / 458 项原子；S0 数据层 32 项）。

## 生成物

`00–04` 与 `catalog/` 为生成物，改 `tools/build.py` 后重新生成，不手改；细节见目录 `README.md`「生成与同步」。

## 写作

- 直接阐述：给定义、结构、表格；不写论证段、反面定义、口号式标题、元叙述与复述。
- 文档自身版本只写在文首 frontmatter；正文、标题、链接标签不写 `v0.x`、`rNNNN`、`本版`。飞书以文首 yaml 代码块表示。
- 不写指向本文档自身的链接。
- 设计面向通用能力；具体项目（如令才）只作为应用举例。
- 保留可核对的事实：路径、数字、`agent-kernel@<sha>`。
- 仓内文件用相对路径链接；仓外证据（如 `~/.dsh/state/…`）可用绝对路径。

## 实施与评审记录

- 方案文档只保留方案与记录索引；每轮修复、评审、优化方案写入方案同名目录（如 `06-data-layer-build/` 下 `rN-fixes.md`、`rN-review.md`、`rN-plan.md`），并在方案文档的索引表与目录 `README.md` 的文件表中登记。
- 新增文档编号前先 `ls` 确认编号未被占用。
- 评审结论区分“已修复 / 部分修复 / 新缺陷”，附复现输入与位置（`file:line`）；不以测试全绿代替结论。

## 飞书同步

- 推送前先拉取线上版本与本地比对，合并用户的线上修改后再推送；总规划只做定点替换与插入，不整篇覆盖。
- `lark-cli` 在沙箱内会 TLS 失败，需在沙箱外执行；`@file` 参数须为工作目录下的相对路径。

## Git

- 主干 `main`；分支 `feat/<方案号>-<主题>`、`fix/<方案号>-rN`。
- 提交信息 `type(scope): 摘要`；轮次沿用 `fix(12-cli-build): rN — …`。
- 包发布 tag `<包名>-<semver>`（如 `dataagent-runtime-0.1.0`）；冻结 `freeze/<名>-<日期>`。
- 推送后在 AgentOS 宿主固定：`git add domains/dataagent && git commit -m "chore(dataagent): bump to <sha12> — <摘要>"`。
- 制品（`*.mint.tar.zst`、`*.whl`、源码归档）不再新增入库；发布到 MintHub 或 Release，仓内只留 digest。
