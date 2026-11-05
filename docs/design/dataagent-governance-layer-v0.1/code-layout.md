# 评测与治理层代码目录提案 v0.1

本文件只提议代码组织，当前不创建以下代码、安装包或运行配置。推荐工作区 `packages/capabilities/dataagent-governance/`，Python 命名空间 `dataagent_governance.*`。共享引用与调用封套沿用 [数据层共享契约](../dataagent-data-layer-v0.1/06-shared-contracts.md)，治理扩展类型见 [README](README.md)。共享契约在实现时提取为可独立依赖的契约包或版本化 schema，不以导入数据/应用模块内部业务代码来共享类型。

## 1. 拟议目录树

```text
packages/capabilities/dataagent-governance/
├── README.md
├── pyproject.toml
├── uv.lock
├── contracts/
│   ├── README.md                    # schema 导出规则
│   └── generated/                   # 从类型生成，非第二份手工权威源
├── src/dataagent_governance/
│   ├── contracts/
│   │   ├── common.py                # 引用共享 CallContext/CapabilityResult
│   │   ├── evaluation.py            # criteria、case、split、report、MetricBundle
│   │   ├── policies.py              # PolicyRef、AccessDecision、gate 与阈值
│   │   ├── changes.py               # request、decision、plan、impact、receipts
│   │   ├── lifecycle.py             # 版本状态、复现清单、回滚与补偿
│   │   └── audit.py                 # 证据链、后端实际粒度、保留与导出
│   ├── ports/
│   │   ├── profiles.py              # DA02 画像与约束统计
│   │   ├── repositories.py          # 版本解析、持久化和原子切换，复用资产拥有者
│   │   ├── sample_vault.py          # 分角色样本读取、隔离、暴露审计
│   │   ├── execution.py             # DA07 隔离运行、dry-run、回执与对账
│   │   ├── identity_policy.py       # 平台/源端身份鉴权与 DA16 授权审批事实
│   │   ├── dependencies.py          # DA05.7 typed 依赖与使用关系
│   │   ├── observation.py           # DA04 实际事件与 DA14 运行窗口
│   │   ├── evaluators.py            # 各类比较/打分/方法诊断与推断实现
│   │   └── audit_storage.py         # 保留锁、追加存储、完整性校验与受控导出
│   ├── evaluation/                  # DA11
│   │   ├── data_quality.py          # DA11.1 字段约束、重复/缺失、跨源对账
│   │   ├── computation.py           # DA11.2 执行表达、口径、粒度合并、对照验证
│   │   ├── methods.py               # DA11.3 统计、预测、仿真与方案适用性
│   │   ├── regression.py            # DA11.4 检索、问数、分析、规则库、引擎一致性
│   │   ├── criteria_samples.py      # DA11.5 正式判据与分角色评测集
│   │   ├── improvement.py           # DA11.6 趋势、贡献、覆盖与交付成本
│   │   ├── shadow.py                # DA11.7 隔离旁路、人工比对、差异归因
│   │   ├── dual_track.py            # DA11.8 结果正确性与真实过程合规
│   │   └── gates.py                 # DA11.9 分环节档位、变更回归、熔断
│   ├── governance/                  # DA12
│   │   ├── access.py                # DA12.1 访问检查、敏感识别、脱敏
│   │   ├── versions.py              # DA12.2 版本政策、决策沉积物与回滚
│   │   ├── feedback.py              # DA12.3 反馈、归因、失效与更新建议
│   │   ├── impact.py                # DA12.4 数据、语义、权限影响
│   │   ├── change_control.py        # DA12.5 写入冲突、生效、撤销/补偿
│   │   ├── reproduction.py          # DA12.6 实际版本绑定与历史可重现性
│   │   ├── change_plans.py          # DA12.7 可审阅变更计划、隔离差异预览
│   │   ├── tuning.py                # DA12.8 Preset 比较、灰度与回退
│   │   ├── cross_tenant.py          # DA12.9 获准通用经验与领域包提案
│   │   ├── audit.py                 # DA12.10 真实证据链、保留、导出、判定依据
│   │   └── blast_radius.py          # DA12.11 影响分级、可逆性、授权阈值草案
│   ├── adapters/
│   │   ├── assets/                  # 数据层版本仓储与内容端口绑定
│   │   ├── samples/
│   │   │   ├── local_split_vault.py # 本地样本角色与访问边界
│   │   │   └── remote_vault.py      # 远程独立验收执行器
│   │   ├── evaluators/
│   │   │   ├── deterministic.py    # 字段/数值/规则确定性比较
│   │   │   ├── retrieval.py        # 排序/召回指标
│   │   │   ├── statistical.py      # 回测、诊断与区间
│   │   │   ├── rubric_model.py     # 模型辅助评分，固定 rubric/模型/提示版本
│   │   │   └── engine_reference.py # 真实权威引擎对照，保留实际粒度
│   │   ├── policies/               # 平台、源端与 DA16 策略/事实适配
│   │   ├── execution/              # 隔离执行、dry-run、回执查询
│   │   ├── observation/            # 实际轨迹、运行窗口、计费/人工记录
│   │   └── audit/
│   │       ├── local_append_store.py # 本地追加与哈希校验，显式有限保证
│   │       └── retention_backend.py  # 具备保留锁等能力的实际后端
│   ├── registry/
│   │   ├── catalog.py              # 67 ID→入口、I/O 类型、依赖/副作用声明
│   │   └── loader.py               # 按需加载组和适配器
│   └── interfaces/
│       ├── python_api.py
│       ├── cli.py
│       ├── http.py
│       └── mcp.py
├── component-specs/
│   ├── evaluation.yaml             # 自拟组级描述，非平台正式 manifest
│   └── governance.yaml
├── presets/
│   ├── rule-library-acceptance.yaml
│   ├── staged-shadow-release.yaml
│   └── asset-change-review.yaml
├── examples/                       # 去标识小样例，不含独立验收金标
├── tests/
│   ├── contracts/                  # 同契约不同实现的共同语义
│   ├── evaluation/                 # 分母、UNKNOWN、不可比、证据不足
│   ├── samples/                    # 关联泄漏、暴露降级、验收金标隔离
│   ├── governance/                 # 权限/用途、版本冲突、范围和幂等
│   ├── audit/                      # 真实粒度、断链、保留保证和脱敏导出
│   └── scenarios/                  # 冻结标准+独立样本的端到端业务结果
└── fixtures/                       # 仅开发/回归 fixture，验收金标不入开发仓库
```

`__init__.py` 等常规文件省略。运行时原件、报告、样本、轨迹、策略副本和导出位于显式配置的受控 `data_root` 或外部后端，不写入源码仓库。独立验收集的金标与开发进程分域；单纯把两个文件夹命名为 train/test 不能提供隔离保证，本地可信边界不足时必须选外部受控执行器或明确其限制。

## 2. 端口和适配边界

| 端口 | 最小职责 | 不可隐含的能力 |
| --- | --- | --- |
| `ProfilePort` | 按版本取 DA02 画像/约束统计，声明采样与覆盖 | 样本统计不等于全量质量证明 |
| `AssetRepositoryPort` | 解析精确版本、写草案、CAS 生效/停用、返回实际回执；由 DA03/04 等资产拥有者适配 | 未保存不能返版本成功；生命周期政策不等于实际内容已存在 |
| `SampleVaultPort` | 角色划分、关联去重、受控读取、曝光台账；验收器专有金标权限 | 修复者不能用验收金标调参；已暴露样本不能继续充作未见样本 |
| `ExecutionPort` | 提交隔离运行/dry-run、声明生产写入禁用、取消与回执对账 | 缺少隔离则拒绝影子副作用；没有 dry-run 就不能返回已试运行 |
| `IdentityPolicyPort` | 解析真实平台主体/源端权限/DA16 委托审批事实，检查用途/资源/动作及决策期限 | 不自己建用户库或发委托；访问允许不等于允许修改或发布 |
| `DependencyPort` | 消费 DA05.7 的 typed edges，保留 basis、版本和覆盖 | 未观测边不当作不存在，不假设遍历结果全量 |
| `ObservationPort` | 读取 DA04 实际事件、DA14 窗口、计费与人工量回执 | 不以模型推理或模拟步骤代替真实已发生事实 |
| `EvaluatorPort` | 方法专属比较/评分/置信区间，记录实现、rubric、模型版本及可比范围 | 模型评分仅辅助，不能自行改正式标准或将无参考案例判真 |
| `AuditStoragePort` | 追加、完整性校验、保留/法律冻结、受控读取与导出、能力等级声明 | 普通文件+哈希不具备 WORM；不宣称不可篡改超出真实后端保证 |

初版可用本地仓储适配器与 SQLite 保存非独立验收元数据；评价程序按需调用统计库或模型，避免把全部评测变成单一模型裁判。正式样本隔离、生产级保留锁和外部授权要求由部署选用满足要求的后端。不可用依赖返回 `dependency_unavailable` 或明确受限报告，不能假返回通过、已发布或已保留。

## 3. 一项能力如何落地

以 `DA11.4.4` 为例：`registry/catalog.py` 注册 `dataagent_governance.evaluation.regression:evaluate_rule_library_regression`，业务输入/输出类型由 `contracts/evaluation.py` 定义；组函数验证冻结判据和样本角色，经 `SampleVaultPort` 取获准回归样本，用 `ExecutionPort` 隔离运行候选/基线，`EvaluatorPort` 计算逐规则/业务分层差异，经 `ObservationPort` 汇总人工与资源记录，再通过资产端口保存实际报告。

报告注明真实运行的样本、依赖与后端版本、未执行范围和未知项。需要条件级依据时只消费后端真实明细，不能由报告器重建一份假 trace。规则库回归结果可供 DA12.8/DA11.9 消费，但不直接调用生产激活。

## 4. 依赖方向与发行粒度

```text
Python/CLI/HTTP/MCP + Registry
                 ↓
      evaluation / governance handlers
                 ↓
      共享契约 + 本层 Port 协议
                 ↑
  资产 / 样本 / 策略 / 执行 / 观测 / 审计 Adapters
```

应用层可消费本层验证/策略接口，本层可通过端口调用应用执行器；二者共同依赖共享契约，各自适配器完成注入，不互相导入应用 handler/runtime 内部模块。DA12.5 消费 DA11 报告或显式验证端口，DA11 读取已经发布的策略事实；避免门禁评估再次触发完整发布控制而循环调用。

`DAxx.y.z` 稳定 ID、Python operation、可替换实现、安装包、Agent 工具和 Preset 是不同粒度。一个工作区可先产出契约、评测、治理等构建产物，重型模型裁判、统计库、权威引擎适配器和生产审计存储作为可选依赖。无需为 67 个 ID 各建一个仓库、进程或发行包；可按独立依赖/维护/部署需要拆包，保留相同 ID 与业务语义。

完整逐项映射见 [atomic-capability-catalog.json](atomic-capability-catalog.json)。发包描述与实际平台适配另行确认；此处没有平台兼容性取证结论。
