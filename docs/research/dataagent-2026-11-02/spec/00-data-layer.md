# 数据层模块拆分（DA01–DA04）

> 依据：`Pluggable-DataAgent.md`（飞书 r953，阶段性定稿）。本文只拆数据层四个模块的**接口、目录与代码结构**；能力语义以主文档为准，本文不重新定义。

## 0. 通用约定

### 0.1 引用类型（全层统一）

所有能力的输入输出一律传**引用**，不传裸数据：

| 类型 | 字段 | 说明 |
|-|-|-|
| `SourceRef` | `source_id, kind, locator, version?` | `kind ∈ sql \| http \| mcp \| fs \| browser \| repo \| queue` |
| `ConnRef` | `conn_id, source_id, caps[]` | 连接句柄的**引用**，凭据不进上下文 |
| `SchemaRef` | `schema_id, source_id, hash` | 结构快照，`hash` 用于判漂移 |
| `DataRef` | `data_id, schema_ref, rows, hash, materialized` | 结果集引用；未落盘时 `materialized=false` |
| `FileRef` | `file_id, path, mime, size, hash` | 文件 |
| `DocRef` | `doc_id, file_id, page_map[]` | 文档（带页/章节映射） |
| `Anchor` | `doc_id, page?, section?, span?, cell?` | 原文锚点，**只回指不改写** |
| `RecordSet` | `schema, batch_size, cursor?` | 流式记录集，必须可续读 |

### 0.2 三类操作与权限

| 前缀 | 语义 | 权限 |
|-|-|-|
| `describe_` / `get_` / `list_` / `search_` | 只读、可重放 | A0 自动放行 |
| `read_` | 只读、可重放 | A0 自动放行 |
| `write_` / `apply_` / `register_` | 有副作用 | 需档位判定（DA15） |

**工具命名即权限**：命名与档位不一致时，以命名为准，并在注册期报错。数据层只有 `register_`（目录登记）与 `write_`（快照落盘）两类写操作。

### 0.3 错误模型

统一返回 `Err{kind, retryable, detail}`：

| kind | 含义 | 处理 |
|-|-|-|
| `unavailable` | 源不可达/超时 | 可重试 |
| `unauthorized` | 凭据无效/越权 | 不重试，转人 |
| `invalid_input` | 参数或数据不合规 | 不重试，修参数 |
| `not_implemented` | 该源不支持此能力 | 不重试，换路径 |
| `partial` | 部分成功 | 携带已完成部分 + 断点 |
| `unknown` | 副作用状态未知 | **不重放**，只查询与对账 |

### 0.4 打包形态

| 模块 | 形态 | 说明 |
|-|-|-|
| DA01 | bundle `dataagent-connectors` | 硬组件随包，`skills/` 给默认做法 |
| DA02 | bundle `dataagent-profiler` | 同上 |
| DA03 | bundle `dataagent-ontology` | 同上 |
| DA04 | **非包** | 由 AgentOS 存储承接，本层只给事件 schema 与适配层 |

---

## 1. DA01 数据接入

**模块定义**：把外部数据源变成可引用的数据引用。不解释业务含义，不建立语义。

### 1.1 目录结构

```
packages/capabilities/dataagent-connectors/
├── mint.toml                    # 能力清单：工具、版本、评测集引用
├── README.md
├── packaging/source-ref.toml    # 源码仓库 + commit + subdir + digest
├── skills/da01-access/SKILL.md  # 软组件：默认做法与失败处置
├── src/dataagent_connectors/
│   ├── contracts.py             # SourceRef/ConnRef/DataRef/RecordSet/Err
│   ├── registry.py              # kind → adapter 路由 + 能力标签
│   ├── tools/                   # MCP 工具入口：只做校验与分派
│   │   ├── describe.py          # describe_source / describe_schema
│   │   ├── read.py              # read_rows / read_sample
│   │   ├── parse.py             # parse_file / parse_pdf / ocr_page
│   │   ├── catalog.py           # register_asset / register_owner / register_freshness
│   │   ├── incremental.py       # read_incremental / subscribe_cdc
│   │   ├── env.py               # list_resources / read_resource / normalize
│   │   ├── probe.py             # list_actions / describe_constraints / describe_limits
│   │   └── credential.py        # proxy_call / register_ownership / rotate
│   ├── adapters/                # 可替换后端，实现同一 Protocol
│   │   ├── sql/{duckdb.py, dbapi.py, mcp_sql.py}
│   │   ├── http/{rest.py, auth.py}
│   │   ├── mcp/{client.py, tools.py}
│   │   ├── fs/{local.py, glob.py}
│   │   ├── browser/{cdp.py}
│   │   ├── repo/{git.py, ci.py}
│   │   └── queue/{kafka.py, webhook.py}
│   ├── parsers/{excel_regular.py, excel_irregular.py, csv_tsv.py, jsonl.py, pdf_text.py}
│   ├── ocr/engine.py
│   ├── catalog/store.py
│   ├── incremental/{cursor.py, cdc.py, dedupe.py}
│   ├── env/{enumerate.py, normalize.py}
│   └── credential/{proxy.py, ownership.py, rotate.py}
└── tests/conformance/
```

### 1.2 代码结构规则

1. `tools/` 只做三件事：参数校验 → 调 `registry` 拿 adapter → 把结果包成 `Ref`。**不写业务逻辑**。
2. `adapters/` 每个后端实现同一 `Protocol`；新增一种源 = 新增一个 adapter + 一条 registry 路由，不改工具层。
3. `parsers/` 是纯函数（`bytes → RecordSet + layout`），不碰网络与凭据，便于单测与离线回放。
4. 所有 adapter 返回 `(Ref, Err)`，禁止抛异常穿过工具边界。
5. `credential/` 独立成模块：工具层拿不到明文密钥，只能拿 `ConnRef`。

### 1.3 能力组接口

| 组 | 工具签名 | 输入 | 输出 | 失败 | 形态 |
|-|-|-|-|-|-|
| DA01.1 来源连接 | `describe_source` / `open_connection` | `SourceRef, opts` | `ConnRef` | `unavailable/unauthorized` | 硬 |
| DA01.2 结构读取 | `describe_schema` | `ConnRef` | `SchemaRef + 表/字段/类型/键` | `not_implemented` | 软 |
| DA01.3 数据读取 | `read_rows` / `read_sample` | `ConnRef, 字段集, 条件, 分页/采样` | `RecordSet(cursor)` | `partial` | 硬 |
| DA01.4 文件解析 | `parse_file` | `FileRef` | `RecordSet + layout{page,cell}` | `invalid_input` | 硬 |
| DA01.5 OCR | `ocr_page` | `FileRef, 页号` | `文本 + box[]` | `unavailable` | 硬 |
| DA01.6 资产目录登记 | `register_asset` | 资产引用 + 位置/维护者/承诺 | 目录条目 | `conflict` | 软 |
| DA01.7 增量与事件接入 | `read_incremental` / `subscribe_cdc` | `水位` / 订阅配置 | 增量 `RecordSet + 新水位` | `partial` | 软 |
| DA01.8 环境资源接入 | `list_resources` / `read_resource` | 环境地址 | 类结构化资源记录 | `unavailable` | 软 |
| DA01.9 能力探测 | `list_actions` / `describe_constraints` / `describe_limits` | 资源引用 | 动作与限制清单 | `not_implemented` | 软 |
| DA01.10 凭据代理与归属 | `proxy_call` / `rotate` | `凭据引用` | 代调用结果（密钥不出域） | `unauthorized` | 硬 |

### 1.4 原子能力输入输出

| 编号 | 原子能力 | 输入 | 输出 |
|-|-|-|-|
| DA01.1.1 | 数据库连接 | `dsn_ref, pool_opts` | `ConnRef` |
| DA01.1.2 | API 连接 | `base_url, auth_ref` | `ConnRef(带会话)` |
| DA01.1.3 | MCP 连接 | `server_ref, tool_filter` | `ConnRef + tools[]` |
| DA01.2.1 | 数据库 Schema 读取 | `ConnRef` | `SchemaRef{tables,columns,pk,fk}` |
| DA01.2.2 | API 结构读取 | `ConnRef, endpoint?` | `SchemaRef{params,fields}` |
| DA01.2.3 | MCP 工具能力探测 | `ConnRef` | `tools[{name,input_schema}]` |
| DA01.3.1 | 条件读取 | `ConnRef, cols, filter, limit` | `RecordSet` |
| DA01.3.2 | 分页读取 | `ConnRef, cursor, page_size` | `RecordSet + next_cursor` |
| DA01.3.3 | 采样读取 | `ConnRef, cols, n 或 pct` | `RecordSet(sample)` |
| DA01.4.1 | 规整 Excel 解析 | `FileRef, sheet?` | `RecordSet + cell_map` |
| DA01.4.2 | 不规则 Excel 提取 | `FileRef` | `TableBlock[]`（坐标 + 原始格） |
| DA01.4.3 | CSV/TSV 解析 | `FileRef, delim?, encoding?` | `RecordSet` |
| DA01.4.4 | JSON/JSONL 解析 | `FileRef, jsonpath?` | `RecordSet(保留嵌套)` |
| DA01.4.5 | 文本型 PDF 解析 | `FileRef, 页范围` | `文本 + 版面 box[]` |
| DA01.5.1 | 扫描 PDF OCR | `FileRef, 页范围, lang` | `文本 + box[] + conf` |
| DA01.5.2 | 图片 OCR | `FileRef, lang` | `文本 + box[] + conf` |
| DA01.6.1 | 资产目录登记 | `资产引用, 位置` | 目录条目 `asset_id` |
| DA01.6.2 | 维护者与使用条件登记 | `asset_id, owner, 使用条件` | 更新后条目 |
| DA01.6.3 | 更新承诺与新鲜度登记 | `asset_id, 承诺周期, 实测新鲜度` | 更新后条目 |
| DA01.7.1 | 游标/水位增量读取 | `ConnRef, 水位` | `RecordSet + 新水位` |
| DA01.7.2 | CDC/事件接入 | `订阅配置` | `事件流句柄` |
| DA01.7.3 | 迟到与重复事件处理 | `事件批次, 去重键` | 有序去重批次 |
| DA01.8.1 | 资源枚举 | `环境地址, 类型` | `资源清单[{id,type,name}]` |
| DA01.8.2 | 资源读取 | `资源 id` | 原始对象（文件/JSON/页面快照） |
| DA01.8.3 | 类结构化归一 | 原始对象 | `RecordSet(统一字段/层级/元数据)` |
| DA01.9.1 | 动作能力枚举 | `资源引用` | `[动作名 + 语义]` |
| DA01.9.2 | 参数与约束探测 | `资源引用, 动作名` | `{参数, 必填, 约束}` |
| DA01.9.3 | 限流与配额探测 | `资源引用` | `{rps, 并发, 配额, 重置窗口}` |
| DA01.10.1 | 凭据代理与不落地 | `凭据引用, 调用意图` | 调用结果（无明文密钥） |
| DA01.10.2 | 资源归属登记 | `资源引用, 主体` | 归属记录 |
| DA01.10.3 | 轮换与失效 | `凭据引用` | 新版本 + 旧版本作废回执 |

---

## 2. DA02 数据准备与探查

**模块定义**：把接入的原始数据变成可信、可解释、可追溯的结构。不定义业务含义（那是 DA03），不执行查询（那是 DA07）。

### 2.1 目录结构

```
packages/capabilities/dataagent-profiler/
├── mint.toml
├── skills/da02-prep/SKILL.md
├── src/dataagent_profiler/
│   ├── contracts.py            # TableBlock / Profile / Lineage / Anchor
│   ├── tools/
│   │   ├── locate.py           # detect_blocks（1.x）
│   │   ├── recover.py          # recover_header / expand_merges / classify_rows（2.x）
│   │   ├── reshape.py          # transpose / pivot / unnest / append（3.x）
│   │   ├── profile.py          # profile_table / profile_column / infer_type（4.x）
│   │   ├── join.py             # find_keys / match_coverage / probe_cardinality（5.x）
│   │   ├── clean.py            # dedupe / cast / standardize / fill（6.x）
│   │   ├── lineage.py          # import / extract_sql / collect / persist（7.x）
│   │   ├── doc.py              # slice / anchor / extract_fields（8.x、12.x）
│   │   ├── drift.py            # diff_schema / check_compat / suggest_mapping（9.x）
│   │   ├── repair.py           # propose / verify / learn_rule（10.x）
│   │   ├── snapshot.py         # save / as_of（11.x）
│   │   ├── process.py          # 流程勘查（13.x）
│   │   ├── org.py              # 角色与审批链（14.x）
│   │   └── baseline.py         # 现状基线（15.x）
│   ├── profiling/{stats.py, roles.py, granularity.py}
│   ├── repair/{rules.py, verify.py}
│   ├── lineage/{sql_parser.py, graph.py}
│   └── doc/{slicer.py, anchors.py, extractors.py}
└── tests/conformance/
```

### 2.2 代码结构规则

1. **画像（4.x）与修复（6.x、10.x）分离**：画像只读不写，产出 `Profile`；修复产出**新 `DataRef` + 改动清单**，原数据不可变。
2. **锚点是贯穿结构**：8.2 的 `Anchor` 是 DA02 内部通用类型，12.3、13.x、14.x 都复用它，不允许各自造一份。
3. **血缘（7.x）是图存储**，不是嵌套 dict；7.1–7.3 只产生边，7.4 负责版本化落盘。
4. **流程与组织（13.x、14.x）输出的是证据 + 推断**，必须带来源锚点与置信，不能只给结论。
5. 所有「建议类」能力（9.3、10.1、15.x）返回 `{建议, 依据, 置信}`，不直接改数据。

### 2.3 原子能力输入输出

| 编号 | 原子能力 | 输入 | 输出 |
|-|-|-|-|
| DA02.1.1 | 工作簿表块检测 | `FileRef, sheet?` | `TableBlock{range, 置信}` |
| DA02.1.2 | 文档页面表格检测 | `DocRef, 页范围` | `TableBlock[]` |
| DA02.2.1 | 多行表头恢复 | 原始格矩阵 | `{表头行数, 数据起始行}` |
| DA02.2.2 | 合并单元格展开 | 格矩阵 + 合并信息 | 展开后矩阵 + 原合并映射 |
| DA02.2.3 | 明细/合计行识别 | 格矩阵 | 每行类型 `detail \| subtotal \| total` |
| DA02.2.4 | 跨页续表拼接 | `TableBlock[]` | 合并表 + 拼接点 |
| DA02.3.1 | 表格转置 | `RecordSet, 轴` | `RecordSet` |
| DA02.3.2 | 宽长表转换 | `RecordSet, 列组` | `RecordSet(长表)` |
| DA02.3.3 | 嵌套字段展开 | `RecordSet, path` | `RecordSet(扁平)` |
| DA02.3.4 | 同结构表追加 | `RecordSet[]` | `RecordSet + 来源列` |
| DA02.4.1 | 表结构画像 | `DataRef` | `{rows, cols, 主键候选, 空值率}` |
| DA02.4.2 | 字段取值画像 | `DataRef, col` | `{distinct, top-k, min/max, 分布}` |
| DA02.4.3 | 字段类型推断 | 样本值 | `{类型, 置信, 反例}` |
| DA02.4.4 | 时间角色识别 | 字段名 + 取值 + 文档 | `{事件/生效/记录时间}` |
| DA02.4.5 | 记录粒度识别 | `DataRef, 候选键` | `{粒度字段, 唯一性}` |
| DA02.5.1 | 键关系发现 | 两表 | 候选键对 + 置信 |
| DA02.5.2 | 取值覆盖匹配 | 两列 | `{覆盖率, 孤儿率}` |
| DA02.5.3 | Join 基数探查 | 两表 + 键对 | `{1:1,1:N,N:M, 扇出}` |
| DA02.6.1 | 重复记录处理 | `RecordSet, 键` | 去重后 `DataRef` + 冲突清单 |
| DA02.6.2 | 类型转换 | `RecordSet, 目标类型` | 新 `DataRef` + 失败行 |
| DA02.6.3 | 取值标准化 | 列 + 规则 | 新列 + 映射表 |
| DA02.6.4 | 缺失值处理 | `RecordSet, 策略` | 新 `DataRef` + 标记列 |
| DA02.7.1 | 源端血缘导入 | 目录/ETL 元数据 | 血缘边集 |
| DA02.7.2 | SQL 血缘提取 | SQL 文本 | 表级/列级依赖边 |
| DA02.7.3 | 转换血缘采集 | 作业/脚本定义 | 依赖边 |
| DA02.7.4 | 数据血缘维护 | 边集 + 版本 | 版本化血缘图 |
| DA02.8.1 | 章节/表格切分 | `DocRef` | 结构树 + `Anchor[]` |
| DA02.8.2 | 原文引用锚点维护 | 切分结果 + 引用 | `Anchor` 索引 |
| DA02.9.1 | Schema 差异检测 | 旧/新 `SchemaRef` | 差异列表 |
| DA02.9.2 | 接口兼容检查 | 差异 + 使用方清单 | 兼容结论 |
| DA02.9.3 | 字段映射修订建议 | 差异 + 画像 | `{映射, 依据, 置信}` |
| DA02.10.1 | 修复方案生成 | 问题清单 | 可执行步骤序列 |
| DA02.10.2 | 修复前后验证 | 方案 + 样本 | 前后指标对比 |
| DA02.10.3 | 复核反馈转修复规则 | 人工复核意见 | 规则草案 |
| DA02.11.1 | 文件/查询结果快照保存 | `DataRef`/`FileRef` | 不可变快照引用 |
| DA02.11.2 | 源端 as-of/快照引用 | 源 + 时间点 | 快照引用 |
| DA02.12.1 | 按目标结构抽取字段 | `DocRef` + 目标 schema | `{字段: 值, 置信}` |
| DA02.12.2 | 表单/单据键值抽取 | `DocRef` | 键值对 + 位置 |
| DA02.12.3 | 抽取结果原文锚定 | 抽取结果 | 结果 ↔ `Anchor` 绑定 |
| DA02.13.1 | 步骤与触发条件提取 | 访谈 + 材料 | 步骤链 |
| DA02.13.2 | 分支与例外路径记录 | 步骤链 | 分支图 + 例外 |
| DA02.13.3 | 人工步骤识别 | 步骤链 | 人工点标记 |
| DA02.14.1 | 角色与权限现状 | 材料/系统导出 | 角色-权限矩阵 |
| DA02.14.2 | 事实上的决定者识别 | 轨迹 + 访谈 | 关键人 + 依据 |
| DA02.14.3 | 审批链还原 | 单据轨迹 | 审批链 + 例外 |
| DA02.15.1 | 人工耗时与频次 | 工单/日志/访谈 | `{工时, 频次, 区间}` |
| DA02.15.2 | 错误率与返工率 | 样本 | `{比率, 置信区间}` |
| DA02.15.3 | 成本基线 | 工时 × 成本 + 其他 | 成本基线（含口径） |

---

## 3. DA03 业务语义与关系

**模块定义**：把数据结构翻译成业务对象、指标与规则，并给出可判定的口径。不执行查询（DA06/07），不定义动作怎么执行（DA15）。

### 3.1 目录结构

```
packages/capabilities/dataagent-ontology/
├── mint.toml
├── skills/da03-semantics/SKILL.md
├── src/dataagent_ontology/
│   ├── contracts.py            # EntityType/Metric/Rule/ActionType/SemanticVersion
│   ├── tools/
│   │   ├── model.py            # 实体与属性（1.x）
│   │   ├── resolve.py          # 身份对齐（2.x）
│   │   ├── relate.py           # 关系与 Join（3.x）
│   │   ├── define.py           # 指标/维度/规则（4.x）
│   │   ├── time.py             # 时间与单位（5.x）
│   │   ├── store.py            # 语义存储与映射（6.x）
│   │   ├── lineage.py          # 语义血缘（7.x）
│   │   ├── history.py          # 历史口径与时点（8.x）
│   │   ├── bootstrap.py        # 导入与冷启动（9.x）
│   │   ├── conflict.py         # 冲突识别（10.x）
│   │   ├── action.py           # 动作语义（11.x）
│   │   ├── rights.py           # 权属模型（12.x）
│   │   ├── evidence.py         # 证据模型（13.x）
│   │   ├── lifecycle.py        # 状态与生命周期（14.x）
│   │   ├── decidability.py     # 可判定性分级（15.x）
│   │   └── scope.py            # 适用范围（16.x）
│   ├── store/{schema.py, versioning.py, index.py}
│   ├── bootstrap/adapters/{dbt.py, metricflow.py, cube.py, bi.py, legacy_sql.py}
│   └── conflict/{detect.py, resolve.py}
└── tests/conformance/
```

### 3.2 代码结构规则

1. **语义对象全部版本化**：`(semantic_id, version, effective_from, effective_to)` 是主键；任何定义变更产生新版本，旧版本不删（8.2 依赖它）。
2. **存储与定义分离**：`tools/` 产生定义，`store/` 负责落盘与索引；`store` 不认识业务语义，只认 schema。
3. **口径是表达式，不是散文**：4.1/4.3 产出的公式必须是可编译到 SQL/QLExpress 的 AST，散文只作 `description`。
4. **边界**：本模块只到「编译成 AST 并给出映射」，真正编译到目标方言与执行归 DA06/DA07。
5. `bootstrap/adapters` 为每种外部语义层一个 adapter，导入结果一律进「草案」而非直接生效。

### 3.3 原子能力输入输出

| 编号 | 原子能力 | 输入 | 输出 |
|-|-|-|-|
| DA03.1.1 | 实体类型定义 | 结构 + 画像 | `EntityType{name, keys, desc}` |
| DA03.1.2 | 实体属性定义 | `EntityType` + 列 | `属性{列, 类型, 单位, 空值语义}` |
| DA03.1.3 | 对象状态定义 | `EntityType` | 状态集 |
| DA03.2.1 | 编码映射 | 两源编码列 | 映射表 + 冲突 |
| DA03.2.2 | 别名匹配 | 名称集合 | 别名簇 + 置信 |
| DA03.2.3 | 跨源实体匹配 | 多源记录 | 同一实体 ID 分组 |
| DA03.3.1 | 实体关系定义 | 两 `EntityType` | `Relation{基数, 方向}` |
| DA03.3.2 | Join 规则定义 | `Relation` + 键 | Join 规则（含过滤条件） |
| DA03.3.3 | 时态关系定义 | `Relation` | 生效区间规则 |
| DA03.4.1 | 指标公式定义 | 业务需求 | `Metric{AST, 依赖, 口径说明}` |
| DA03.4.2 | 维度层级定义 | 业务需求 | `Dim{层级, 汇总规则}` |
| DA03.4.3 | 业务规则定义 | 业务需求 | `Rule{条件 AST, 结论, 例外}` |
| DA03.5.1 | 业务时间定义 | 业务日历 | 时间口径（含边界） |
| DA03.5.2 | 财务日历定义 | 财年配置 | 财年映射 |
| DA03.5.3 | 单位换算定义 | 单位对 | 换算函数 + 精度 |
| DA03.6.1 | 业务语义存储 | 语义对象 | 版本化存储记录 |
| DA03.6.2 | 语义与表列映射 | 语义 + `SchemaRef` | 映射表 |
| DA03.6.3 | 语义与 API/文档映射 | 语义 + 源 | 映射表（含锚点） |
| DA03.7.1 | 指标依赖提取 | `Metric` | 依赖边 |
| DA03.7.2 | 规则依赖提取 | `Rule` | 依赖边 |
| DA03.7.3 | 语义血缘维护 | 边集 + 版本 | 版本化依赖图 |
| DA03.8.1 | 业务生效时间解析 | 定义文本 | `[effective_from, effective_to)` |
| DA03.8.2 | 指定时点语义版本解析 | 时点 | 该时点生效的版本快照 |
| DA03.9.1 | 外部语义层导入 | dbt/MetricFlow/Cube/BI 定义 | 语义草案 |
| DA03.9.2 | 历史口径挖掘 | SQL/报表/Excel 模板 | 指标与过滤草案 |
| DA03.9.3 | 语义草案生成 | 结构 + 画像 + 文档 + 模板 | 实体/指标/关系草案 |
| DA03.9.4 | 待确认项排序 | 草案 | 按影响面 × 不确定性排序的清单 |
| DA03.10.1 | 定义冲突检测 | 语义库 | 冲突清单（同名异义/异名同义/口径重叠） |
| DA03.10.2 | 冲突说明与协调方案 | 冲突 | `{并存 \| 按作用域区分 \| 合并}` + 理由 |
| DA03.11.1 | 动作类型定义 | 业务动作 | `ActionType{name, 语义}` |
| DA03.11.2 | 参数 schema | `ActionType` | JSON Schema（必填/枚举/范围） |
| DA03.11.3 | 前置/后置条件 | `ActionType` | 条件 AST（可判定） |
| DA03.11.4 | 影响面与可逆性 | `ActionType` | `{影响对象集, 可逆性, 回滚方式}` |
| DA03.12.1 | 读/提议/执行三档 | 业务角色 + 动作 | `A0 \| A1 \| A2` 档位表 |
| DA03.12.2 | 委托关系 | 角色 | 委托图（只缩不扩） |
| DA03.12.3 | 审批策略 | 动作 + 影响面 | 审批策略（谁批、几人、超时） |
| DA03.13.1 | 证据类型定义 | 结论类型 | 证据类型清单 |
| DA03.13.2 | 充分性判据 | 结论类型 | 可判定判据（布尔表达式） |
| DA03.13.3 | 证据与结论绑定 | 结论实例 | 证据集 + 充分性结论 |
| DA03.14.1 | 业务对象状态定义 | 业务对象 | 状态集 |
| DA03.14.2 | 状态迁移与回退 | 状态集 | 迁移图（含回退边） |
| DA03.14.3 | 与执行状态机的映射 | 业务状态 | 内核执行状态映射 |
| DA03.15.1 | 可机器化判定 | 条款原文 | 「可编译为表达式」+ 表达式草案 |
| DA03.15.2 | 需人工裁量 | 条款原文 | 「需看附件/需业务判断」+ 判据 |
| DA03.15.3 | 不适用 | 条款原文 | 原因 `纯线下 \| 系统强控 \| 与单据无关` |
| DA03.15.4 | 判定缓存与失效 | 条款 + hash | 缓存命中 / 重判 |
| DA03.16.1 | 适用范围表达 | 条款 | 范围表达式（管哪些单据与场景） |
| DA03.16.2 | 生效前提表达 | 条款 | 前置条件 AST |
| DA03.16.3 | 前置引用与去重 | 前置集合 | 去重后集合 + 引用关系 |
| DA03.16.4 | 前置未知的处置 | 前置求值结果 | `UNKNOWN` 判定（不算满足） |

---

## 4. DA04 任务轨迹与记忆

**模块定义**：把做过的事变成可复用、可回放、可失效的经验与资产。不存业务数据（DA01/02），不存语义定义（DA03）。

### 4.1 形态：非包，但需要定义承接契约

DA04 不发布为 bundle，存储由 AgentOS 承接。问题在于**现有内核契约不够用**：

| 内核契约 | 覆盖 | 对 DA04 的缺口 |
|-|-|-|
| `StoreContract::append/read(session, from, limit)` | DA04.1 会话内轨迹 | **只有 session 内游标**，跨会话检索、按作用域分层（个人/任务/企业）没有落点 |
| `ContextSnapshot{session, turn, bytes, caps_versions, content_type}` | DA04.5 的「版本钉定」雏形 | 是 session/turn 粒度，不含**数据版本与语义版本**，无法支撑 5.3 修订同步 |
| 无版本/失效契约 | — | DA04.6 的晋升、冲突、淘汰需要**可变 + 版本化 + 可失效**，现有契约只提供了只增不改 |

结论：DA04 要么推动内核补三层能力（作用域、版本钉定、失效传播），要么在 OS 之上自建索引层。**这是数据层里唯一需要动内核的模块**，建议单独拉一个议题。

### 4.2 目录结构（适配层，非独立包）

```
packages/agent-kernel/extensions/memory/     # 或独立 sidecar
├── schema/
│   ├── event.json            # DA04.1 事件 schema
│   ├── experience.json       # DA04.2/4.3 经验条目
│   └── asset.json            # DA04.4 资产
├── src/memory/
│   ├── append.py             # 写轨迹（复用 StoreContract）
│   ├── scope.py              # 作用域路由：personal / task / org
│   ├── extract.py            # 2.x 提炼
│   ├── verify.py             # 6.x 验证与晋升
│   ├── context.py            # 5.x 上下文包
│   └── index/{by_task.py, by_scope.py, by_version.py}
└── tests/replay/
```

### 4.3 原子能力输入输出

| 编号 | 原子能力 | 输入 | 输出 |
|-|-|-|-|
| DA04.1.1 | 任务事件记录 | `{session, seq, event}` | 追加回执 `{offset}` |
| DA04.1.2 | 查询/工具调用记录 | `{call, params, result_ref}` | 追加回执 |
| DA04.1.3 | 用户纠正记录 | `{原结论, 纠正, 理由}` | 追加回执 |
| DA04.2.1 | 成功查询提炼 | 成功轨迹集 | 查询模板候选 |
| DA04.2.2 | 分析方法提炼 | 成功轨迹集 | 方法候选（步骤 + 判据） |
| DA04.2.3 | 失败经验提炼 | 失败轨迹集 | 反例 / 约束候选 |
| DA04.2.4 | 流程模板提炼 | 同类成功轨迹 | Preset 配置候选 |
| DA04.3.1 | 个人记忆存储 | 条目 + owner | `memory_id` |
| DA04.3.2 | 任务共享记忆存储 | 条目 + task_id | `memory_id` |
| DA04.3.3 | 企业经验存储 | 条目 + org_id | `memory_id` |
| DA04.4.1 | 查询/代码资产保存 | SQL / 代码 + 元数据 | `asset_id` |
| DA04.4.2 | 模型资产保存 | 模型定义 + 参数 | `asset_id` |
| DA04.4.3 | 报表/模板资产保存 | 报表/模板 | `asset_id` |
| DA04.4.4 | 产物来源关联 | 产物 + 依赖 | 来源边集 |
| DA04.5.1 | 任务上下文创建 | 任务 + 版本钉定 + 权限 | `ContextPack{data_v, semantic_v, exp[], grants}` |
| DA04.5.2 | 子任务上下文派发 | `ContextPack` + 子任务 | 裁剪后 `ContextPack` |
| DA04.5.3 | 任务修订同步 | 变更事件 | 新修订 + 失效结果清单 |
| DA04.6.1 | 候选经验验证 | 候选 + 相关样本 | 通过率 + 反例 |
| DA04.6.2 | 作用域晋升 | 通过验证的候选 | 新作用域 + 生效时间 |
| DA04.6.3 | 冲突与污染检查 | 候选 + 认证语义 + 已有经验 | 冲突清单 |
| DA04.6.4 | 经验失效与淘汰 | 经验 + 变更/反例/未用时长 | 降级或淘汰决定 |
| DA04.7.1 | 契约与 Runbook 版本 | 交付物 | 版本记录 |
| DA04.7.2 | 交接材料归属 | 材料 | 归属登记 |
| DA04.7.3 | 现场范围记忆 | 现场 + 经验 | 作用域绑定（该经验只在某现场有效） |

---

## 5. 层内依赖与落地顺序

### 5.1 依赖

```
DA01 接入 ──→ DA02 准备与探查 ──→ DA03 语义
   │                │                 │
   └────────────────┴─────────────────┴──→ DA04 记忆（横向，记录全层产出）
```

- DA02 依赖 DA01 的 `DataRef/SchemaRef`，不直接连源
- DA03 依赖 DA02 的 `Profile`（画像驱动建模），不依赖原始文件
- DA04 不阻塞任何模块，但只有 DA01–03 产出稳定后才有提炼价值

### 5.2 最小可用切片（第一个闭环）

| 顺序 | 能力 | 理由 |
|-|-|-|
| 1 | DA01.1 / DA01.3 / DA01.4 | 能连库、能读表、能解 Excel —— 没有更小的可跑闭环 |
| 2 | DA02.1 / DA02.2 / DA02.4 | 表块识别 + 结构恢复 + 画像，让「读进来」变成「看得懂」 |
| 3 | DA03.1 / DA03.3 / DA03.6 | 实体 + 关系 + 存储，产出第一份可用语义 |
| 4 | DA01.6 / DA02.11 | 目录与快照，让结果可回溯 |

其余能力按场景补：文件类场景补 DA01.5/DA02.12，制度类补 DA02.8/DA03.15，FDE 场景补 DA01.8–10/DA02.13–15。

### 5.3 打包对照

| 模块 | bundle | 含硬组件 | 评测集 |
|-|-|-|-|
| DA01 | `dataagent-connectors` | 连接、读取、文件解析、OCR、凭据代理 | 各类源的连接与解析回归 |
| DA02 | `dataagent-profiler` | 表块识别、结构恢复、历史保留 | 脏表/畸形表恢复基准 |
| DA03 | `dataagent-ontology` | 语义存储与映射 | 语义一致性 + 口径回归 |
| DA04 | 无（OS 承接） | — | 轨迹回放一致性 |
