# RSI cpmrt transport 接入需求（M6 输入）

> 状态：M6 需求基线，未实施。本文只定义 M6 的接入边界、验收要求和不得声明的事项；
> M1 仍使用 `mint run --json`，不因本文改变 M1 的验收结论。

## 1. 触发条件与事实基线

2026-10-28 外部 cpmrt 已发布 **0.1.14（std 档）**，本机可验证：

| 事实 | 证据 |
| --- | --- |
| `cpmrt 0.1.14` 可执行 | `~/.mint/bin/cpmrt -> ~/.mint/cores/0.1.14-std/bin/cpmrt`；`cpmrt --version` 输出 `cpmrt 0.1.14` |
| 0.1.14 只有 std 制品 | `mint core install core@0.1.14` 失败：`mint/core@0.1.14 没有 core-aarch64-apple-darwin 制品`；`std@0.1.14` 安装成功 |
| 制品可校验 | 30,053,210 B，`sha256:3f4668ae0d5aa49dc6db0f3519f95d7af42f424ea852d5e8c2b4f4ad84941cdc`，minisign 验签通过 |
| ABI/能力 | `cpmrt info --json`：ABI 1，features 含 `tools/skills/approval/jsonl-sessions/mcp` |
| 档位不一致 | `std@0.1.14` 制品内的 `cpmrt info` 自报 `build_flavor: core`；项目锁 `std` 时 `mint run` 报“此二进制不支持请求档位 std（编译档位 core）”，但直接 `cpmrt run --flavor core` 可读取已安装 SKILL（`core_version=0.1.14`） |
| Mint CLI 不变 | `mint 0.1.11`；CLI 与 Core/cpmrt 版本分别记录 |

上述档位不一致是 0.1.14 的已知边界，不能靠改项目 lock 或包装脚本来掩盖。M1 仍用
`core@0.1.6` 的 `mint run` 证据；0.1.14 只作为 M6 的直接运行/ACP 输入。

`cpmrt` 已具备 ACP 服务、headless `run`、loop 宿主和契约自述面（`_mint/contract`、
`_mint/session/list`、`_mint/context/usage`、`_mint/agents/*`）。但它**仍没有
`_mint/model/*` 方法**；有效模型来自 `_mint/session/info#info.model`。因此本需求
不把 cpmrt 当作 `iface-model` 的 callable transport。

## 2. 范围

M6 只做一件事：在 M4 的 `RuntimeExecutor` 语义之上新增 cpmrt 适配器，并用独立证据
证明执行、取消、断连、重启和隔离与 M4 同等。它不重做 M1 的模块拆分，不改
`rsi-evaluation`/`rsi-foundation` 的公共 API，不替换 M1 的 `mint run` 入口。

进入条件：

1. M4 退出评审通过，`RuntimeExecutor` 的提交/取消/恢复语义已冻结。
2. 存在可安装、可验签的 cpmrt 稳定制品；当前为 `std@0.1.14`，只接受显式版本，
   不接受 `stable` 漂移。
3. 已记录 cpmrt 的 ABI、CLI 版本、制品 sha256、平台和事件协议 fixture。

## 3. 必须满足的需求

### 3.1 版本与启动

- 适配器必须显式固定 `cpmrt 0.1.14` + `std`，记录二进制路径、sha256、ABI 和
  `cpmrt --version`；不得跟随 `stable` 自动升级。
- 只通过 `cpmrt acp`（stdio）或 `cpmrt run --json` 启动；用户侧不执行 pip，不修改
  Python `sys.path`，不读取个人 provider 凭据。
- 启动环境使用白名单（PATH/HOME/TMPDIR/LANG/MINT_HOME），记录 argv、cwd、退出码；
  子进程必须可取消、可回收，超时和信号路径有测试。

### 3.2 契约映射

- 会话/回合/取消/状态映射到 cpmrt 的 ACP 方法；不得虚构 `_mint/model/*` 或把
  `iface-model` 声明为已接通。
- 模型能力只从 `_mint/session/info#info.model` 读取，必须允许 `None`/未知，并在
  报告中标注“运行时已知模型”，不把它冒充 `iface-model` 的完整契约实现。
- `_mint/contract` 的自述结果作为运行时能力检查输入；缺方法返回 `available:false`，
  形状错误必须拒绝，不拿残缺自述开控件。

### 3.3 事件与恢复

- ACP/JSONL 事件必须按实际顺序记录并校验：会话开始、回合、工具调用/更新、文本/思考、
  结束/取消；不得用最终文本或单个 `done` 代替执行证据。
- 相同 ID 重复 submit 不得重放；取消、断连、进程重启后的结果必须是显式的
  `Unknown`/失败，而不是猜测成功。
- 断连/重启后工作区、代理、事件完整性必须与 M4 同等；事件 fixture 带版本标记。

### 3.4 证据与门

- 新增 `conformance/cpmrt-m6/`：`acceptance.md`、`acceptance.json`、命令记录、
  事件 fixture、负例（缺依赖/取消/断连/重启/tamper）和版本证据。
- 每个结论绑定 cpmrt 制品 sha256、ABI、提交和运行日期；不得用 M1 的 Mint 证据
  替代 M6 证据。
- 退出条件：M4 同等执行/隔离标准 + 独立复核；未满足时 M6 保持未开始，不写
  “cpmrt 兼容”。

## 4. 明确不做

- 不做 native MCP 生产接入（M5 的 probe 不等于 M6）。
- 不发布 MintHub、不接真实模型 provider、不宣称学习收益或性能提升。
- 不把 `cpmrt` 的 ACP 契约自述当成 RSI 五个包的 IFace 契约已经可调用。
- 不在 M1 分支上实现 M6；M1 的 cpmrt 边界只记录“0.1.14 可用、未接”。

## 5. 与 M1 的关系

M1 的 workspace G4-W 仍用 `mint run --json` + `core@0.1.6` 验证 scripted
skill_read 和安装态调用；cpmrt 0.1.14 只用直接 `cpmrt run --flavor core` 记录
就绪证据，不进入 M1 的 `mint run` 结论。M1 报告必须分别列“M1 已验证的
Mint 0.1.11/core 0.1.6 运行证据”和“cpmrt 0.1.14 直接运行/ACP 未接入”，
不得把前者写成后者。
