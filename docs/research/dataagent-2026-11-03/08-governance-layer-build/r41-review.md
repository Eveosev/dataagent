---
round: 41
date: 2026-11-05
subject: dataagent-governance、dataagent-runtime、dataagent-s0、dataagent-scenarios 的完成度与质量评审；跨包共性问题
kernel: agent-kernel@c1231ab（本地 HEAD，未 fetch；source-ref 记为 f0fa521，HEAD 领先 168 个提交，期间 iface 只追加，S0 映射原语不变）
tests: governance 117 passed；runtime 75 passed；scenarios 12 passed
---

# Round 41 评审：评测与治理层、共享运行时、S0 组合

范围：`dataagent-governance`（08 §1、§5）、`dataagent-runtime`（08 §2）、`dataagent-s0` 与 `dataagent-scenarios`（08 §8），均在 `packages/capabilities/`。数据层与契约 core 见 [06 r41-review.md](../06-data-layer-build/r41-review.md)，执行应用层见 [07 r41-review.md](../07-application-layer-build/r41-review.md)。

| 包 | 规模 | 测试 | 结论 |
|-|-|-|-|
| governance | src 34 文件 / 4,143 行；tests 4,161 行 | 117 passed | S0 6 项均已实现且各带缺陷；按需 48 项未注册 |
| runtime | src 18 文件 / 2,397 行；tests 1,569 行 | 75 passed | 08 §2 组件齐全；复检与外发钩子 fail-open；自身 bundle 落后于 src |
| s0 | `mint.toml`、README、2 个 Skill | — | 引用一致，离线 `mint pack` 通过；应用层以 warn 运行；只有相对路径依赖 |
| scenarios | src 2 文件 / 194 行；tests 1,655 行 | 12 passed | 两族各一条三进程 MCP 链路到 AcceptanceReport；跳过 W0 样例多数中间步骤；加载源码包而非 bundle |

测试命令：各包 `.venv/bin/python -m pytest -p no:cacheprovider -o addopts=''`。直接 `.venv/bin/pytest` 在 governance 有 8 个 collection error。

## 1. 跨包共性问题

| # | 严重度 | 确认/疑似 | 位置 | 问题 | 复现 |
|-|-|-|-|-|-|
| X1 | 高 | 确认 | `dataagent-runtime/.../enforcement.py:152`；`dataagent-runtime/.../interfaces/mcp_server.py:85-86`；`dataagent-governance/.../governance/access.py:47-48`；三个 bundle 的 `.mcp.json`（无 `DATAAGENT_HOST_*`）；`dataagent-data/.../runtime.py:43-79` | 宿主权威未交付到产品路径：打包后主体与用途取自 Agent 可写的 `arguments.context`；`subject_ref` 为空时跳过主体比对；数据层 `create` 不读宿主 env。测试固件均注入 `host_subject_ref` / `host_purpose`，掩盖了该问题；`test_s0_mcp_e2e.py:266` 中 mallory 被拒只因策略无其规则 | `governance/r1_wire_identity.py`：不设 HOST env、enforce，MCP 传 `context.subject_ref=user:admin` → allow `table:payroll@*`，随后 grain 检查 ok 并带回值；`governance/r9_misc.py` [R1b]：省略主体 → 复检 ok；`runtime/runtime_probe.py` R6 |
| X2 | 高 | 确认 | `dataagent-runtime/.../invoke.py:90-105`、`:378`；`registry.py:56-76`；`dataagent-governance/.../runtime/runtime.py:30-46` | 复检范围由 `resource_fields` 声明决定且不校验：字段名错、字段类型为 `str`/`dict`/`list[dict]` 时静默跳过；应用层 13 个 op、数据层 10 个 op 未声明；治理层 `policy:` 开头的授权不看 id 与 revision，按合成资源 `table@*` 求值，显式 deny `table:secret` 不命中，得到覆盖所有表的 allow；该分支无测试 | `runtime/runtime_probe.py` R1/R2：决策只覆盖 `table:public`，读 `table:secret@r1`，字段名拼错 / str / dict → ok；`governance/r2_policy_bootstrap.py`：`authorization_ref="policy:does-not-exist@r999"` 在 enforce 下读 `table:secret` → ok，`source_sum=3.0`；`s0/repro_nores.py`：`append_task_event` enforce + 伪造授权 → ok |
| X3 | 高 | 确认 | `dataagent-application/packaging/bundle/.mcp.json:3-15`；`dataagent-s0/README.md:21-30`；`test_s0_mcp_e2e.py:368-379` | 应用层 bundle 未注入 `DATAAGENT_ENFORCEMENT_MODE=enforce`，在 preset 中以 warn 运行；无 EgressDecision 时规则原文进入 `inference_request`；场景测试用 `_enforced_app_server` 显式注入 enforce | `s0/repro_app_warn.py`：不设 env → `runtime=warn … leaks SECRET-RULE=True`；设 enforce → False |
| X4 | 高 | 确认 | `dataagent-runtime/.../enforcement.py:223`、`:267-278`、`:319-336`、`:356-371`；`dataagent-application/.../helpers.py:286`；`dataagent-governance/.../governance/sensitivity.py:29-32` | 外发检查：`egress_check` / `guarded_inference` 只认 `content` 键，内容在 `statement`、`table` 等 W0 §5 内容键下时直接放行，挂 deny 决策也不解析；allow_masked 时新增 `content=脱敏结果`，原 `statement` 保留；应用层调用不传 `load_masked`，allow_masked 一律被拒；数据层 egress 引用 0 处；身份证正则用 `\b`，中文紧邻时漏检，手机号与银行卡号不支持 `-`、空格、`+86` | `runtime/runtime_probe.py` R7：deny 决策 + `{"statement":"SECRET TEXT"}` → `allowed=True`，模型收到原文；`governance/r8_egress_hook.py`：allow_masked 后 statement 仍为原文 "…13800138000"；`governance/r6_sensitivity_gaps.py`：5 种写法 findings 为空，vendor_api → allow |
| X5 | 中 | 确认 | `dataagent-governance/.../policy/evaluator.py:81-83`、`:101-103`；`dataagent-runtime/.../enforcement.py:117-165`；`dataagent-governance/.../evaluation/computation.py:233-238` | `field_constraints`、`row_constraints`、`masking_obligations` 只写入决策，读取、复检、外发三处均不执行；可行性评审 §7.2 要求不能落实的约束即拒绝 | `governance/r9_misc.py` [R11]：决策 `field_constraints=['emp']`，DA11.2.3 读出受限列 salary 合计 1099.0 |

另：`DATAAGENT_ENFORCEMENT_MODE` 取值无法识别时静默回落 warn（`dataagent-runtime/.../enforcement.py:69-72`），记为 06 r41 D7。

## 2. dataagent-governance

### 2.1 S0 完成度

| 原子 | 名称 | 状态 | 证据 |
|-|-|-|-|
| DA11.5.1 | 业务验收判据定义 | 部分完成 | `evaluation/criteria_samples.py:191-244`，两段式 `:247-289`；确认入口 `:295-367`，CLI `confirm-criteria`（G5）；`tests/evaluation/test_criteria.py` |
| DA11.5.5 | 端到端业务验收 | 部分完成 | `criteria_samples.py:544-771`；比较器 `adapters/deterministic_evaluators.py`（G1、G2、G3） |
| DA11.5.6 | 验收样本隔离 | 部分完成 | `criteria_samples.py:419-509`；`adapters/local_split_vault.py`（G6） |
| DA12.1.1 | 访问范围检查 | 部分完成 | `governance/access.py:149-168`；`policy/evaluator.py`（X1、X2、X5） |
| DA12.1.4 | 模型上下文可见性与外发控制 | 部分完成 | `governance/access.py:186-317`；`governance/sensitivity.py`（X4） |
| DA11.2.3 | 结果粒度与合并检查 | 已完成 | `evaluation/computation.py:212-521`，带 `resource_fields`（低危 G7） |

Catalog `source_file` 三个文件存在，`def <operation>` 均可找到；注册表启动时校验（`registry.py:35-43`）。

### 2.2 按需

| 范围 | 数量 | 说明 |
|-|-|-|
| 已注册 operation | 0 | — |
| 有内部函数 | 2 | DA12.1.2 `scan_content`、DA12.1.3 `mask_content`（`governance/sensitivity.py`），与 08 §6 约定一致 |
| 未开始 | 46 | DA12.2 6、DA11.4 5、DA11.2 4、DA11.3 4、DA11.5 4、DA11.6 4、DA12.3 4、DA11.1 3、DA12.4 3、DA12.5 3、DA12.6 2、DA12.7 2、DA12.8 2；其中 10 项的 Catalog 源码文件因与 S0 共用而存在 |

治理层 73 项 = FDE 19 + 非 FDE 54，与方案一致。

### 2.3 方案三项落地

| 项 | 状态 | 差距 |
|-|-|-|
| 运行时访问复检 | 部分修复 | `dataagent-runtime/.../invoke.py:375-433`、`enforcement.py:117-165`，off / warn / enforce 与资源闭包校验已实现；X1、X2、X5；`kernel_guard_declared` 不读 env，一律完整复检（符合“未接线不豁免”） |
| 外发检查 | 部分修复 | 钩子在 `enforcement.py:234-373`，应用层经 `helpers.gate_inference_request` 接入；数据层未接入；MCP 原样序列化整个 CapabilityResult；X4 |
| S0 Preset | 部分修复 | 见 §4 |

### 2.4 可行性评审对 08 的缺口

| 条目 | 状态 | 说明 |
|-|-|-|
| §7.1 授权引导与可信上下文 | 部分修复，含新缺陷 | `host_subject_ref` / `host_purpose` 与 `_meta` 优先已实现；`.mcp.json` 未注入 `DATAAGENT_HOST_*`（X1）；`policy:` 引导分支绕过 deny（X2） |
| §7.2 约束落实与派生资源传播 | 未修复 | X5；外发端不读 `visible_fields` |
| §7.3 内核豁免 | 已修复（未接线，默认完整复检） | — |
| §8 完整模型可见输出 | 未修复 | 应用层部分接入，数据层 0 |
| §9 判据确认合同 | 部分修复，含新缺陷 | 入口绑定 digest 与 revision；G5 |
| §10 样本资格与运行清单 | 部分修复，含新缺陷 | 暴露索引按内容寻址、不可逆；无按 `run_id/case_id` 绑定的运行清单，`run_ref` 为随机 uuid；`HostObservations` 为 Agent 可写输入；G2 |
| §6 证据解析路径 | 部分修复 | 锚点只支持 `json_pointer`，`excel_cell` 等一律判 fail（`criteria_samples.py:120-124`） |
| §11 制品与配置注入 | 部分修复 | vendoring 与可复现源码归档 `--check` 通过；`DATA_ROOT` / `WORKSPACE` 只声明不注入；无真实 Mint 安装测试与离线依赖准备 |
| §12 计数与依赖 | 已修复 | 54 / 6 / 48 与 Catalog 一致 |

### 2.5 catalog-snapshot 一致性

`packaging/`、`src/dataagent_governance/`、`packaging/bundle/packaging/`、`packaging/bundle/src/dataagent_governance/` 四份快照均为 6 项，`group / group_name / id / name / operation / s0_family / source_file` 与 Catalog “评测与治理层 + S0” 切片完全相等；sha256 均为 `6aaa1c30…40da`，与 `source-ref.toml` 的 `snapshot_sha256` 一致；`source_sha256` 等于当前 Catalog sha256（`fbd48e5a…c3ae`）。`export_catalog_snapshot.py --check`、`build_source_archive.py --check` 通过；三个 src 树与 bundle 副本 `diff -rq` 无差异。

### 2.6 新缺陷

| # | 严重度 | 确认/疑似 | 位置 | 问题 | 复现 |
|-|-|-|-|-|-|
| G1 | 高 | 确认 | `adapters/deterministic_evaluators.py:243-244`、`:304-318`；`criteria_samples.py:544-549`、`:675` | `CaseResult.notes` 写入金标值（如 "expected 1111.0"、期望判定），不记暴露台账；DA11.5.5 无 `resource_fields`、无需授权，可反复作为金标查询器 | `governance/r3_gold_leak_and_exclusion.py` [R3]：交付全 0，notes 列出全部 4 个金标值，exposed digests 为 0 |
| G2 | 高 | 确认 | `criteria_samples.py:608-613`、`:734-741`、`:755-765`；`governance/access.py:117-118` | 被暴露剔除的未见样本从分母消失：`coverage.total` 取剔除后数量，`limits` 仅在全部剔除时提示；任何读内容的调用（含被拒的外发检查，`_content_covered` 先读内容再判覆盖）都能把指定样本降级；结合 G1 可只保留答对的样本 | [R4]：冻结 4 个未见样本，按 notes 交付 2 个正确值，对另 2 个 gold ref 调 `check_model_context_egress`（failed，但已记暴露），重新验收 → overall=pass、2/2、coverage 2/2，limits 无剔除说明 |
| G3 | 高 | 确认 | `deterministic_evaluators.py:198-269`；`criteria_samples.py:426-492`、`:664` | 判定族金标为空列表时比较器无可比项，返回 pass；DA11.5.6 不校验 `expected_ref` 是否存在或为空 | `governance/r5_empty_gold_and_errors.py` [R5]：金标 `[]`，交付 verdict=fail、target 任意，两样本均 pass，overall=pass |
| G4 | 中 | 确认 | `governance/sensitivity.py:29-32` | X4 的识别规则部分：身份证 `\b` 与中文、手机号与银行卡号分隔符 | `governance/r6_sensitivity_gaps.py` |
| G5 | 中 | 确认 | `criteria_samples.py:312-343`；`interfaces/cli.py:63-97` | 确认人 `confirmer_ref` 取自请求体，只查白名单；`confirmed_at` 过期与 `authority_ref` 不校验；评审 §9 要求拒绝伪造与过期确认 | `governance/r9_misc.py` [R10]：确认时间 2000-01-01、`authority_ref="anything"`、确认人自报，判据被激活 |
| G6 | 中 | 确认 | `criteria_samples.py:434-442`、`:481-490` | 指纹去重取 `input_ref` 的 revision 字符串而非内容哈希，label revision 下不同样本被当作重复删除；跨角色近重复告警在去重之后执行，为死代码；近重复检测未实现 | `governance/r13_dedup.py`：5 个不同的 `doc:invoice-i@r1` 剩 1 个 |
| G7 | 低 | 确认 | `evaluation/computation.py:336-364` | Join 基数判断依赖书写顺序：`FROM regions JOIN orders` 判 1:N fail，交换顺序 pass，实际输出行数等于订单行数 | `governance/r9_misc.py` [R12] |
| G9 | 低 | 确认 | `evaluation/criteria_samples.py:262-266` | DA11.5.1 第一阶段以 `code="invalid_input"` 返回 `needs_input`；数据层与应用层两段式为 `da03.inference_required` / `da06.inference_required`，调用方按错误码区分“缺输入”与“需推理”时会误判 | CLI：`draft_acceptance_criteria{delivery_target:"报销判定"}` → `needs_input`，`issues[0].code=invalid_input` |
| G10 | 中 | 确认 | `governance/access.py:139`、`:174`；`evaluation/computation.py:35`；`evaluation/criteria_samples.py:162`、`:384`、`:530` | 6 个输入模型直接继承 `BaseModel`，未设 `extra="forbid"`，未知字段被静默忽略；数据层与应用层 45 个输入模型均为 forbid；违反 05 准入规则 | CLI：`check_access_scope{resource_ref:"file@*", bogus:1}` → ok；`append_task_event` 加 `bogus` → `invalid_input` |
| G8 | 低 | 确认（错误码）/ 疑似（`report_separately`） | `dataagent-runtime/.../invoke.py:449-459`；`criteria_samples.py:621`、`:669-683`、`:770` | draft 判据或未冻结集合验收返回 `execution_unknown`（提示 do not retry blindly），应为 invalid_input 或前置条件错误；单个样本金标缺失使整次验收报 FileNotFoundError；`report_separately` 下 unknown 仍计入通过率分母 | `governance/r5_empty_gold_and_errors.py` [R5b][R7] |

## 3. dataagent-runtime

### 3.1 完成度

| 项 | 状态 | 证据 |
|-|-|-|
| invoke（08 §4.1） | 部分完成 | `invoke.py:299-474`（R3） |
| 注册表与 Catalog 一致性 | 已完成 | `registry.py:45-159`；同名不同 spec 拒绝，同 spec 幂等（`:72-75`） |
| 存储端口与适配器 | 部分完成 | `ports/*`、`adapters/sqlite.py`、`local_content.py`；R4、R6 |
| InferencePort | 部分完成 | `ports/inference.py` 只有 Protocol，无适配器（`agent_provided` 在数据层）；X4 |
| 访问复检（allow、未过期、覆盖、用途） | 部分完成 | `enforcement.py:117-165`；X1、X2、X5 |
| 外发检查 | 部分完成 | `enforcement.py:234-373`；X4 |
| 内核路径须宿主声明 | 已完成 | `enforcement.py:134-137`；单独的 `kernel_session_id` 不构成豁免，有测试 |
| 宿主权威（B7） | 部分完成 | `invoke.py:276-296`，只在 `resource_fields` 非空路径上盖章（`:378-379`）；无资源 op 的 handler 读到调用方伪造身份 |
| W0 §1 codec | 部分完成 | 表 codec `ports/tabular.py`（R6）；文档与来源映射 codec 在数据层 |
| W0 §2–§4 | 不在本包 | 在 `dataagent-application` |
| W0 §5 模型可见输出边界 | 部分完成 | `EGRESS_CONTENT_KEYS` 只在应用层 `helpers.py:115`；X4 |
| W0 §6 P2 与宿主注入 | 部分完成 | `enforcement_from_env`、`DATAAGENT_HOST_*` 已实现；`mint.toml [metadata.env]` 只声明；X1 |
| 打包 | 部分完成 | R7 |

### 3.2 新缺陷

X1、X2、X4、X5 的 runtime 部分见 §1。

| # | 严重度 | 确认/疑似 | 位置 | 问题 | 复现 |
|-|-|-|-|-|-|
| R1 | 中 | 疑似 | `enforcement.py`（前缀覆盖） | 以 `:` 作前缀边界，`table:orders@*` 覆盖 `table:orders:secret`；取决于 id 命名约定 | 读代码 |
| R2 | 中 | 确认 | `invoke.py:407-409`、`:447-448`；`errors.py:32`；`ports/tabular.py:122-125` | 异常逃出 invoke：handler 抛 code 无命名空间或 message 为空的 `CapabilityError` 时，`to_issue()` 在 except 中构造 Issue 抛 ValidationError；`access_recheck` 无 try，决策行损坏或 resolver 抛异常直接冒出；MCP 返回 -32603，CLI 打 traceback；`output_model` 不校验，任意 dict 包装为 ok | `runtime/runtime_probe.py` R4/R5：`CapabilityError("oops","bad")`、`CapabilityError("da.x","")`、损坏的 `ad:bad` 行均抛出；`runtime/invoke_out.py`：错误输出类型 → `ok {'anything': 'goes'}` |
| R3 | 中 | 确认 | `adapters/sqlite.py:57-61`、`:120-140` | `save_content_addressed` 的 `find_by_digest` 在事务外且早于 `expected_revision` 检查：过期 `expected_revision` + 相同内容不报冲突；A→B→A 返回旧 `r1 existing=True`，当前仍为 B；查找与写入间有 TOCTOU；数据层适配器已修（`dataagent-data/.../storage/sqlite.py:231-270`，r4-review #10），runtime 副本未修，治理层使用该副本（`dataagent-governance/.../runtime/runtime.py:122`）；`with connect()` 不关闭连接 | `runtime/runtime_probe.py` R8：A again + expected r2 → `('r1', {'v':'A'}, True)`，current `('r2', {'v':'B'})`；过期 r1 存 B → `('r2', …, True)` |
| R4 | 中 | 确认 | `adapters/gold_ledger.py:42-53`、`:55-66`、`:106-120` | 金标暴露台账读改写无锁，并发丢记录；文件损坏或截断时 `_load` 静默返回空，下次写入清空不可逆的暴露历史（08 §5.2），已暴露样本重新成为 unseen | `runtime/ledger_race.py`：4 进程 × 20 次，期望 80 条，实得 25；截断后一次 `register()`，D 的暴露记录为 0 |
| R5 | 中 | 确认 | `ports/tabular.py:122-148`、`:172-173`；`local_content.py:81-88` | codec：非 dict 载荷时 `invalid_input(..., action=…)` 自身抛 TypeError，错误码退化为 `execution_unknown`；未知版本报 `unsupported`，W0 §1.1 规定为 `invalid_input`；`row_meta` 元素非 dict（如 `"total"`）静默当作 `detail` 参与聚合，违反 unknown 不可聚合；重复 `field_id` 被接受，`row_dict` 丢列；内容读取不校验 digest | `runtime/runtime_probe.py` R10/R11：`decode_table_payload([1,2])` 抛 TypeError；`row_meta=["total",None,5]` → 全为 detail；重复 id → `{'a': 2}`；改写对象文件后 `get` 返回 `{"x":999}` |
| R6 | 中 | 确认 | `packaging/bundle/src/dataagent_runtime/{enforcement,runtime}.py`、`adapters/local_content.py` | runtime 自身 bundle 落后于 src：缺 r38/r40 外发内容地址绑定（拒绝时仍 raise `_EgressDenied`，无内联内容 digest 校验）、金标读取钩子与 `gold_ledger.py`；`source-ref.toml` 要求可追溯，实际不可；data / application / governance 三个 bundle 内的 runtime 副本与 src 一致 | `diff -rq src/dataagent_runtime packaging/bundle/src/dataagent_runtime`：3 文件不同，1 文件缺失 |

## 4. dataagent-s0

| 项 | 状态 | 证据 |
|-|-|-|
| bundle 名称与版本 | 已完成 | `dataagent-s0/mint.toml:17-19` 与三个 `packaging/bundle/mint.toml:2-3` 均为 `dataagent/{data,application,governance}-layer@0.1.0` |
| 路径 | 已完成 | 三个 path 指向 `../dataagent-*/packaging/bundle`；vendored 源码与五个包 src `diff -rq` 无差异 |
| Mint 解析 | 部分完成 | mint 0.1.26 在临时镜像中 `mint pack --offline` 四包成功；`mint add --dry-run` 需先 `mint trust` 写 `~/.mint`，沙箱禁写，未验证依赖解析与安装计划 |
| 发布后可安装 | 未完成 | 打包后 manifest 保留 `"path": "../dataagent-application/packaging/bundle"`，离开仓库不可安装；README:37-39 已声明；不满足可行性评审 §13 第 4 波次 |
| Skill 引用的 operation | 已完成 | 32+13+6 个 operation 覆盖两个 S0 Skill 与 6 个 bundle Skill 中的全部反引号名 |
| 判定族覆盖（Catalog 14 项） | 部分完成，2/14 | 只有 `extract_fields_to_schema`、`anchor_extracted_values`；缺 `define_business_rules`、`segment_document`、`maintain_source_anchors`、`register_extraction_schema_version`、DA03.15.*、DA03.16.*；“规则”步骤误用计算族的 `bind_metrics_and_dimensions` |
| 计算族覆盖（Catalog 17 项） | 部分完成，9/17 | 缺 `classify_table_rows`（W0 §8 第 2 步排除合计行，按 Skill 执行可能把合计行求和）、`extract_irregular_excel`、`inspect_workbook_calc_state`、`detect_workbook_regions`、`recover_headers`、`parse_time_and_filters`、`identify_calculation_ambiguities`、`generate_clarification_questions` |
| 骨干项 | 部分完成 | 两个 Skill 均未写 DA04.1 轨迹与 `ocr_*`；计算族 Skill 未写 `check_model_context_egress`，而 `define_metric_formula`、`bind_metrics_and_dimensions` 是两段式推理 |
| 以 enforce 运行 | 未完成 | X3 |
| 共享 data_root | 疑似未完成 | README:31-33 称三进程默认共享 `<workspace>/.dataagent/`；bundle 均未注入 `DATAAGENT_DATA_ROOT`，结果取决于 Mint 拉起子进程的 cwd；无场景验证 |
| 文档 | 部分完成 | README:44 把 `dataagent/governance-layer` 写成 `data/governance-layer` |

## 5. dataagent-scenarios

### 5.1 场景覆盖

| 测试 | 链路 | 真实跨层 | 断言强度 |
|-|-|-|-|
| `gate::test_all_32_data_atoms_pass_the_recheck_with_a_covering_decision` | 32 个数据层原子过测试专用 gate 后进 data invoke | 进程内；gate 只在测试包 | 弱：24 次 `invalid_input`、2 次 `dependency_unavailable`，6 次到达 handler，断言接受 `failed`（S1） |
| `gate::test_recheck_rejects_without_decision` | `access_recheck` 单元 | 否 | 中 |
| `gate::test_recheck_rejects_expired_or_uncovered_or_wrong_purpose` | 过期、不覆盖、用途不符 | 否 | 中 |
| `gate::test_parse_delimited_file_executes_under_enforce` | 治理层铸决策 → gate → parse | 进程内两层 | 强 |
| `gate::test_product_path_rechecks_on_the_shared_decision_store` | 治理层铸决策 → 数据层产品路径复检（共享 `decisions.sqlite3`） | 进程内两层 | 强 |
| `gate::test_all_resource_reading_atoms_are_declared` | `resource_fields` 与 gate 映射一致 | 否（静态） | 中 |
| `gate::test_infer_field_types_profile_branch_is_gated` | profile 分支复检 | 进程内两层 | 强 |
| `gate::test_rebound_table_content_is_denied_under_the_covering_decision` | 资产与内容闭包重绑被拒 | 进程内两层 | 强 |
| `cross_layer::test_compute_family_chain_produces_acceptance_report` | parse → access → grain → criteria → isolate → acceptance | 进程内；两个 data_root 手工复制衔接 | 弱（S4） |
| `mcp::test_three_bundles_over_mcp_in_skill_order` | 三进程 initialize/tools；access → parse 拒绝分支 → engine → 两段式第一段 → 判据第一段 | 子进程；应用层非 enforce、不共享 data_root | 中：止于 needs_input |
| `mcp::test_judgment_family_three_bundle_mcp_to_acceptance_report` | access → parse → 外发剥离 → egress allow → 两段式 → `evaluate_scalar_expression` → 判据 + CLI 确认 → isolate → acceptance | 子进程；记录、证据源、规则、金标手造，数据层产物只取一个数字 | 中：只覆盖 pass |
| `mcp::test_compute_family_three_bundle_mcp_to_acceptance_report` | access → parse → `execute_duckdb_sql` → 判据 + CLI 确认 → isolate → acceptance | 子进程；SQL spec 手写，无口径绑定与 engine_binding；金标由产物反推 | 中：只覆盖 pass（S3） |

### 5.2 未覆盖链路

1. 判定族（W0 §7）：PDF 接入 → `segment_document` → `extract_fields_to_schema` → `define_business_rules` → 表达式；字段 missing → verdict unknown → 按 `unknown_policy` 计分。
2. 计算族（W0 §8）：`extract_irregular_excel`、合并单元格、`classify_table_rows`、`infer_field_types`、`define_metric_formula`、`bind_metrics_and_dimensions`、`generate_single_table_sql` 口径校验、`acquire_and_align_engine`。
3. `check_result_grain_and_merge` 经 MCP；进程内只测透传表的 pass。
4. 报告步骤：`compose_document_report`、`export_report_format`、`build_result_workbook`。
5. 外发 allow_masked / deny（如 vendor_api 加敏感字段）；现有场景只测 local allow。
6. 冷启动：空 data_root 直接 enforce，经 MCP / CLI 装载策略后首次判定。
7. 验收负例：fail、unknown、超时计入分母、金标暴露降级为 regression。
8. 制品层（可行性评审 §11 第 4 条）：经 Mint loader 与 bundle `.mcp.json`（`uv run --frozen --project $PKG`）拉起；不注入 `DATAAGENT_DATA_ROOT` 时的默认共享；宿主 cwd 不同；缺依赖。
9. DA04.1 轨迹。

### 5.3 新缺陷

| # | 严重度 | 确认/疑似 | 位置 | 问题 | 复现 |
|-|-|-|-|-|-|
| S1 | 中 | 确认 | `dataagent-scenarios/tests/test_data_layer_gate.py:239` | “32 原子全部经复检”断言过弱：24 次授权调用以 `invalid_input` 失败、2 次 `dependency_unavailable`，handler 与产品路径复检未执行（产品路径先校验输入后复检）；拒绝分支测的是测试专用 gate | `s0/probe/test_probe32.py`：`{('failed','invalid_input'): 24, ('ok',''): 6, ('failed','dependency_unavailable'): 2}` |
| S2 | 中 | 确认 | `dataagent-scenarios/src/dataagent_scenarios/gate.py:7-9` | docstring 称 S0 组合中不会有调用在不可解析的授权下运行；gate 只在测试包，preset 不含；产品路径上 10 个无 `resource_fields` 的数据层原子在 enforce 下接受伪造授权（X2） | `s0/repro_nores.py` |
| S3 | 中 | 确认 | `test_s0_mcp_e2e.py:698-718`、`:729`、`:751`；`dataagent-application/.../execution/sql.py:136`；`dataagent-s0/skills/dataagent-s0-compute/SKILL.md:34-35` | 计算族场景绕过口径绑定：spec 手写，无 engine_binding 与 RequirementSpec；`execute_duckdb_sql` 只在有 engine_binding 时校验，带变换与额外过滤的 SQL 可执行；与 Skill “SQL 必须绑定 engine_binding 与指标固定过滤”不符；金标 `metric_id` 取自产物 `target_ref`；场景用 `file@*` 决策读 `table:*` 仍通过（07 r41 A2） | `s0/repro_app_enforce.py`：`SELECT SUM(c3)*2 … WHERE c2='north'` → `ok 200.0 []`；`execute_duckdb_sql bogus auth: ok 300.0 []` |
| S4 | 中 | 确认 | `test_cross_layer.py:59-61`、`:139`、`:170-171`、`:289-297` | 进程内计算族链路同义反复：交付值由金标期望值构造，grain 检查的 output_table 即输入表；两层用不同 data_root 靠 `content.put` 衔接，与共享 data_root 的设计相反 | 读代码：`expected = 100.0*(...)` 直接写入 `computed_result.value` |
| S5 | 中 | 确认 | `dataagent-scenarios/pyproject.toml:20-21`；`dataagent-scenarios/uv.lock`；`dataagent-application/packaging/bundle/uv.lock`；`test_s0_mcp_e2e.py:43-51` | scenarios 锁 duckdb <2、sqlglot <27（来自治理层约束），应用层在 duckdb 1.5.6 / sqlglot 26.33 下测试，bundle 发布 2.0.0 / 30.29；口径校验依赖 sqlglot AST，W0 §8 写 engine 2.0.0；MCP 子进程以 `sys.executable -m` 加载源码包，bundle `.mcp.json`、vendored 副本与 bundle lock 未执行；兄弟包以 `[tool.uv.sources]` editable path 引用 | 对比各 `uv.lock`；场景输出 `engine_version: 1.5.6` |
| S6 | 低 | 确认 | `dataagent-scenarios/pyproject.toml:7`；`dataagent-scenarios/README.md:12-14`；`test_cross_layer.py:3`、`:329` | 文档漂移：描述仍写 data + governance；README 称 MCP 测试只到验收准备，实际已到 AcceptanceReport；注释仍写“应用层完成前”“完成后接入” | 读文件 |

## 6. 测试覆盖缺口

- 治理层 117 例的 `conftest.rt` 固件均注入宿主身份，未测打包后的真实配置（X1）。
- 无测试：`policy:` 引导分支；空金标；notes 泄漏金标；部分样本被剔除后的分母；确认时间过期与确认人自报；中文语境与带分隔符的敏感号码；label revision 去重；约束落实。
- 复检与外发测试多直接调用 `egress_check` 并自构 `load_masked`，未经应用层或数据层真实调用方验证外发闭环。
- 前置条件类测试只断言消息子串（如 "active"、"frozen"），不断言错误码。
- runtime 75 例集中在已知攻击形状；无 `resource_fields` 声明错误、`content` 以外内容键、subject 缺省、约束义务、handler / resolver 异常、输出类型校验、A→B→A 与过期 `expected_revision`、台账并发与损坏、codec 非 dict 载荷与 `row_meta`、bundle 与 src 同步的测试。
- runtime 测试在包目录留下 `.dataagent/db/*.sqlite3`，疑似有测试走 `default_runtime()` 的 cwd 路径。
- `test_r24/35/38/40_fixes.py` 共 48 例为历轮回归，正反例较完整；这些轮次只能从测试文件名与 §12 修订记录追溯。

## 7. 复现

脚本在 [r41-repro/](r41-repro/)：

| 目录 | 脚本 | 对应 |
|-|-|-|
| `governance/` | `common.py`（夹具）、`r1_wire_identity.py`、`r2_policy_bootstrap.py`、`r3_gold_leak_and_exclusion.py`、`r5_empty_gold_and_errors.py`、`r6_sensitivity_gaps.py`、`r8_egress_hook.py`、`r9_misc.py`、`r13_dedup.py`、`compare_snapshot.py` | X1、X2、X4、X5、G1–G10、§2.5 |
| `runtime/` | `runtime_probe.py`、`invoke_out.py`、`ledger_race.py`、`resfields.py` | X1、X2、X4、R2–R5 |
| `s0/` | `ops.py`、`repro_app_warn.py`、`repro_app_enforce.py`、`repro_nores.py`、`count32.py` | X2、X3、S2、S3、§4 |

S1 的治理探针源码可在提交 `fbe24d8` 查阅。

`governance/` 脚本以自身目录为 `sys.path`，可直接运行：

```bash
cd packages/capabilities/dataagent-governance && .venv/bin/python ../../../docs/research/dataagent-2026-11-03/08-governance-layer-build/r41-repro/governance/r2_policy_bootstrap.py
```

`runtime/`、`s0/` 中部分脚本含本机绝对路径与 `/tmp/claude-502/` 临时目录，按需改路径后用对应包的 `.venv/bin/python` 运行。
