---
title: AgentCPM OS 项目核心信息
source: https://modelbest.feishu.cn/wiki/Tx9dwLf6giRWwGkk8LDcXwZbnGc
source_revision: 517
retrieved_on: 2026-10-26
category: official
tags: [AgentCPM, AgentOS, Kernel, roadmap]
---

# AgentCPM OS 项目核心信息

## 一句话总结

AgentCPM OS 面向终端用户提供端侧优先、覆盖低算力设备到服务器的智能体运行系统，将模型、工具、记忆、安全等共性能力沉淀为开源 Kernel，通过应用包与包管理器实现智能体应用即装即用，并自带可交互、可安装扩展的最小智能体。

## 核心要点

- 目标体验：设备安装系统后，像安装手机 App 一样，一句话安装和使用智能体应用。
- Kernel 面向开发者，Kernel 之上的 AgentCPM OS 面向终端用户；行业产品需求持续沉淀为系统能力。
- 系统由开源 Kernel、应用包、包管理器构成，模型、硬件与存储后端可通过插件扩展。
- 首批应用包括 PilotDeck、StaffDeck、CPM-Harness，以及为系统提供本地模型能力的端侧部署包。
- 先交付最小内核、Terminal 和装包闭环，再补资源管理、调度、跨设备、恢复、记忆与桌面交互。

## 1. 定位与目标体验

当前智能体应用通常各自携带模型调用、工具执行、记忆、安全控制等完整底座。多个应用并行运行会重复消耗资源，能力难以共享或复用。

AgentCPM OS 将共性能力统一放入系统，应用可直接使用，也允许自行构建相应能力。目标包括：

- **即装即用**：通过一句话安装智能体应用，生态开发者也可发布应用包。
- **端侧优先**：以 “Run AnyWhere AnyTime” 为目标，覆盖 IoT、手机、PC 和服务器，按设备能力裁剪或增强。
- **插件扩展**：模型接入、硬件设备、存储后端像驱动一样接入系统。
- **最小可用智能体**：自带资源消耗最小的 agent loop，安装系统后即可使用，并可自主安装扩展自身。

产品关系：AgentCPM Kernel 是 AgentCPM 产品体系的底座；AgentCPM OS 是基于这些基础能力、具备完备体验的标准化产品。行业产品的共性需求进入 Kernel，Kernel 再支撑更多产品。

## 2. 系统组成与边界

| 组成 | 面向对象 | 职责与边界 |
| --- | --- | --- |
| Kernel，开源 | 开发者 | 模型调用、工具执行与安全控制、会话与记忆、事件与调度；强调精简、可靠、设备覆盖 |
| Rust Agent 框架 | Kernel 开发者 | Kernel 的重要组成；V0.1 架构设计已完成，提出单一可执行文件、三档构建、插件热拔插与统一宿主 API |
| 应用包 | 应用开发者与用户 | 使用系统基础能力或自建能力；生态允许开源包与商用包 |
| 包管理器 | 开发者 | 安装、更新、卸载、依赖与版本管理，类比 pip / apt |

Rust 框架细节见 [Kernel 架构核心信息](./kernel-architecture-v0.1.md)。这里的“设计完成”不等同于功能已经实现或验收。

### 首批应用包

| 应用包 | 定位 / 能力 |
| --- | --- |
| PilotDeck | 任务型智能体工作台 |
| StaffDeck | 企业数字员工平台 |
| CPM-Harness | 全双工语音智能体 |
| 端侧部署包 | 本地模型一键运行；模型下载与校验、进程管理、OpenAI 兼容接口；面向 macOS、Windows、鸿蒙 PC，基于 minicpm-for-pc 积累；安装后为系统提供本地模型能力 |

## 3. 团队与协作

| 职责 | 成员 |
| --- | --- |
| 技术负责人 | 卢雅西 |
| 产品经理 | 王炤 |
| 内核架构 | 李鹏越、李奕杉、郑达奇 |
| 应用包开发 | 李奕杉、黑子健、魏耀全、伍培文、冯佳玉、方奔皓、吴佳翮 |
| 解决方案 / 业务开发 | 上官圣垚、骆元昊、丁来平 |
| 系统评估 | 刘曜、骆元昊、龚建 |

例会：每日 10:00 线下站会；每周五 17:00 线下周会。

## 4. 里程碑

| 里程碑 | 正文目标时间 | 交付范围 |
| --- | --- | --- |
| M1：OS v2026.10 ready | 2026 年 10 月底 | 最小运行内核：会话与循环、事件、外部调用管控、模型调用、扩展；AgentOS Terminal；一句话安装端侧部署包；标配样本最小 MVP |
| M2：OS v2026.11 ready | 2026 年 11 月底 | 调度、资源池、模型路由、分布式、恢复、存储；三档构建交付；桌面 App、记忆包、后台长任务 |

正文周计划、版本目标表和里程碑时间存在差异，详见第 9 节。以下日期与状态均保留对应来源的原始口径。

## 5. 版本目标表快照

读取日期：2026-10-26。来源为内嵌表 `tblyUUphpUxcOFgm`，rev 49，共 18 项，已完整读取。优先级 P0 / P1 / P2 分别对应关键 / 重要 / 一般。

### OS v2026.10：8 项

| 目标 | 核心要求 / 备注 | 负责小组 | 优先级 | 开始至结束 | 状态 |
| --- | --- | --- | --- | --- | --- |
| 会话与循环 | 会话创建、步进执行、挂起与恢复 | 内核架构 | P0 | 10/19 至 11/01 | 进行中 |
| 事件 | 事件记录、存储、访问；观测、审计、恢复基于同一事件流 | 内核架构 | P0 | 10/19 至 11/01 | 进行中 |
| 外部调用管控 | 统一拦截，执行权限检查、审批与审计 | 内核架构 | P0 | 10/19 至 11/01 | 进行中 |
| 模型调用 | 端点抽象与本地 / 远端调用 | 内核架构 | P0 | 10/19 至 11/01 | 进行中 |
| 扩展 | 能力注册与注销、作用域生命周期、热拔插；能力视图每步重建 | 内核架构 | P0 | 10/19 至 11/01 | 进行中 |
| AgentOS Terminal | 自然语言终端，支持对话、执行任务和装包 | 内核架构 | P0 | 10/26 至 11/01 | 未开始 |
| 一句话安装 | 装上端侧部署包后，本地模型就绪 | 应用包开发 | P0 | 10/26 至 11/01 | 未开始 |
| 标配样本智能体 | Terminal 内交互的最小 MVP | 应用包开发 | P0 | 10/26 至 11/01 | 未开始 |

### OS v2026.11：10 项

| 目标 | 核心要求 / 备注 | 负责小组 | 优先级 | 开始至结束 | 状态 |
| --- | --- | --- | --- | --- | --- |
| 资源池 | 模型运行时 / 内存共享与配额 | 内核架构 | P1 | 11/02 至 11/08 | 未开始 |
| 存储 | kv / blob，作为记忆包等能力包的基础 | 内核架构 | P1 | 11/02 至 11/15 | 未开始 |
| 调度 | 算力与资源优先级仲裁；默认按焦点动态分配 | 内核架构 | P1 | 11/09 至 11/15 | 未开始 |
| 模型路由 | 多端点选择；默认本地优先、受控云端顾问 | 内核架构 | P1 | 11/09 至 11/15 | 未开始 |
| 焦点调度演示 | 前台焦点 agent 与后台 agent 的算力优先级动态倾斜 | 内核架构 | P1 | 11/09 至 11/15 | 未开始 |
| 记忆包 | 基于存储机制的跨会话记忆，装上即生效 | 应用包开发 | P1 | 11/09 至 11/15 | 未开始 |
| 分布式 | 设备发现、会话跨设备迁移 | 内核架构 | P2 | 11/16 至 11/22 | 未开始 |
| 恢复 | 事件重放、投影重建、副作用账本 | 内核架构 | P2 | 11/16 至 11/22 | 未开始 |
| 桌面 App | 标配样本智能体的完整交互形态；app-server / JSON-RPC 前端协议 | 应用包开发 | P2 | 11/16 至 11/22 | 未开始 |
| 后台长任务 | 挂起、到点提醒 | 内核架构 | P2 | 11/23 至 11/29 | 未开始 |

版本目标表合计：5 项进行中，13 项未开始，0 项已完成。状态仅反映表格快照。

## 6. 周计划与进度看板

### 正文周计划

| 周次 | 正文日期，2026 年 | 计划 |
| --- | --- | --- |
| W1 | 10/26 至 11/01 | Kernel 基本代码框架；类 syscall 层接口文档；ABI 与迁移方案；组件包抽象；最小组件安装 / 卸载闭环 |
| W2 | 11/02 至 11/08 | OS v2026.10 收尾：最小机制集、Terminal、端侧部署包安装、样本 MVP |
| W3 | 11/09 至 11/15 | 资源池机制；三档构建 |
| W4 | 11/16 至 11/22 | 调度与焦点策略；模型路由；记忆包 |
| W5 | 11/23 至 11/29 | 分布式；恢复；桌面 App |
| W6 | 原文为“11.30 - 12”，结束日期未写完整 | 后台长任务；设备档位评估；集成与 OS v2026.11 发布 |

### W1 具体分工

| 事项 | 负责人 / 要求 |
| --- | --- |
| ABI 文档与 PilotDeck / StaffDeck 迁移方案 | 李鹏越、卢雅西、周界 |
| Rust 重构与 ABI 对齐 | 郑达奇 |
| 包管理器 + Hub 抽象文档 | 李鹏越 |
| PilotDeck 模块化组件包 | 李奕杉 |
| StaffDeck 模块化组件包 | 彭淳毅 |
| CPM-Harness 模块化组件包 | 魏耀全 |
| W1 闭环 | MVP Kernel + 包管理器，在 Rust PilotDeck / TypeScript PilotDeck 跑通最小组件安装与卸载 |

### 内嵌进度看板快照

来源为表 `tbl999i1VBdpWdY6`，rev 33，共 17 项，已完整读取。为保留状态差异，按周合并展示所有任务。

| 周次 | 看板日期，2026 年 | 任务与负责小组 | 优先级 | 状态 |
| --- | --- | --- | --- | --- |
| W1 | 10/19 至 10/25 | Kernel 基本代码框架、类 syscall 层接口文档，均由内核架构负责 | 2 项 P0 | 2 项进行中 |
| W2 | 10/26 至 11/01 | 最小机制集、Terminal：内核架构；端侧部署包一句话安装、样本 MVP：应用包开发 | 4 项 P0 | 4 项未开始 |
| W3 | 11/02 至 11/08 | 资源池机制、三档构建：内核架构 | 2 项 P1 | 2 项未开始 |
| W4 | 11/09 至 11/15 | 调度与焦点策略、模型路由：内核架构；记忆包：应用包开发 | 3 项 P1 | 3 项未开始 |
| W5 | 11/16 至 11/22 | 分布式、恢复：内核架构；桌面 App：应用包开发 | 3 项 P2 | 3 项未开始 |
| W6 | 11/23 至 11/29 | 后台长任务：内核架构；设备档位评估：系统评估；集成与发布：全组 | 3 项 P2 | 3 项未开始 |

看板合计：2 项进行中，15 项未开始，0 项已完成。补充备注：装包任务依赖包管理器安装链路；模型路由默认本地优先、受控云端顾问；记忆包基于 kv / blob；恢复包含事件重放与副作用账本；桌面 App 使用 app-server / JSON-RPC；设备评估对齐 EdgeBench。

## 7. 评估与硬件

| 对标产品 | 角色 | 目标 |
| --- | --- | --- |
| WorkBuddy | 商业对标，企业 agent 平台 | 产品体验最终达到同等水平 |
| DeepSeek Harness | 体验对标 | 对话、工具调用、后台任务、权限审批的核心体验 |

系统评估组负责指标体系，与 EdgeBench 对齐：

- **资源占用**：启动内存、二进制体积、档位裁剪。
- **延迟**：模型调用链路、一句话安装链路。
- **设备档位**：同一系统在不同算力设备上的表现。

| 档位 | 项目目标硬件 |
| --- | --- |
| FULL | PC、服务器、DGX Spark、AIPC |
| LITE | 树莓派、工控机、华为 300 盒子 |
| CORE | AI 眼镜、MaixCam2 等资源受限端侧设备；MaixCam2 示例为爱芯元智 AX630C、双核 A53、NPU 3.2 TOPS@INT8、1GB / 4GB LPDDR4 |

## 8. 相关资料与仓库

下列内容是源文档提供的入口，未在本轮逐篇展开或检查仓库实现。

### 官方文档

| 类别 | 入口 |
| --- | --- |
| 产品定位 | [AgentCPM OS 产品定位与目标场景](https://modelbest.feishu.cn/docx/PzoHdahQBop1l3xFmiKcthJGnSc) |
| 品牌与产品体系 | [AgentCPM 品牌边界与产品体系 v2（内部讨论稿）](https://modelbest.feishu.cn/wiki/N92Bw915KiDCCPkLPHqcRDRynsy) |
| Q4 设计 | [2026 Q4 AgentOS 设计文档 v0.1](https://modelbest.feishu.cn/wiki/CEAywLGSqiwdVtkSufTclNc2nLf) |
| 沟通记录 | [AgentCPM 任务沟通会 2026-10-16](https://modelbest.feishu.cn/docx/MMgudV4K8o0QhoxzI3tctVaDnbK) |
| Rust 框架设计 | [Rust Agent 框架架构设计 V0.1](https://modelbest.feishu.cn/wiki/JV7TwNyQqiY8J5kTwx2cB1Fonce)；[本地摘要](./kernel-architecture-v0.1.md) |
| Kernel RFC | [【RFC】Kernel](https://modelbest.feishu.cn/wiki/FJ3BwWjR5iNrctkk6Eycnqj2noB) |
| PilotDeck 架构 | [PilotDeck 解耦版产品架构图](https://modelbest.feishu.cn/docx/Ora2dyl6TocFLtxZPvzcBXu7nRe) |
| 功能清单 | [产品功能清单（346 项）](https://modelbest.feishu.cn/base/TVoBbVHwkaNtWpsd8HxctTe6nMf?table=tbl20bWQVVljqPjA&view=vew1se5eW3) |
| 模块接入 | [PilotDeck / StaffDeck 通用模块架构、通信与接入指南](https://modelbest.feishu.cn/docx/Wq8Ydr3IJoPcUIxyXFpczvjxn8V) |
| 项目子页面 | [【评审】端侧智能体系统研发](https://modelbest.feishu.cn/docx/FXCGdOayDo4n0jxqbx0cpC8PnMc)、[端侧智能体自进化](https://modelbest.feishu.cn/docx/M6vAda6a5on9WaxFWxPcK1RhnGc)、[组件包开发汇总](https://modelbest.feishu.cn/base/OsJ3bbVi3aZSwbsPaswcpF26nhd) |

### 仓库

| 仓库 | 地址 |
| --- | --- |
| AgentKernel | [华为云 CodeHub，master](https://devcloud.cn-north-4.huaweicloud.com/codehub/project/5a5fe37f080d4dcdab39d8b3ea837bb1/codehub/3102476/home?ref=master) |
| CPM-Harness | `git@codehub.devcloud.cn-north-4.huaweicloud.com:5a5fe37f080d4dcdab39d8b3ea837bb1/CPM-Harness.git` |
| AgentCPM 模块化版本 | `git@codehub.devcloud.cn-north-4.huaweicloud.com:96dc8a30a5644cc6a8d2bb2f199016a7/as/AgentCPM.git`；[内部页面](https://devcloud.cn-north-4.huaweicloud.com/codehub/project/96dc8a30a5644cc6a8d2bb2f199016a7/codehub/3098669/home?ref=main) |
| minicpm-for-pc | `git@codehub.devcloud.cn-north-4.huaweicloud.com:f70296edad404aa3ac9f5d19edfc9121/inference/minicpm-for-pc.git` |
| EdgeBench | `git@codehub.devcloud.cn-north-4.huaweicloud.com:96dc8a30a5644cc6a8d2bb2f199016a7/as/EdgeBench.git` |

AgentCPM 分支口径：`main` 为 TypeScript 版本；`rust-core` 为 Rust 重构核心 sidecar 与公共代码；`rust-core-base-pd` 为 Rust 与 TypeScript 拼装版本；`rust-core-full` 为 Rust 重构中的分支。源文档称后者仅部分后端接口已实现、进度不及预期，并将原因归于所用模型表现；这属于源文档作者的状态说明与判断，未通过仓库验证。

## 9. 待确认事项

| 问题 | 来源差异 / 缺口 |
| --- | --- |
| 周计划与看板相差一周 | 正文 W1 为 10/26 至 11/01，看板 W1 为 10/19 至 10/25；W2 至 W6 同样存在一周偏移 |
| M1 时间不一致 | 里程碑为 10 月底；版本目标表结束于 11/01；正文 W2 将 v2026.10 收尾安排在 11/02 至 11/08 |
| M2 时间不一致 | 里程碑为 11 月底；看板发布结束于 11/29；正文 W6 从 11/30 开始，结束日期仅写“12” |
| 人员名单口径 | 正文应用包开发名单未列彭淳毅，但 W1 分工将 StaffDeck 组件包指定给彭淳毅；ABI 分工还出现周界 |
| 设计与实现进度需分别核验 | Rust 框架 V0.1 是设计资料；表格状态不能证明具体代码、API 或设备适配已完成 |

本摘要保留差异，不自行选择其中一套排期作为最终承诺。
