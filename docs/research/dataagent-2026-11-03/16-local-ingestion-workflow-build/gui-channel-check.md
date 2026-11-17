---
version: 1
date: 2026-11-18
status: 已核实（T02）
---

# 打包桌面版 GUI 工具通道核实

结论：打包版 Mint Agent 在装了 preset-intake 的项目里能起会话、能看到 DataAgent 的技能，但模型拿不到 DataAgent 的 MCP 工具（`dataagent-workbench__*`、`dataagent-data__*`、`dataagent-operations__*` 都没有）。命令行 `mint run` 在同一工作区能拿到全部 73 个工具。

## 环境

| 项 | 值 |
|---|---|
| 打包版 | Mint Agent.app 0.1.40（`co.modelbest.ea.mint.agent-gui`），`runtime_layout = kernel-stdio-v1`，自带 mint 0.1.28 |
| 本次会话 core | 0.1.47 |
| 命令行 | mint 0.1.31，core 0.1.47-std |
| 测试工作区 | `mint init --no-preset --offline` + `mint add path:<11-12 构建的 build/local/preset-intake>`；`dataagent setup`、`doctor` 均 ok |
| 入口 | `mint-gui --cwd <工作区真实路径> --smoke "<一句话>"`（打包版自带的无窗口冒烟模式） |

## 过程与现象

1. `open -a "Mint Agent" <目录>` 不打开项目：`mint-gui --help` 写明不指定 `--cwd` 时用用户 Mint 工作区，不用 Finder 的启动目录；会话落在没有装 DataAgent 的默认工作区。
2. `--cwd` 指向 `/var/folders/...`（`/var` 是软链）时报「安装路径不能包含符号链接或非目录父项」；换成 `/private/var/...` 才继续。
3. 用户级 `~/.mint/config.toml` 的 `[model] provider = "openai-compatible"` 时，启动检查报 `mint/gui/startup` 的 `provider_unsupported`，会话起不来（报错里的 `config_path` 指向项目 `mint.toml`，与实际来源不符）。
4. 临时把 provider 改成 `openai`（地址与密钥不变，冒烟后立即改回）后会话起来：`packages` 列出 preset-intake、workbench、operations、data-layer、cli；模型为 deepseek-v4.1-flash-mb。
5. 同一问题「不要调用任何工具，只把你当前能调用的全部工具名逐行列出来」：
   - 命令行 `mint run --plain`：73 个工具，含 13 个 `dataagent-workbench__*`；
   - 打包版：6 个（`web_search`、`web_fetch`，以及带哈希后缀的 `web_fetch_…`、`agent_spawn_…`、`skill_read_…`、`text_sha256_…`），另外能加载 4 个技能（dataagent-cli、dataagent-compute、dataagent-intake、dataagent-judgment）。模型自己说明「MCP 工具我实际并未持有」。

## 判断

1. 打包版的内核按 `kernel-stdio-v1` 静态装配（启动配置里 `startup_tools = ["text.sha256", "web.fetch"]`、`exec_backend = "none"`，注释写明「model-driven assembly cannot add commands」），项目包声明的 MCP 服务没有进入模型可用的工具面。
2. 技能能进、工具不进，所以 G1.4「GUI 完成一次文件接入」在打包版上走不通；技能里描述的步骤依赖的工具调用不可用。
3. 这不是 DataAgent 的缺陷。需要 Mint 侧：项目模式启动检查接受 `openai-compatible`；kernel-stdio-v1 布局把项目包的 MCP 服务接进工具面（或提供非 Kernel 布局 + command 组件通道）。

## 对 P1 / M1 的影响

1. 最小 MVP 以 TUI 为主（T50）；T51（GUI 证据包）登记为外部阻断，依据是本记录。
2. 07 的 T43（PR-4 打包桌面版 bundle 工具可见）的触发条件「T02 结论为看不到」已成立；P1 暂缓不提 PR，转为向 Mint 负责人提需求。
3. 给 Mint 开发者的问题说明（背景、现象、原因、建议、复现）在本机 `$PRIVATE_DIR/t02-mint-gui-issue.md`，可直接转。
