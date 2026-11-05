# AgentCPM OS 官方资料摘要

这里保存飞书官方项目资料的本地摘要与原文抄录，供项目对齐与后续开发查阅。

## 阅读入口

| 文档 | 内容 | 官方来源 |
| --- | --- | --- |
| [应用组件整体规划（原文抄录）](./agent-os-application-components.md) | 20 个通用技术方向、120 个二级能力、24 个业务方向、144 个二级任务与 10 条完整链路 | [AgentCPM候选业务组件列表](https://modelbest.feishu.cn/wiki/CJkhwwhBRinSwSk26NTc4mZKns4) |
| [项目核心信息](./agentcpm-os-project.md) | 产品定位、系统组成、团队、版本目标、进度、里程碑、评估与资料入口 | [AgentCPM OS项目](https://modelbest.feishu.cn/wiki/Tx9dwLf6giRWwGkk8LDcXwZbnGc) |
| [Kernel 架构核心信息](./kernel-architecture-v0.1.md) | Rust Core、三档构建、插件、宿主 API、ReAct 扩展、code mode、前端协议、硬件与性能 | [Rust Agent 框架架构设计 V0.1](https://modelbest.feishu.cn/wiki/JV7TwNyQqiY8J5kTwx2cB1Fonce) |

## 来源与范围

整理日期：2026-10-26，时区：Asia/Shanghai。内容通过 `lark-cli` 以用户身份只读获取。

| 来源 | 版本或读取范围 |
| --- | --- |
| AgentCPM候选业务组件列表 | 2026-10-31 读取；document revision 147；正文、历史说明与 5 张内嵌表格（spreadsheet revision 98） |
| AgentCPM OS项目 | document revision 517；正文与项目内核架构画板 |
| 项目进度看板 | table `tbl999i1VBdpWdY6`，rev 33；17 条记录，`has_more=false` |
| 项目版本目标 | table `tblyUUphpUxcOFgm`，rev 49；18 条记录，`has_more=false` |
| Rust Agent 框架架构设计 V0.1 | document revision 20；正文、分层架构与硬件覆盖两张画板 |

《应用组件整体规划》是 2026-10-31 的原文抄录快照，其余两份为 2026-10-26 的摘要快照，均不代表当前目录已有相应实现。架构能力按设计描述记录，状态按读取时的表格记录，性能数据保留原文测试条件与估算标识。三张画板均已读取原始节点文字，整理为分层说明和兼容性表格。

相关文档、仓库与子页面保留为索引，未递归读取其内容；其中《【RFC】Kernel》也仅作为后续参考入口。源文档的排期及技术口径差异，分别记录在两份摘要的“待确认事项”中。
