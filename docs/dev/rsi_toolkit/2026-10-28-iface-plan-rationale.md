# 取舍说明：更正记录、方案对比与未决问题

配套主方案：[`2026-10-28-iface-modularization-and-minthub.md`](2026-10-28-iface-modularization-and-minthub.md)
平台事实：[`2026-10-28-mint-platform-notes.md`](2026-10-28-mint-platform-notes.md)

本页只放**过程与依据**：改过什么、为什么这样选、和并行方案差在哪、还有什么没定。
主方案不重复这些内容。

---

## 1. 更正记录（v1 → v3）

| # | 曾写过的 | 实际 | 怎么发现的 |
| --- | --- | --- | --- |
| 1 | "Mint 官网文档无法访问" | 可访问。`curl` 返回 200 / 25,032 字节；MintHub `/docs` 正文在 `DocsPage-*.js` 里 | 浏览器工具因"非公网 IP"拒绝，误判为网络不通；换 `curl` 即通 |
| 2 | 契约包用 `mint add` 装 | 官方是 **`mint pull`**，只写本机单元库，不改项目 `mint.toml` | 官网原文 |
| 3 | "运行时已是 `cpmrt`" | **文档改名、制品未改**：`mint/core@0.1.12` 里是 `bin/mint-core`，`which cpmrt` 为空 | 拉取制品后 `tar -tf` 看到真实文件名 |
| 4 | "`rsi.store.Store` 按 `iface-store` 补 Protocol" | **过度声明**。`iface-store` 只有 append/read/checkpoint；`Store` 是 617 行 ≈50 方法 | 并行方案 B 的机器清单直接标 `not iface-store` |
| 5 | 把 6 个 JSON Schema 当"接口"发 | **数据契约 ≠ 调用协议**。schema 只描述结果形状，不描述调用/错误/取消/幂等 | 方案 B 的批判；`provides.interfaces` 因此改为 `<iface>.data` |
| 6 | `publish --dry-run` 可作发布前验收 | 官方：**"只做本地检查，不上传，也不验证远端发布权限"** | 官网原文 |
| 7 | loop 协议写"describe/step/interrupt/status" | 这是**形状**；**线上方法名**是 `initialize` 与 `loop/next`，可执行文件在单元 `bin/` 下 | 回读 SPA 原文的 JSX 内联代码 |

**方法论教训**：工具的失败是**工具策略**，不是事实。判断"能不能访问/能不能执行"必须用能真正发出
请求或运行命令的通道验证一次，再下结论。第 1、3 条都是同一个毛病。

---

## 2. 与并行方案 B 的关系

同期另有一篇：[`docs/superpowers/specs/2026-10-28-rsi-iface-modularization-design.md`](../../superpowers/specs/2026-10-28-rsi-iface-modularization-design.md)
（配套机器清单 [`rsi-toolkit-modules.toml`](../../architecture/rsi-toolkit-modules.toml)）。

两篇**不是竞争，是同一件事的两个正交层面**：

| | 方案 B | 本文（v3） |
| --- | --- | --- |
| 回答 | 内部怎么解耦到能独立构建、独立替换 | 外部怎么发、怎么被发现、怎么被装 |
| 主轴 | **能力**（13 个 Python 包 + 同库 UoW） | **分发**（五类包 + 发布/消费路径） |
| 证据 | 源码调用链、事务边界、回归清单 | `mint` 实测、MintHub 文档原文、hub 检索 |
| 交付 | 设计与机器清单，**明确不发布任何包** | 生成器 + 发布脚本 + 发布顺序 |
| 缺口 | 没有"第三方今天怎么拿到契约"的可执行路径 | 没有事务所有权与迁移门禁 |

**v3 已吸收 B 的内容**：§2 的 13 模块分解、M0–M5 的阶段划分、事务所有权与"同库 UoW"、
`source-ref` 固定 commit + 构建描述 digest、迁移期间必须保留的行为清单。

### 2.1 B 对、本文原先错的三处

1. **`Store` 不能整体当 `iface-store`**。只有"事件日志"那一片可以声明实现，其余要靠领域调用契约。
2. **JSON 数据契约 ≠ 调用协议**。这是 D4（`<iface>.data` 命名）的直接来源。
3. **Rust trait 不是 Python ABI**。主方案 §3 的映射是**语义映射**；本地 schema 里的方法字符串
   不足以生成 binding。

### 2.2 本文有、B 没有的三处

1. **`kind = "iface"` 根本不在发布通道**（0.1.11 实测拒绝），线上 `agentcpm/iface-*` 是 `bundle`。
2. **契约的消费是 `mint pull`**，且 `inspect --abilities` 在 0.1.11 尚未发布。
3. **`bundle` 在 0.1 只装载 `skills/`**、`dry-run` 不验远端权限、`minisign` 装前逐项校验。

### 2.3 两篇共同漏掉、已补的事实

文档口径是 `cpmrt`，但制品里是 `bin/mint-core`。"cpmrt 尚未发布"与"运行时已是 cpmrt"都只对一半：
**文档改了名，制品没改**。因此主方案 D5 选择继续用 `MintHost + mint run --json`，并把 cpmrt 放到 M5。

### 2.4 唯一真正的分歧：现在发不发

- **B**：调用协议没定就发，只会得到"看起来像契约的文档"。
- **本文**：不发就没有分发渠道，第三方连数据形状都拿不到。

**取舍（D4）**：现在发，但用 `<iface>.data` 命名，README 首行写明"只定义数据形状，调用协议未定稿"；
调用契约就绪后**追加**裸名，不覆盖旧值。这样既不假称接口，也不失去今天唯一的发现通道。

---

## 3. 完整风险登记

| # | 风险 | 影响 | 应对 | 谁负责 |
| --- | --- | --- | --- | --- |
| 1 | 伪模块化：13 个包互相 import，各只有 1 个实现 | 拆了等于没拆 | M1 硬门：同一调用方跑两实现的测试 | 实施方 |
| 2 | 过度声明接口：数据契约当调用接口发 | 消费者按错误假设实现 | D4 的 `.data` 后缀 | 本文 |
| 3 | 跨存储原子性丢失 | 审批已置位但文件未替换，或反之 | 保持单进程；`result_unknown` 兜底 | 架构 |
| 4 | `Store.put_release_set` 只切 release_set，不切 asset_release | 一次激活、整体回滚做不到 | M3 目标，不是现有保证 | 实施方 |
| 5 | `RuntimeService.recall` 仍选 `latest_index`，不消费 active release set | 召回可能命中未激活集合 | M3 的 `release-set` 驱动召回 | 实施方 |
| 6 | `ExperienceService.ingest_trace` 多次事务 | 无法声称原子学习提交 | M3 的 ingest UoW | 实施方 |
| 7 | `CampaignService.release` 无 TTL / 一次性审批 | 弱于旧 Controller | 授权契约 + receipt 绑定 | 架构 |
| 8 | 装完不能用：`mint add` 不装依赖、不起服务 | 用户预期落空 | bundle 带 `setup.py`，README 首行写"还要两步" | 发布 |
| 9 | 许可 AGPL-3.0-only | 契约含源码会传染第三方实现 | 契约包只放 schema + 文档；许可单列需法务 | owner |
| 10 | 小样本被误读 | 0.2.0 真实实验是 `NO_IMPROVEMENT` | 文案保留"同任务重复测量，不构成泛化收益" | 内容 |

**IFace 文档漂移**（实施前必须固定权威版本）：`Store` trait 只有 append/read/checkpoint；
`Session` 缺 README 所列的 facts/list_ids/count；`Policy` trait 用 `check`，schema 写 `authorize`。

---

## 4. 未决问题

**给 Mint 平台方**

1. `Kind::Iface` 何时进发布通道？在此之前 `bundle` + `provides.interfaces` 是否被承认为契约包的正式形态？
2. `mint inspect --abilities` 与 `mint loop` 计划在哪个版本发布？（当前 `mint/cli` 最新 0.1.11）
3. hub 能否把 `interfaces` 进检索索引（`/-/v1/search?interface=rsi-recall`）？
4. 是否计划支持"消费方声明依赖某契约"（`requires.interfaces`）？
5. 契约包这类"无代码纯文档"包，是否应有独立的 trust / 审核类别？
6. `mint-core` → `cpmrt` 的制品层改名计划？

**已由实测回答、无需再问**

- ~~安装时是否验签~~ → 是，装前逐项校验 minisign。
- ~~dry-run 能否当验收~~ → 不能，只做本地检查。
- ~~令牌需要什么 scope~~ → `publish-new` + `publish-update`。

**给产品 owner**

7. 用哪个 scope？owned namespace 还是借用 `agentcpm/`？
8. 契约包许可：保持 AGPL-3.0-only，还是给 schema 单独许可？
9. 能力包 wheel：bundle 内嵌，还是独立分发包？
10. `Store` 的内存实现：测试替身，还是正式第二实现？

---

## 5. 反模式清单

1. 把控制面拆成 8 个微服务——跨存储原子性会碎，`result_unknown` 变常态。
2. 把 `service/rsi` 按目录拆成 6 个 Python 包分别发——必须严格同版本锁定，收益为零。
3. 给每个 iface 造空实现凑"可替换"——违反"同一调用方跑两实现"，只增维护面。
4. 把 `rsi-host` 实现成 loop 单元——回退语义破坏"未知结果不可重放"。
5. 契约包里放 Python 代码——AGPL 传染 + 契约随实现漂移。
6. 依赖 bundle 携带 `.mcp.json` 自动装 MCP——0.1 只装载 `skills/`，会静默失效。
7. 用 `dry-run` 的成功当作"发布没问题"——它不验远端权限。
