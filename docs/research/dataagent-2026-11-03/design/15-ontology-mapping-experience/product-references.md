---
version: 1
date: 2026-11-10
method: 官方公开文档阅读；未登录或测试产品部署
---

# 映射交互参考记录

| 页面 | 核对内容 | 对方案的影响 |
| --- | --- | --- |
| [Palantir Ontology Manager](https://www.palantir.com/docs/foundry/ontology-manager/overview) | 对象概览、属性编辑、链接类型等入口分离 | 对象、字段、关系采用分层视图 |
| [Palantir 创建对象类型](https://www.palantir.com/docs/foundry/object-link-types/create-object-type) | 来源列映射属性、目标属性选择来源列、对象标识 | 主表按目标字段排列，支持从来源反查，身份策略显式检查 |
| [Palantir 编辑对象类型](https://www.palantir.com/docs/foundry/object-link-types/edit-object-type) | 更换 backing datasource 时，schema 一致才自动重映射 | 结构漂移展示差异和重验需求 |
| [Fabric 数据绑定](https://learn.microsoft.com/en-us/fabric/iq/ontology/how-to-bind-data) | 选择来源、绑定已有属性、次级来源关联列 | 来源、属性与关系绑定分别可核对 |
| [Fabric Ontology Agent](https://learn.microsoft.com/en-us/fabric/iq/ontology/how-to-use-ontology-agent) | 自然语言发现、草拟、验证和应用；预览候选内容 | Agent 准备草案，用户通过业务语言和界面共同修改 |

记录只采纳可核对的交互模式；没有据文档推定这些产品支持本项目的文档、API、GUI 多源自动接入、实例断言或 Mint 集成。界面草图为独立创作，未复制产品截图。
