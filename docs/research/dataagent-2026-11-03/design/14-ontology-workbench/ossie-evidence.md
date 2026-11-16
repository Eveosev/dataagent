---
version: 1
date: 2026-11-10
repository: https://github.com/apache/ossie
commit: d700cdeac41d15a7004eb2f9b0b38a2b1d517a18
upstream_spec: 0.3.0.dev0
method: 官方仓库浅克隆、静态阅读；未执行上游代码
---

# Apache Ossie 参考记录

## 读取范围

通过联网 `git ls-remote` 取得 HEAD，浅克隆后 `git rev-parse HEAD` 与其一致。网页 main、raw 与缓存内容可能来自不同修订，本记录以固定提交的源码为准。文件 SHA-256 见 [source-manifest.json](source-manifest.json)。

| 来源 | 核对内容 |
| --- | --- |
| [README](https://github.com/apache/ossie/blob/d700cdeac41d15a7004eb2f9b0b38a2b1d517a18/README.md) | 项目定位、规范目录、Python 模型及转换器独立仓库 |
| [Core specification](https://github.com/apache/ossie/blob/d700cdeac41d15a7004eb2f9b0b38a2b1d517a18/core-spec/spec.md) | 未发布草案、逻辑模型结构、表达式与 custom_extensions |
| [Core schema](https://github.com/apache/ossie/blob/d700cdeac41d15a7004eb2f9b0b38a2b1d517a18/core-spec/ossie-schema.json) | 逻辑模型字段、schema 引用及厂商扩展结构 |
| [Ontology specification](https://github.com/apache/ossie/blob/d700cdeac41d15a7004eb2f9b0b38a2b1d517a18/ontology/ontology.md) | EntityType/ValueType、关系与角色、身份、约束、派生、独立映射及工具支持边界 |
| [Ontology schema](https://github.com/apache/ossie/blob/d700cdeac41d15a7004eb2f9b0b38a2b1d517a18/ontology/ontology.json) | 概念、关系、角色、映射对象及 additionalProperties 限制 |
| [Mapping schema](https://github.com/apache/ossie/blob/d700cdeac41d15a7004eb2f9b0b38a2b1d517a18/ontology/mapping.json) | 本体引用、语义模型引用、concept_mappings 与 custom_extensions |
| [Python models](https://github.com/apache/ossie/blob/d700cdeac41d15a7004eb2f9b0b38a2b1d517a18/python/src/ossie/models.py) | 当前逻辑模型类、OssieDocument、扩展数据的字符串载体 |
| [Python exports](https://github.com/apache/ossie/blob/d700cdeac41d15a7004eb2f9b0b38a2b1d517a18/python/src/ossie/__init__.py) | 公开导出的模型范围 |
| [Python README](https://github.com/apache/ossie/blob/d700cdeac41d15a7004eb2f9b0b38a2b1d517a18/python/README.md) | Pydantic 模型、加载与序列化职责 |
| [Flights ontology](https://github.com/apache/ossie/blob/d700cdeac41d15a7004eb2f9b0b38a2b1d517a18/examples/flights.ontology.yaml)、[semantic model](https://github.com/apache/ossie/blob/d700cdeac41d15a7004eb2f9b0b38a2b1d517a18/examples/flights.semantic_model.yaml)、[mapping](https://github.com/apache/ossie/blob/d700cdeac41d15a7004eb2f9b0b38a2b1d517a18/examples/flights.mapping.yaml) | 三类文档如何组织及对象、关系的映射树示例 |

## 已确认事实

1. 本体规范区分实体类型和值类型，关系按有序角色表达，可包含多个角色。
2. identify_by、requires、derived_by 分别表达身份引用、约束和派生声明；这些声明的运行执行需要消费方实现。
3. 关系采用集合语义，关系链接不包含 null。来源观察的重复、缺失与不确定性需要在应用实例/断言层保留。
4. 独立 mapping 文档引用一个本体和一个逻辑语义模型。内嵌映射仍为兼容保留；规范明确独立格式的解析器与转换器支持将另行补充。
5. 当前 Python models 与 exports 覆盖逻辑模型、数据集、字段、指标等，不以此推定拥有完整本体实例、审核和流程运行时。
6. 本体 schema 的 root、概念与关系结构拒绝任意额外字段；mapping/core 的 custom_extensions 采用显式厂商扩展，Python 载体的 data 为字符串。
7. 当前规范有未发布草案标记；导入导出实现应固定提交及 schema 依赖，单独记录支持子集与损失。

## 应用边界

本体概念、关系、身份和映射用于 DataAgent 交换适配的参考。实例、来源断言、审核、纠正范围、数据发布及 GUI 流程为 DataAgent 自有协议，须分别实现和验收。源码阅读未验证转换器运行行为、目标工具兼容性或业务推理效果。
