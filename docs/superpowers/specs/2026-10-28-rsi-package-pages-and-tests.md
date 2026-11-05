---
title: RSI 包发布页与测试用例规范
date: 2026-10-28
status: proposed
type: specification
parent: ../plans/2026-10-28-rsi-iface-v2-m0-m1.md
baseline: 44235f1060c64c3e3f1d8c32ea51ed9363e99850
---

# RSI 包发布页与测试用例规范

本文件补齐首批及各阶段包的**使用文档正文**和**可执行测试用例要求**。设计见 [v2 设计方案](2026-10-28-rsi-iface-v2-design.md)，任务顺序见 [首批实施计划](../plans/2026-10-28-rsi-iface-v2-m0-m1.md)，人工接入步骤和完整测试代码见 [workspace 测试指南](../../../workspace/rsi-iface-v2/README.md)。本文的用例表是待实施要求，不是已通过报告；本轮不发布 MintHub。

## 1. 目标与判定

每个包发布后，MintHub 页面必须能独立回答四个问题，不需要读者翻仓库：

1. 它是什么、**不是什么**；
2. 怎么装（`mint add` 还是 `mint pull`）；
3. 最小可运行示例与预期输出；
4. 怎么自己验证它没坏。

页面正文只有一处手写来源：包目录下的 `README.md`。每包另交付 `REQUIREMENTS.md`、`TESTING.md`、`cases.json`；正文链接这些附件。机器字段由构建器从清单生成，正文中的安装/验证命令由同一份字段渲染。

页面通过判定：标注为可执行的命令块由 `packaging/tests/test_readme_commands.py` 在对应环境执行，断言退出码和结构化结果。JSON/TOML、接口表及预期输出作为资料块解析，不作为 shell 执行。测试不得以任意 stdout 前缀代替评分、工具调用或完整性断言。

### 1.1 与参考页的关系

2026-10-28 读取的[线上样例](https://mint-hub.ea.modelbest.co/p/wujiahe/skill-document-generation-for-proofs)版本为 0.4.1，其可见页面可作为组织基准：

| 页面组成 | 来源 | 该样例的做法 |
| --- | --- | --- |
| 标题 + 一句话 | `mint.toml` 的 `description` | “按模板生成在职证明、收入证明等文书” |
| 正文 | 使用说明 | 来源、独立安装、宿主前提、AgentCPM 接入脚本、撤销 |
| 安装命令 | 机器生成 | `mint add wujiahe/...@0.4.1` |
| provides | `mint.toml` | `{"skills": ["document-generation-for-proofs"]}` |
| 宿主能力 | `REQUIREMENTS.md` 链接 | 业务工具另行配置，安装技能不自动授予 Python/网络权限 |
| 制品与溯源 | 页面制品栏 | 通用制品、sha256、签名和固定来源提交 |

目标每包正文 40–90 行，详细操作放附件。该公开页面没有展示自动化测试结果，不能据此声称它带完整测试套件。RSI 额外要求用例输入、预期输出和机器报告。参考包的 AgentCPM 脚本与 RSI 的 Mint 接入方式分别描述，不复制未经验证的适配命令。

## 2. 页面固定结构

八节，顺序不变。缺少任何一节视为发布资料不完整。

```markdown
# <包名>

<一句话：它做什么，给谁用。>

## 它是什么
## 它不是什么
## 安装
## 快速开始
## 接口
## 验证
## 已知限制
## 卸载与溯源
```

约束：

- **“它不是什么”必填。** 这一节是防止过度声明的唯一位置，必须逐条列出本包不覆盖的能力（例如 `rsi-evaluation` 不执行任务、不连模型）。
- **安装节**必须区分包类型：契约包 `mint pull <scope>/<name>@<version>`；能力包 `mint add <scope>/<name>@<version>`。
- **版本号不写死在正文**，用 `<version>` 占位，由构建器替换；发布页显示 `install_command` 字段。
- **scope 不写死**：本轮构建用 `local/`，发布时由构建器替换为实际 scope。正文里出现 `local/` 一律视为缺陷。
- **禁止出现 pip 命令**，包括“开发时可以 pip install”这类提示；开发入口只有 `packaging/dev_run.py`。
- **不写截图**，不写无法复制的“在你的环境里应该可以”。

补充交付要求：

| 文件 | 必须包含 |
| --- | --- |
| `REQUIREMENTS.md` | Python >=3.13、Mint CLI 实测版本、Core 是否需要、可选 YAML/模型/平台能力、权限与配置来源 |
| `TESTING.md` | case ID、fixture、命令、预期退出码/JSON、报告位置、故障排查、卸载和恢复 |
| `cases.json` | §3 的机器可读索引；禁止把计划中的 case 标记为通过 |
| `examples/` | 与 probe 注册表一致的示例输入；README 的命令由同一索引生成 |
| `SKILL.md` | 本包用途、安装位置和验证命令；明确库安装、技能发现和工具注册的区别 |

`mint add` 只把 Python 源码放到项目安装目录，不会让任意 `python3 -c 'import ...'` 自动成功，也不自动注册 Kernel/MCP 工具。安装态示例通过校验闭包的 probe 运行器执行；使用方自己的应用按 T9 构建闭包。wheel 环境示例另行标注。包正文链接 workspace 指南，但正常用户验证不依赖 checkout 中的 `packaging/` 存在。

## 3. 用例模型

### 3.1 四层

| 层 | 名称 | 回答什么 | 运行位置 |
| --- | --- | --- | --- |
| L0 | 安装 | 能装、能卸、布局稳定、无残留 | 临时 Mint 工程 |
| L1 | 冒烟 | 最小调用返回正确形状 | 包 lib 或 checkout |
| L2 | 边界 | 畸形输入、契约拒绝、路径逃逸、能力缺失 | 包 lib |
| L3 | 完整性与替换 | 篡改拒绝、同一调用方两实现、无 pip、无 site-packages | 安装后执行 |

L0/L3 在 G4 和 workspace 验收跑；L1/L2 在拥有该包的任务提交前跑。AST、历史 fixture 和旧导入兼容只在开发验收运行，不能谎称安装目录中存在源码仓库。

### 3.2 用例文件

位置：能力包 `modules/<pkg>/cases.json`，数据包源模板 `packaging/contracts/rsi-iface-data/cases.json`。构建器复制到 bundle 根；它不进 `lib_sha256`，但与 README/REQUIREMENTS/TESTING/examples 一起计入 `test_input_sha256` 和制品哈希。安装态 driver 位于 probe 应用的 lib，受其闭包摘要校验。

```json
{
  "schema": "rsi.package-cases/v1",
  "package": "rsi-foundation",
  "version": "0.1.0",
  "cases": [
    {
      "id": "F-02",
      "level": "L2",
      "title": "篡改 blob 后读取必须报 CorruptBlob",
      "profiles": ["development", "installed"],
      "driver": "python",
      "entry": "rsi_probe.cases.foundation:f02",
      "expect": {"exit": 1, "stderr_contains": ["CorruptBlob"]},
      "covers": ["content.CAS.get", "content.CorruptBlob"]
    }
  ]
}
```

driver 固定为 `python`、`mint-lifecycle` 或 `source-check`。`entry` 只能取构建时冻结的 case ID 注册表，不从 JSON 执行任意 import/shell。开发 runner 显式加入本包、depends 的 source_paths 及 probe 的 src，注册表懒加载当前 case，不提前导入未迁移包；安装 runner 只调用 `python3 -I -S -B <probe>/bin/rsi-launch.py --case F-02 --tmp <新临时目录>`，不自行插入未经验证的 lib。

F-02 的 driver 完整示例，落地到 probe 的 `cases/foundation.py`：

```python
def f02(tmp):
    from rsi_foundation.content import CAS
    cas = CAS(tmp / "cas")
    ref = cas.put(b"original")
    digest = ref.removeprefix("sha256:")
    (cas.root / digest[:2] / digest[2:]).write_bytes(b"tampered")
    cas.get(ref)
```

`expect.exit` 精确匹配；可选 `stdout_json` 对指定 JSON 路径的值断言，`stderr_contains` 对错误子串断言；任一失败报告即失败。每例独立临时目录和超时 30 秒，生命周期例可显式扩至 120 秒；超时记失败。缺少运行条件记 `blocked`，不能当 `passed`。source-check 不参与无 checkout 的安装覆盖，报告同时列适用和未适用集合。

### 3.3 运行与报告

```bash
# 开发模式：只跑 L1/L2
python3 packaging/run_cases.py modules/rsi-foundation --levels L1,L2 --out /tmp/foundation-development.json

# 安装模式：跑全部四层
python3 packaging/run_cases.py --project /absolute/test-project --installed /absolute/test-project/.mint/packages/local/rsi-foundation@0.1.0 --probe /absolute/test-project/.mint/packages/local/rsi-probe@0.1.0 --levels L0,L1,L2,L3 --out /tmp/foundation-installed.json
```

仓库验收报告归档到 `conformance/iface-v2/packages/<pkg>.json`；workspace 原始结果保留到 `workspace/rsi-iface-v2/evidence/`。字段如下，digest/commit 均由实际输入生成，不复制下例值：

```json
{
  "schema": "rsi.package-report/v1",
  "package": "rsi-foundation",
  "version": "0.1.0",
  "lib_sha256": "sha256:...",
  "test_input_sha256": "sha256:...",
  "artifact_sha256": "sha256:...",
  "profile": "installed",
  "python": "3.13.15",
  "mint": "0.1.11",
  "commit": "44235f1...",
  "cases": [{"id": "F-01", "level": "L1", "exit": 0, "ok": true}],
  "summary": {"total": 11, "passed": 11, "failed": 0, "blocked": 0},
  "generated_at": "2026-10-28T00:00:00Z"
}
```

数据包没有 lib，`lib_sha256` 为 null，另记录 `schemas_sha256`。普通包用例报告证明包行为；它不能自动证明某项 IFace 的全部要求。`implements` 仍需设计 §6 的契约专属报告，包含 contract ID/schema digest、该契约要求的全部测试及当前制品摘要。rsi-evaluation 保持不声明 implements。

## 4. 首批 5 个包

以下正文是各包 README 的源模板，`<version>`、`<scope>`、`<probe-version>` 由构建器替换。实施时将示例命令转成带 rsi:exec 标记的 fenced block，并把接口、期望输出保持为资料；本文件展示用的外层 markdown block 不直接交给 shell。附带 probe 的安装/准备步骤必须写入各包 TESTING.md 并在快速开始前链接，不能假设只装一个库就已存在 probe。

### 4.1 `rsi-iface-data`（契约参考包，零代码）

```markdown
# rsi-iface-data

RSI 领域数据契约的权威形状定义。只描述数据长什么样，不包含任何代码。

## 它是什么
5 个冻结的 JSON Schema：trace、experience、evaluator、recall、component。
实现方按它产出数据，消费方按它校验数据；同一份 schema 同时用于仓库内的
`rsi-foundation` 校验器。

## 它不是什么
- 不是调用协议：没有方法名、错误码、取消或幂等语义。
- 不包含实现，也不带 `lib/`，装完不会多出任何可执行能力。
- 不包含 `rsi.host/v1`；M1 仍保留旧 Host，runtime-executor/v1 只是后续草案。

## 安装
    mint pull <scope>/rsi-iface-data@<version>

## 快速开始
    mint pull <scope>/rsi-iface-data@<version>
    mint inspect <scope>/rsi-iface-data@<version>

## 接口
| schema | $id | 用于 |
| --- | --- | --- |
| rsi.trace.v1.json | urn:rsi:trace:v1 | 执行轨迹归档 |
| rsi.experience.v1.json | urn:rsi:experience:v1 | 经验条目与状态 |
| rsi.evaluator.v1.json | urn:rsi:evaluator:v1 | 评测器描述与资格 |
| rsi.recall.v1.json | urn:rsi:recall:v1 | 召回请求与响应 |
| rsi.component.v1.json | urn:rsi:component:v1 | 组件清单与运行结果 |

## 验证
    python3 -I -S -B .mint/packages/<scope>/rsi-probe@<probe-version>/bin/rsi-launch.py --case ID-04
    期望：schema_count=5，全部摘要与冻结来源一致。

此验证命令使用本地 path 安装的契约参考包和配套 probe，准备步骤见 TESTING.md。
pull 只进入单元库，不在当前目录创建 schemas/，也不改变项目依赖。

## 已知限制
- Mint 不校验 `provides.interfaces`，声明是否真实由实现方的 conformance 报告保证。
- 各 schema 的 `schema_version` 独立演进，包版本用 SemVer，两者不等价。

## 卸载与溯源
pull 未添加项目依赖。若通过本地 path 方式安装到项目，再使用：
    mint remove <scope>/rsi-iface-data
来源、commit 与每个 schema 的 sha256 见 `ORIGIN.md`。
```

用例：

| ID | 层 | 用例 | 命令/输入 | 期望 |
| --- | --- | --- | --- | --- |
| ID-01 | L0 | 本地 path 安装成功 | `mint add path:<out>/rsi-iface-data` | exit 0，目录出现 `schemas/` |
| ID-02 | L0 | `pull` 到单元库 | `mint pull <scope>/rsi-iface-data@<version>` | exit 0；单元库有 manifest 与 blob；无本地 registry 时明确 blocked，M5 前补验 |
| ID-03 | L1 | 5 个 schema 可解析 | 逐个 `json.load` | 无异常 |
| ID-04 | L1 | schema 字节与仓库一致 | 比对 `sha256(contracts/*.json)` | 5 项全等 |
| ID-05 | L2 | 包里没有代码 | `find <pkg> -name '*.py' -o -name lib` | 无结果 |
| ID-06 | L2 | 包里没有旧边界 | `find <pkg> -name 'host.v1.json'` | 无结果 |
| ID-07 | L2 | provides 用 `.data` 名 | 读 `mint.toml` | 5 个 `rsi-*.data`，无裸名 |
| ID-08 | L2 | 安装文档区分 pull/path | 文档命令元数据 | pull 不改项目；path 是本地代验；remove 只对应项目安装 |

### 4.2 `rsi-foundation`

```markdown
# rsi-foundation

内容寻址存储、契约加载与校验、证据与脱敏。只依赖 Python 标准库。

## 它是什么
- `rsi_foundation.content`：CAS、canonical JSON、digest、`PrivateCAS` 权限加固。
- `rsi_foundation.contracts`：5 个 schema 的加载、子集校验与共享 DTO（含 RecallPolicy）。
- `rsi_foundation.evidence`：脱敏、usage 归一、非敏感模型描述。

## 它不是什么
- 不是通用 JSON Schema 实现：只支持 5 个冻结 schema 实际使用的关键字，
  遇到未知关键字直接报错，不静默放行。
- 不校验 `format: date-time`：本版把 `format` 当注解，非法时间字符串也会通过。
- CAS 保留旧 `delete(ref)` 行为；无引用计数和自动垃圾回收，删除由调用方管理。

## 安装
    mint add <scope>/rsi-foundation@<version>

## 快速开始
安装配套 probe 后执行（完整输入与 Python 用法见 TESTING.md）：
    python3 -I -S -B .mint/packages/<scope>/rsi-probe@<probe-version>/bin/rsi-launch.py --case F-01
    期望：CAS 往返 b"hi"，sha256 引用长度 71。

## 接口
| 符号 | 说明 |
| --- | --- |
| `CAS(root)` | `put/get/put_json/get_json/refs/delete`，ref 形如 `sha256:<64hex>` |
| `PrivateCAS(root)` | 同上，目录 0700、文件 0600 |
| `canonical(obj) -> bytes` | 历史字节算法，保持兼容 |
| `canonical_json_v1(obj)` | 同编码，额外拒绝 NaN/Infinity |
| `load(name)` / `errors(name, payload)` / `require(name, payload)` | 契约加载与校验 |
| `validate(schema, value)` / `validate_schema(schema)` | 子集校验器公开入口 |
| `Redactor` / `redact(value)` | 脱敏并返回报告 |

## 验证
    python3 -I -S -B .mint/packages/<scope>/rsi-probe@<probe-version>/bin/rsi-launch.py --package rsi-foundation --levels L1,L2

## 已知限制
- `canonical` 不拒绝非有限数，这是历史行为；需要严格版请显式用 `canonical_json_v1`。
- 校验器不认识 `$ref` 之外的远程引用，也不读网络。
- 错误文字不保证与 jsonschema 完全一致，但保留数据路径。

## 卸载与溯源
    mint remove <scope>/rsi-foundation
```

用例：

| ID | 层 | 用例 | 输入 | 期望 |
| --- | --- | --- | --- | --- |
| F-01 | L1 | put/get 往返 | `put(b"hi")` 后 `get(ref)` | 结果 `b"hi"`，ref 以 `sha256:` 开头且长度 71 |
| F-02 | L2 | 篡改后读取 | 直接改 blob 字节后 `get` | 抛 `CorruptBlob` |
| F-03 | L1 | legacy canonical 字节 | `canonical({'b':1.0,'a':'中文'})` | 等于 `'{"a":"中文","b":1.0}'.encode('utf-8')` |
| F-04 | L2 | 非有限数 | `canonical_json_v1(float('nan'))` | 抛 ValueError；`canonical(float('nan'))` 仍成功 |
| F-05 | L1 | 11 个正例全过 | `contracts/examples/v1/*` | `errors(...)` 全为空 |
| F-06 | L2 | 8 个负例全拒 | `contracts/invalid/v1/*` | 每例至少 1 条错误，且含数据路径 |
| F-07 | L2 | 未知关键字 | `validate_schema({"contains": ...})` | 抛 `ValueError("unsupported ...")` |
| F-08 | L2 | date-time 是注解 | 非法时间字符串的 trace payload | 校验通过（回归用例，防止静默收紧） |
| F-09 | L1 | 无 jsonschema 可运行 | `python -I -S -B` 下导入并校验 | 成功，`jsonschema` 不在 `sys.modules` |
| F-10 | L2 | 私有权限 | `PrivateCAS` 建目录写文件 | 目录 0700、文件 0600 |
| F-11 | L2 | 无跨层导入 | development profile AST 扫描 `src/` | 不出现 `rsi/control/harness/toolkit/connectors`；安装态另验 origins |

### 4.3 `rsi-model-client`

```markdown
# rsi-model-client

OpenAI 兼容的提案模型客户端。显式调用，不重试，不跟随重定向。

## 它是什么
`CompatibleModel(base_url, model, api_key, timeout, max_tokens, transport)`：
一次调用返回文本，`last_usage` 记录用量，`describe()` 返回非敏感身份。

## 它不是什么
- 不实现 Kernel `iface-model` 的 transport：只做语义对齐，不声明可替换
  Kernel 模型端口。
- 不做隐式重试、不做流式、不自动切模型。
- 不保证供应商侧的模型版本；`describe()` 只报声明值。

## 安装
    mint add <scope>/rsi-model-client@<version>

## 快速开始
    python3 -I -S -B .mint/packages/<scope>/rsi-probe@<probe-version>/bin/rsi-launch.py --case M-01
    期望：text="ok"，usage.input_tokens=3；transport 是本地替身，无外部请求。

## 接口
| 符号 | 说明 |
| --- | --- |
| `CompatibleModel(...)` | 构造即校验 URL 与凭据；非 loopback 必须 HTTPS |
| `model(prompt) -> str` | 单轮调用，失败抛 `RuntimeError`，凭据已脱敏 |
| `model.last_usage` | 最近一次的 `usage` 原始字典 |
| `model.describe()` | provider/model/base_url/timeout/max_tokens |
| `transport=` | 注入替身，签名 `fn(body) -> dict` |

## 验证
    python3 -I -S -B .mint/packages/<scope>/rsi-probe@<probe-version>/bin/rsi-launch.py --package rsi-model-client --levels L1,L2

## 已知限制
- 拒绝 HTTP 重定向，重定向按失败处理。
- `finish_reason` 为 `length` 或 `content_filter` 时按失败处理，不返回半截文本。

## 卸载与溯源
    mint remove <scope>/rsi-model-client
```

用例：

| ID | 层 | 用例 | 输入 | 期望 |
| --- | --- | --- | --- | --- |
| M-01 | L1 | 替身 transport 返回文本 | `transport` 返回固定 dict | 文本 `ok`，`last_usage` 等于传入的 usage |
| M-02 | L1 | `describe()` 不含凭据 | 构造后调用 | 无 `api_key` 字段，`base_url` 去尾斜杠 |
| M-03 | L2 | 明文 HTTP 非 loopback | `base_url='http://example.com/v1'` | 抛 `ValueError` |
| M-04 | L2 | URL 内嵌凭据 | `https://u:p@host/v1` | 抛 `ValueError` |
| M-05 | L2 | 截断 | `finish_reason='length'` | 抛 `RuntimeError`，消息含 `truncated` |
| M-06 | L2 | 空文本 | `content=''` | 抛 `RuntimeError` |
| M-07 | L2 | 失败信息脱敏 | transport 抛含 key 的异常 | 消息含 `[REDACTED]`，不含原 key |
| M-08 | L2 | 不重定向 | 桩服务 302 | 失败，且只有一次请求 |

### 4.4 `rsi-evaluation`

```markdown
# rsi-evaluation

评测器、资格判定、配对统计。纯函数，不执行任务，不连模型。

## 它是什么
- `Case` / `TaskSuite`：用例与套件，JSON 直接读，YAML 需要可选的 pyyaml。
- 5 种评测器：Exact、Contains、JSONFields、Rubric、Composite。
- `qualify()`：用校准集产出 Qualification；`qualification_matches()`：校验记录是否仍然适用。
- 指纹双算法：v1 保留历史等价，v2 用稳定 ID，不依赖模块路径。

## 它不是什么
- 不执行任务：`ExperimentService` 留在应用层，本包只做打分。
- 不连接模型：Rubric 通过注入的 `judge` 回调使用模型，本包不内置客户端。
- 不声明 `implements rsi-evaluator.data`：现有字段与冻结 schema 尚不一致。

## 安装
    mint add <scope>/rsi-evaluation@<version>

## 快速开始
    python3 -I -S -B .mint/packages/<scope>/rsi-probe@<probe-version>/bin/rsi-launch.py --case E-02
    期望：status="qualified"、observed=5、agreement=1.0。
fixture 是 5 个带 text/pass 标签的 construct case，输出按 pass 交替为 ok/bad，
使用 ExactEvaluator("text")；完整代码见 TESTING.md 和 workspace 指南。

## 接口
| 符号 | 说明 |
| --- | --- |
| `Case(case_id, split, task, **kw)` | `expected`、`files`、`category` |
| `TaskSuite.from_file(path)` | `.json` 直读；`.yaml` 需 pyyaml |
| `Evaluator.evaluate(case, output, trace=None)` | 返回 `{score, passed, detail}` |
| `evaluator_from_spec(spec, judge=None)` | 从声明构造内建评测器 |
| `qualify(evaluator, cases, outputs, **kw)` | 产出 Qualification |
| `qualification_matches(value, evaluator, audit_cases)` | 记录是否仍适用 |
| `evaluator_fingerprint` / `..._v1` | v2 / 历史算法 |
| `paired_bootstrap` / `worst_case_evidence` | 确定性统计（固定 seed） |

## 验证
    python3 -I -S -B .mint/packages/<scope>/rsi-probe@<probe-version>/bin/rsi-launch.py --package rsi-evaluation --levels L1,L2

## 已知限制
- YAML 套件需要额外安装 pyyaml；缺失时抛明确的可选功能错误，JSON 路径不受影响。
- v1 指纹对评分函数源码**逐字敏感**：迁移后重排格式会让历史 qualification 失效。
- 未注册的第三方评测器会被拒绝，不再回退到旧算法。

## 卸载与溯源
    mint remove <scope>/rsi-evaluation
```

用例：

| ID | 层 | 用例 | 输入 | 期望 |
| --- | --- | --- | --- | --- |
| E-01 | L1 | Exact 打分 | 输出与 expected 相同/不同 | 1.0 / 0.0，`passed` 对应 |
| E-02 | L1 | 5 例校准通过 | `min_cases=5`，全对 | `status='qualified'`，`agreement=1.0` |
| E-03 | L2 | 不足 5 例 | 4 例 | `status='exploratory'`，不能报告 qualified，保留现有语义 |
| E-04 | L1 | 记录仍适用 | 刚产出的 Qualification | `qualification_matches` 为 True |
| E-05 | L2 | 设置变更即失配 | 改 `expected_field` | `qualification_matches` 为 False |
| E-06 | L2 | 历史 v1 迁移后仍匹配 | 模块路径别名 + fixture | True |
| E-07 | L2 | v2 不依赖模块路径 | 改 `__module__` | v2 指纹不变 |
| E-08 | L2 | Composite 递归 v1 | 两层组合的 fixture | 与历史指纹一致 |
| E-09 | L2 | 未注册第三方 | 自定义类 | 抛 `EvaluationError` |
| E-10 | L2 | 未知算法 | evidence 里 `fingerprint_algorithm='x'` | 返回 False，不回退 v1 |
| E-11 | L2 | 无 pyyaml | 读 `.yaml` 套件 | 明确的可选功能错误；读 `.json` 正常 |
| E-12 | L1 | 统计确定性 | 同输入同 seed=17 跑两次 | 结果完全相同 |

### 4.5 `rsi-execution`

```markdown
# rsi-execution

执行端口：旧 `Host` 协议、结果归一、两种工作区暂存策略。

## 它是什么
- `Host` Protocol：`capabilities()` 与 `execute(request, cancel_event)`。
- `normalize_result()`：唯一校验 `execution_id` 的地方，非法即 `result_unknown`。
- `safe_path()` / `stage_assets()`：相对路径围栏与原子文本暂存（common 策略）。
- `stage_assets_strict()`：额外拒绝 `.git`、`.mint`，`O_NOFOLLOW`，0600。

## 它不是什么
- 不提供 `submit/status/cancel` 的持久生命周期：DTO 只是拟议形状，M1 不落库。
- 不包含 `MintHost` / `SeatbeltMintHost` / `PilotDeckHost`，它们留在应用层适配。
- 不是 OS sandbox：拥有安装目录写权限的调用者仍可改代码。

## 安装
    mint add <scope>/rsi-execution@<version>

## 快速开始
    python3 -I -S -B .mint/packages/<scope>/rsi-probe@<probe-version>/bin/rsi-launch.py --case X-01
    期望：临时绝对工作区内 a.txt 内容为 hi；数据在安装目录外。

## 接口
| 符号 | 说明 |
| --- | --- |
| `Host` | Protocol，`execute` 返回宿主原始 dict |
| `normalize_result(result, execution_id, host)` | 补齐字段并校验身份 |
| `safe_path(root, relative)` | 拒绝绝对路径、`..`、围栏外目标 |
| `stage_assets(workspace, assets)` | common 策略，绝对路径 workspace，原子替换 |
| `stage_assets_strict(workspace, assets)` | strict 策略，额外名称拒绝与 `O_NOFOLLOW` |
| `ExecRequest/ExecResult/CancelAck` | 拟议 DTO，形状冻结、未接宿主 |

## 验证
    python3 -I -S -B .mint/packages/<scope>/rsi-probe@<probe-version>/bin/rsi-launch.py --package rsi-execution --levels L1,L2

## 已知限制
- `common` 与 `strict` 是两套有意的差异策略，不做合并；差异见验证表 X-05。
- 平台不提供 `O_NOFOLLOW` 时 strict 直接报能力不支持，不降级为 common。

## 卸载与溯源
    mint remove <scope>/rsi-execution
```

用例：

| ID | 层 | 用例 | 输入 | 期望 |
| --- | --- | --- | --- | --- |
| X-01 | L1 | 正常暂存 | `{'a.txt': 'hi'}` | 文件内容 `hi` |
| X-02 | L2 | `..` 逃逸 | `{'../x': 'hi'}` | `AssetPathError` |
| X-03 | L2 | 绝对路径 | `{'/etc/x': 'hi'}` | `AssetPathError` |
| X-04 | L2 | symlink 逃逸 | 工作区内软链指向外部 | 拒绝，外部文件未被写 |
| X-05 | L2 | 两种策略差异 | `.git/config`、`.mint/x` | common 允许、strict 拒绝（逐项断言） |
| X-06 | L2 | 相对 workspace | `stage_assets('ws', {...})` | `AssetPathError('workspace must be absolute')` |
| X-07 | L2 | 身份不一致 | `execution_id` 不匹配 | 结果 `status='result_unknown'` |
| X-08 | L2 | 非法状态 | `status='weird'` | `result_unknown` |
| X-09 | L3 | 同一调用方两实现 | 两个替身 Host 跑同一次调用 | 归一后结果一致 |
| X-10 | L2 | 无降级 | 模拟无 `O_NOFOLLOW` | 报能力不支持，不写文件 |

## 5. 后续包的骨架

M2/M3 包在各自独立阶段计划中定义命令；本轮只列入阶段输入的页面章节与用例类别，不计作首批未完成任务。

| 包 | 页面必须有的专有节 | 必须覆盖的用例类别 |
| --- | --- | --- |
| `rsi-component-runner` | 进程模型、limits/kill/reap、artifact 回收 | 超时、取消、孤儿进程、产物哈希不符、`RSI_ROOT` 未设置 |
| `rsi-storage` | migration 版本、备份恢复、并发 | 历史迁移不重写、`tx` 嵌套、并发写、备份后恢复一致 |
| `rsi-experience-store` | ingest 提交边界、索引构建 | 去重、跨表原子、索引与账本一致、召回过滤 |
| `rsi-recall-selection` | 选择与渲染、降级策略 | 预算截断、空语料、降级到 lexical、超时 |
| `rsi-asset-ledger` | prepare/commit/rollback、授权消费 | 期望版本不符、授权重放、TTL 过期、回滚原子性 |
| M5 应用包 | 服务启动、MCP 入口、数据位置、升级 | 干净安装、启动、MCP 调用、升级保留数据、卸载 |

每个后续代码包至少 6 条 L1/L2 用例；涉及实现替换的包另加 1 条 L3。数据包按 5 schema 字节与来源验收。首批 49 条包用例另与 workspace W-01 到 W-12 的集成用例关联；条目数量不代表覆盖率。

## 6. 与阶段门的关系

| 门 | 页面/用例要求 |
| --- | --- |
| G2 | fixture 包有 README/REQUIREMENTS/TESTING/cases，runner 跑通适用 L1/L2；模板命令可渲染 |
| G3 | wheel profile 的 Python 示例能脱离 checkout 执行；Mint 安装命令在 G4 实验 |
| G4 | 真实 5 包在临时工程跑安装适用的 L0–L3，另有 source-check 报告；digest 一致，pull 缺口单列 |
| G4-W | workspace W-01 到 W-12 的必需集通过；scripted Agent 有实际 skill_read 和安装路径证据 |
| G5 | 页面字段与清单一致；命令无模板残留；正文和 workspace 指南分别完成可执行检查 |

`packaging/tests/test_readme_commands.py` 通过 `<!-- rsi:exec id=F-01 profile=installed -->` 标记关联紧随其后的命令块；ID 必须在 cases 索引中，profile 必须显式填写。G2 只检查已交付 fixture/template，G4 执行真实安装块；缺少后阶段条件不能在早期报告通过。示例命令、fixture 和预期来自同一注册表。

## 7. 发布时的替换

| 项 | 本地阶段 | 发布后 |
| --- | --- | --- |
| scope | `local/` | 实际 scope |
| 安装命令 | `mint add path:<out>/<pkg>` | `mint add <scope>/<pkg>@<version>` |
| 契约消费 | `mint add path:` 代用 | `mint pull <scope>/<pkg>@<version>` |
| integrity | lib tree_digest、test_input 摘要和本地制品哈希 | 保留这些字段，另加仓库 manifest/hash/签名 |

正文模板只用生成字段，发布渲染结果不得有 `<scope>/<version>/<probe-version>`。本地 path 模式必须实际执行；registry 模式先验证渲染和 argv，联网 pull 的通过证据在可用本地 registry 或 M5 补齐，不因尚未发布而伪造命令执行结果。

## 8. 已确定的补充决策

- cases.json 和文档随包分发，T8 用真实 Mint pack 检查保留情况；缺失则 G2 失败。
- Rubric 示例固定 `judge_id="example/v1"` 并标记替身，不声称真实模型质量。
- 四个能力包的注册 driver 来自 probe 的单一实现，数据包只含描述和 fixture，不添加 Python lib。
- workspace 交付是 M1 的必需用户验收，详见实施计划 T10W。外部真实模型和 M5 MCP 验收另立条件，不计入 scripted 通过结论。
