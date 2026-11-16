# DataAgent 工作约定

## 仓库

- 本仓库：DataAgent / FDE Agent 的能力包、方案与实施记录，GitHub `Eveosev/dataagent`（private）。
- 在 AgentOS 宿主（`Eveosev/agentos`）中以 submodule 挂载于 `domains/dataagent/`。
- 仓内路径与拆分前的 AgentOS 根一致：`packages/capabilities/dataagent-*`、`docs/research/dataagent-*`、`docs/research/fde-agent-2026-11-02`、`docs/design/dataagent-*-v0.1`。拆分前的提交与 tag 保留原 SHA（`fbe24d8`、`dataagent-runtime-0.1.0` → tag 对象 `20022e0a`）。

## 与 mint / iface 对比前，必须先确认 agent-kernel 是否为最新

agent-kernel 不在本仓库内，只 pull、不提交：在 agentcpm-os 宿主下位于 `../../upstream/agent-kernel`，在 AgentOS 宿主下位于 `../../packages/agent-kernel`。每次与 Mint 或 iface 契约做对比、取证、出结论之前：

```bash
cd <宿主里的 agent-kernel>
git fetch origin --prune
test "$(git rev-list --count HEAD..@{u})" -eq 0 || git pull --ff-only
git rev-parse HEAD
```

- 契约以 `kernel/iface/src/` 为准，身份包在 `products/iface-identity/`；`packages/iface-*` 已停止维护，不作基线；`scripts/sync-iface-packages.sh --check` 已停用，不再运行。
- 结论中记录 `agent-kernel@<git rev-parse HEAD>`。
- 向 agent-kernel 提 PR 的规矩见 `docs/dataagent/03 平台方案与 iface 共建.md` §8。

## 文档位置

- 现行文档集：`docs/dataagent/`（00 术语与总览 → 07 MVP 实施文档），用 bigproj 发布到飞书；P1 任务清单见 `07 MVP 实施文档.md`。

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

## bigproj（agentcpm-os）

本仓库同时挂在 AgentOS（`domains/dataagent`）和 agentcpm-os（`projects/dataagent`）下，两边规则见各自宿主的 AGENTS.md「双宿主规则」。在 agentcpm-os 下工作时，宿主指针的 bump 写在 agentcpm-os 仓库里。下面三个块由 bigproj 维护，不要手改。

<!-- bigproj:stage begin -->
## 当前阶段

MVP 实施（2026-11-17 起）。下一步：MVP 实施文档定稿后，把分步清单登记成开发交付，进入开发。
<!-- bigproj:stage end -->

<!-- bigproj:links begin -->
## 文档与看板

| 名称 | 本地 | 飞书 |
|---|---|---|
| 文档集首页 | docs/dataagent/README.md | https://modelbest.feishu.cn/wiki/WCXwwJIatirPtXkCF8gcV7x9nme |
| 工作表（功能拆解、裁决清单） | — | https://modelbest.feishu.cn/wiki/Ah8MwzzwliTB8FkWXUlcHiwVnpd |
| 开发交付（本子项目视图） | — | https://modelbest.feishu.cn/wiki/FDIPwTuQci1FY7kiQ6GccbG8nDe?table=tbl3i9VGaRruX7b5&view=vewlcx9Npd |
| workspace 项目首页 | — | https://modelbest.feishu.cn/wiki/DlRpwgNlSiwMHRk3xHGcZdZBnWd |
<!-- bigproj:links end -->

<!-- bigproj:core-rules begin -->
## 核心规则（摘自 workspace，v1，由 bigproj 维护，不要手改）

- 本项目属于 workspace「agentcpm-os」（~/Vibe/AgentCPM-OS）；通用规则在它的 AGENTS.md，会话不在 workspace 里启动时先读一遍。
- 叙述类文档以 docs/dataagent/ 下的本地 Markdown 为源，用 bigproj publish 发布到飞书；不在飞书上直接写正文。
- 只在主分支、合并后 publish；worktree 里只写本地稿。发布提示「飞书端已被修改」时先合回本地，不要强行覆盖。
- 文档之间用相对路径互链；不要改各篇头部的 doc_id 和 feishu_node、feishu_obj。
- 新篇按读法顺序编号，一篇回答一个问题；提需求的原话放「附B 原始诉求」，不改写。
- PRD 的每个目标（G）对应一条验收指标（V）；待拍问题记 Q，用 bigproj decisions 汇总到裁决清单。
- 按 原始诉求 → 调研与设计 → 分期与 PRD → MVP 实施 → 开发 → 验收 推进；每步由人确认后用 bigproj stage 进入下一步。
- 开发交付只改自己负责的行并写会话名；验收状态由人改。发布、删除、申请资源、对外发消息先征得人确认；飞书页面不删除，只归档。
<!-- bigproj:core-rules end -->
