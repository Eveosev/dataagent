---
version: v0.2
date: 2026-11-03
baseline: 飞书总规划 r1045、数据层 r14、执行应用层 r8、评测与治理层 r7、持续运行与 FDE 交付 r8
frozen: ../dataagent-2026-11-02/sources/freeze-v0.2-2026-11-03/
---

# Pluggable DataAgent

## 文件

| 文件 | 飞书 | 内容 | 能力组 / 原子 |
|-|-|-|-|
| [00-pluggable-dataagent.md](00-pluggable-dataagent.md) | [总规划](https://modelbest.feishu.cn/docx/TlN4dygs9oJR3Qx1FaictiPEn3c) | 定义、平台对接待决、跨层契约、能力目录、切片、唯一归属、调研参照 | 141 / 458 |
| [01-data-layer.md](01-data-layer.md) | [数据层](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d) | DA01–DA04、DA13 | 51 / 165 |
| [02-application-layer.md](02-application-layer.md) | [执行应用层](https://modelbest.feishu.cn/docx/ReDXdJzLWoihZDxqaO0clUxInKf) | DA05–DA10 | 41 / 126 |
| [03-governance-layer.md](03-governance-layer.md) | [评测与治理层](https://modelbest.feishu.cn/docx/QwN4dFvdroH7X3xI3Eycnkbon3b) | DA11–DA12 | 20 / 73 |
| [04-operations-fde-layer.md](04-operations-fde-layer.md) | [持续运行与 FDE 交付](https://modelbest.feishu.cn/docx/NqS0dcV0CoaatHxJTTFc7amnnke) | DA14–DA18 | 29 / 94 |
| [05-contracts.md](05-contracts.md) | [dataagent-contracts](https://modelbest.feishu.cn/docx/VavsdOWFeoLBFrxOt9JcjAsInDe) | 契约层：定位、内核映射、准入与版本规则、S0 类型与字段、S1/S2 预留 | — |
| [06-data-layer-build-plan.md](06-data-layer-build-plan.md) | [数据层建设方案](https://modelbest.feishu.cn/docx/NvOsd04lAoZk60xY2Kpc4SrYnwf) | S0 数据层 32 项与契约包 core 的实现方案；实施与评审记录索引（§12）；内核组件事件接口提案（附录 A） | — |
| [06-data-layer-build/](06-data-layer-build/) | — | 各轮修复（`rN-fixes.md`）、评审（`rN-review.md`）、优化方案（`rN-plan.md`）与专项审计 | — |
| [07-application-layer-build-plan.md](07-application-layer-build-plan.md) | — | 执行应用层非 FDE 110 项：S0 13 项、按需 90 项、S1 7 项的实现方案；实施与评审记录索引（§13） | — |
| [07-application-layer-build/](07-application-layer-build/) | — | 执行应用层评审与修复记录（`rN-review.md`、`rN-fixes.md`）及复现脚本 | — |
| [08-governance-layer-build-plan.md](08-governance-layer-build-plan.md) | — | 评测与治理层非 FDE 54 项：S0 6 项、按需 48 项的实现方案；运行时访问复检与外发检查；S0 Preset；实施与评审记录索引（§13） | — |
| [08-governance-layer-build/](08-governance-layer-build/) | — | 评测与治理层、`dataagent-runtime`、S0 组合的评审与修复记录及复现脚本；跨包共性问题 | — |
| [09-benchmark-plan.md](09-benchmark-plan.md) | — | 需长期监控的 15 个核心模块：原子组合、参考 benchmark、监控指标；评测集与流程 | — |
| [09-benchmark/](09-benchmark/README.md) | — | 15 个模块的评测任务目录：任务卡、评测集账本、轮次与基线、门槛与趋势看板、校验工具 | — |
| [11-s0-stage-report.md](11-s0-stage-report.md) | — | S0 阶段报告：整体进展与阻断项；Mint 本地安装与端到端测试流程；51 个 S0 原子的测试方法 | 51 |
| [12-unified-cli-research.md](12-unified-cli-research.md) | — | Mint 内 Agent 自装 DataAgent 并经 `dataagent` CLI 调用能力：Mint shell 与沙箱机制、MCP 与 CLI 通道对比、包与命令设计、对 Mint 的诉求 | — |
| [catalog/atomic-capability-catalog.json](catalog/atomic-capability-catalog.json) | [总 Catalog](https://modelbest.feishu.cn/base/AjY0bNRutawmZ0s62MZcUSmQn4f)（多维表格） | 458 项原子：编号、名称、说明、能力组、模块、所在层、形态、FDE、operation、源码文件、切片、S0 闭环族 | 141 / 458 |
| `feishu/` | — | 推送用的飞书格式片段与 `plan.json` | — |

## 生成与同步

```bash
python3 -I docs/research/dataagent-2026-11-03/tools/build.py                      # 快照 → 00–04 与 catalog/
python3 -I docs/research/dataagent-2026-11-03/tools/to_feishu.py                  # 05 → feishu/05-contracts.md
python3 -I docs/research/dataagent-2026-11-03/tools/sync_feishu.py prepare layers # 01–04 → feishu/ 片段与 plan.json
```

- `build.py`：精确匹配替换并断言次数；校验总规划 18 / 141 / 458、各层原子 165 / 126 / 73 / 94、原子一一对应且有 operation 与源码文件、S0 原子 51 项；正文不得含版本标签、指向本文档的链接或飞书标记。00–04 与 `catalog/` 为生成物，不手改。
- 版本只写在文首 frontmatter；飞书以文首 yaml 代码块表示。
- 总 Catalog 多维表格由 `catalog/atomic-capability-catalog.json` 写入（`catalog/feishu-base.json` 记录 base 与表）。
- 飞书有新修改时：先比对线上与本地，合并后再推送。

## 冻结

`../dataagent-2026-11-02/sources/freeze-v0.2-2026-11-03/`：六篇飞书文档导出、总 Catalog 全部记录、`manifest.json`（飞书 revision 与内容哈希、本地文件哈希、Catalog 记录数及与本地编号一致性）。

## 修订

| 项 | 修订 | 位置 |
|-|-|-|
| R1 | 平台对接待决 P1–P7 | 总规划 §2.3 |
| R2 | 跨层契约 `dataagent-contracts`、统一 `LifecycleStatus`、类型完整度门槛；DA01.4.4 与 DA02.3.3 衔接 | 总规划 §2.4；数据层；05 |
| R3 | 8 个概念的唯一归属及相关边界 | 总规划 §4.2；各层 |
| R4 | DA17.2 统一为默认版本；DA03.14 边界；DA18.6/18.7 去掉 FDE 标记 | 各处 |
| R5 | 新增能力组 DA05.9、DA06.8，新增原子 24 项，修改 7 处边界 | 总规划 §三；各层 |
| R6 | 切片：S0 通用只读证据闭环（判定族 / 计算族）→ S1 Mint 包与回写 → S2 持续运行与移交 | 总规划 §4.1 |
| R7 | DA18.6/18.7 发布为 Mint `kind = "skill"` / `kind = "preset"` 包 | DA18；总规划 §2.3 P4 |
| R8 | 能力与调研章节对照 | 总规划附录 A |
| — | 总 Catalog 多维表格；删除各层旧 JSON 附件节 | 总规划索引；各层 |

计数：能力组 139 → 141，原子 434 → 458，硬能力组 30 → 31，FDE 能力组 45 → 43。

## 未完成

- P1–P7 只有建议，待定案。
- 约 100 个输出类型仍无字段；进入切片前补齐。
- DA08.5、DA12.3、DA14.7、DA18.2 未拆分。
- 层内审批策略等表述未逐条改写，以总规划 §4.2 为准。
- 内核依据 `agent-kernel@f0fa521`；`packages/iface-*` 相对 `kernel/iface/src` 的漂移未处理。
