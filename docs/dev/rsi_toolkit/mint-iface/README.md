# rsi iface 契约包：生成与发布工具

> **2026-11-02 更新**：下文对比的 `packages/kernel-iface/publish-iface-online.sh` 所属快照已冻结为 0.1.0 历史版本；
> 现行发布脚本是 `packages/agent-kernel/scripts/publish-iface-mint-hub.sh`，生成/校验脚本是
> `packages/agent-kernel/scripts/sync-iface-packages.sh`。iface 契约以 `packages/agent-kernel/kernel/iface/src` 为权威源。

新版 M0-M1 单数据包入口见 [RSI v2 计划 T8](../../../superpowers/plans/2026-10-28-rsi-iface-v2-m0-m1.md#t8契约包bundle-构建与完整性算法)，产品生成器为 `packaging/contracts/build_iface_data.py`。本目录保留历史生成逻辑。

配套设计文档：[`../2026-10-28-iface-modularization-and-minthub.md`](../2026-10-28-iface-modularization-and-minthub.md)

这两个脚本只做一件事：把 `apps/plugins/rsi-toolkit/contracts/` 里**已冻结的 JSON Schema**
变成可直接 `mint publish` 的契约包，并保证 8 个包的形状不会各自漂移。

## 为什么需要生成器而不是手写 8 个目录

契约包的全部价值在于"形状一致、可被程序消费"。手写 8 份 `mint.toml` + README + SKILL.md，
第一次能对齐，第二次就漂了。脚本把"有哪些包"收敛到一张表（`PACKAGES`），
表里没有的包就不存在。

## 用法

```bash
# 0) 自检：哪些契约已有 schema、哪些还缺
python3 gen_contract_packages.py --check

# 输出：
# [OK ] rsi-iface-host       interface=rsi-host         schema=host.v1.json
# ...
# [TODO] rsi-iface-experiment interface=rsi-experiment   schema=None
# [TODO] rsi-iface-release    interface=rsi-release      schema=None

# 1) 生成（scope 必须是你在 MintHub 拥有的命名空间）
python3 gen_contract_packages.py --out /abs/release/rsi-iface \
  --scope agentcpm --version 0.1.0

# 2) 本地验证：逐包 pack
export MINT_HOME=/abs/scratch/mint-home          # 隔离，避免动 ~/.mint
for d in /abs/release/rsi-iface/rsi-iface-*; do
  mint --offline pack "$d" --out /abs/release/packed
done

# 3) 登录（令牌经 stdin；控制台令牌需勾选 publish-new + publish-update）
mint login

# 4) 本地检查（默认不上传，也不验证远端权限——不是验收）
./publish-rsi-iface.sh --dir /abs/release/rsi-iface --scope agentcpm

# 5) 真发布
./publish-rsi-iface.sh --dir /abs/release/rsi-iface --scope agentcpm --publish
```

## 消费侧怎么用（官方路径不是 `mint add`）

MintHub 官方文档对契约包的用法是**拉单元**，只写本机单元库，不改项目 `mint.toml`：

```bash
mint pull agentcpm/rsi-iface-recall        # 拉单元
mint info agentcpm/rsi-iface-recall        # 看 provides.interfaces
mint inspect agentcpm/rsi-iface-recall --abilities   # 官方文档写的发现命令
```

> ⚠️ **`--abilities` 在已发布的 mint 0.1.11 里不存在**（只有 `--remote`），`mint inspect --remote`
> 只输出 OCI annotations，不含 `provides`。所以当前可用的发现方式是 `mint info`，
> 或直接读安装后的 `.mint/packages/.../manifest.json` 的 `manifest.provides`。
> 详见设计文档 §3 的差异表。

## 生成出来的包长什么样

```
rsi-iface-recall/
├── mint.toml                          # kind="bundle" + provides.interfaces=["rsi-recall"]
├── README.md                          # 契约摘要 + 为什么不是 kind="iface" + 安装示例
├── schema.json                        # 逐字节复制自 contracts/rsi.recall.v1.json
└── skills/rsi-iface-recall/SKILL.md   # bundle 的硬性载荷（validate 要求）
```

## 三个必须知道的限制

1. **`kind = "iface"` 不能用。** 发布的 mint 0.1.11 拒绝该变体：

   ```
   unknown variant `iface`, expected one of `core`, `host`, `plugin`, `overlay`,
   `bundle`, `skill`, `mcp`, `preset`, `template`, `app`, `agent`
   ```

   所以生成器写 `kind = "bundle"`，用 `provides.interfaces` 表达契约身份。
   线上 10 个 `agentcpm/iface-*@0.1.0` 也是这个形态。等 `Kind::Iface` 进入发布通道后，
   只需把 `kind` 改回 `iface` 并去掉 `skills/` 载荷。

2. **`bundle` 必须有载荷。** 没有 `skills/` `commands/` `agents/` `hooks/` `.mcp.json`
   之一，validate 直接失败。这就是每份契约都带一个 `SKILL.md` 的原因。

3. **`keywords` 上限 5 个。** 生成器固定 4 个，别加。

## 发布脚本与 kernel-iface 版本的差别

| 项 | `packages/kernel-iface/publish-iface-online.sh` | 本脚本 |
| --- | --- | --- |
| 默认行为 | **直接发布** | **只 pack + dry-run** |
| 真上传 | 默认就是 | 需要显式 `--publish` |
| scope 校验 | 无 | 发布前比对每个包 `mint.toml` 的 scope |
| 本地 pack 预检 | 无 | 每包先 `pack`，结构问题本地暴露 |

发布是不可撤销的对外副作用（版本不可覆盖），不该由"忘了加参数"触发。

## 未实现（有意）

- 不生成 `rsi-iface-experiment` / `rsi-iface-release`：它们的 schema 还不存在。
  先补 `contracts/rsi.experiment.v1.json` 与 `rsi.release.v1.json`，再往 `PACKAGES` 里加两行。
- 不做签名：`mint publish` 自己用 minisign 签（`sig.keyid`）；**消费侧 `mint` 装前会逐项校验**，
  被改过的制品直接拒绝（官方文档 §2.7）。
- 不碰 `packages/kernel-iface`：那两个目录的 `kind = "iface"` 与线上 `bundle` 制品不一致，
  且用 0.1.11 **连 pack 都跑不了**，属于需要单独决策的事项，不在本工具范围内。
