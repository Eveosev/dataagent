---
doc_id: ask
title: 附B 原始诉求
answers: 提需求时的原话
status: 已有
feishu_node: TsWkwjM5HiESY9k5oeocbqmrnff
feishu_obj: THaBd1ahRowfMex56mBcKU9Anwh
---
# 附B 原始诉求

> 这里保存提需求时的原话，不改写。后来补充的内容另起一节，注明日期。

1、阅读AgentOS这个project中的所有session，目前我这边负责的是DataAgent（及广义DataAgent）、令才中的自进化（ql-audit），自进化toolkit的实现（帮我总结当前的实现，后续会交接到其他人手上）

这些项目，基于当前的框架，如何放进来；其次，我们需要依托的agent-kernal(iface， mint)等，帮我加在这个项目的架构中

## 2026-11-16 补充

目标：在AgentCPM/Mint框架下，完成DataAgent的多源数据接入和ontology的接入

梳理一下：需要哪些核心包（iface）的支持，以及还需要哪些功能；哪些需要放在业务侧坐，哪些需要核心包加机制

（追问时补充）你需要结合，已经实现的代码，回答这个问题

当前的实现，需要都考虑按iface包重构，给一个方案；

查看之前的全局设计：https://modelbest.feishu.cn/docx/TlN4dygs9oJR3Qx1FaictiPEn3c

目前，我还需要一个整体的设计和完整的PRD，保持第一阶段的验收目标是多源数据的接入, P2是ontology的实现、打通和可视化；其他阶段帮我丰富一下

使用子agent，结合palantir的ontology设计，以及Genie 的设计是：用 Ontology 管理业务含义，用 Pages 明确权威定义，用 Skills 固化工作方法；底层依靠 Unity Catalog 管理数据和权限。

上面的场景都是典型的NL2SQL场景，跟我们的目标具有借鉴意义

1、多源接入是当前的刚需；
2、iface的协议，是整个AgentCPM / AgentOS的底层，我们需要承担完善它的职责；通过业务应用在此协议上的建设，发觉需要iface扩充的地方，并且可以提PR去完善它；属于业务的建设，则我们可以自己承担
3、如果锚定了令才报销审核，写出来的方案，很可能过拟合到令才上；如何避免

1、采购对账，我不需要，因为我有一个，食品安全审核要校对的场景，但是这个场景没有真值，难以验证true / false；
2、lingcai其实也难以验证真假，只不过可以通过ql表达式，把一部分剔除；
3、NL2SQL或者金融分析的benchmark倒是可以找到类似的；
4、lingcai有一个完整的报销行为，是我之前让Codex通过Computer use去采集的多个数据；进而发起真实的报文审核；这个其实是一个完整的验收场景；你判断一下是否可用；
5、通用的可以考虑，并且可以丰富多个维度；

真实的业务场景，数据其实我们获取不到；后续我来跟进

上面的验收办法完善成 03 的 P1 和 09-benchmark 计划

按照标准的PRD，设计方案，和任务清单，帮我维护在飞书的项目里；后续我需要你调用本地的crew（启动dsh, zcode，codex 的cli）来按照清单完成任务；调用方式稍后我提供，你可以参考「超大型项目开发经验」这个会话

## 2026-11-25 补充：现状整理与项目选路

> 目前的dataagent项目，感觉在实现的过程中越走越远；先帮我把目前的东西都归纳整理，并同步飞书；你来思考一下，是我们新建一个子项目fde harness（里面要包含dataagent，并且可以适当的复用之前的能力），还是沿着原来的代码实现
