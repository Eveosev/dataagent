# F. 中国市场：智能问数 / Data Agent / BI+大模型竞品与需求特征

> 2026-10-30。**方法说明**：web_search 不可用（无 API key），改用 curl 直取厂商官网 + BIRD 官方榜单。凡页面为 JS 渲染、正文未取到的，标 **未核实**；不引用无法回溯的融资额、客户名单与报价。

## 1. 执行摘要

1. **NL2SQL 已不是护城河。** BIRD 榜（2026-10）上中国团队把 Test 执行准确率推到 82% 区间：华为 2012 Labs DataGallery-Text2SQL 78.10/82.39、腾讯 SiriusAI-SQL 77.77/82.28、京东 JoyDataAgent-SQL 76.19（仅 4B）、蚂蚁 Agentar-Scale-SQL 74.90、小米 73.66/80.83；"人类 DB 工程师"基准是 92.96/72.37。**基准上机器已越过人类平均线**，竞争重心迁移到语义层、口径治理与交付。
2. **头部玩家集体转向"语义层 + Agent"。** FineBI 7.0 把架构从"数据表分析"重构为"指标语义层"（官网原话：以指标为基座）；SmartBI 白泽 V5、Kyligence Zen、观远指标中心、Quick BI 的 AI-ready 语义层路径一致。**指标平台是入场券，不是差异点。**
3. **云厂商的壁垒是资质与渠道，不是模型。** Quick BI 首批通过信通院「大模型驱动的智能数据分析工具」+「BI 分析工具基础能力」双评测，连续 7 年入选 Gartner ABI 魔力象限（厂商自述，2026-07）。
4. **"文件即席分析"普遍只是数据源入口。** 多数产品把 Excel/CSV 当"又一个 connector"，少有把文件里的临时口径**沉淀回受治理指标层**——这是最实在的产品空档。
5. **中国客户的采购单位是"项目"，不是"席位"。** 私有化/信创/数据不出域是硬门槛，POC 由集成商带，决策看"能不能过等保、能不能跑达梦/金仓"。

## 2. 竞品表

| 厂商 | 产品 | 形态 | 差异点 | 客户/价格 |
|---|---|---|---|---|
| 阿里云 | Quick BI + 智能小Q | SaaS/混合云本地部署 | 4 Agent（搭建/问数/报告/洞察）；70+ 数据源；**即席分析仅专业版**；QBI Skill(2026-04)、CLI(2026-03)、MCP；问数 Agent 2026-07 支持多轮多步+语音 | 个人/高级/专业三档订阅，**价格页未取到，未核实** |
| 阿里云 | DataWorks Data Agent | 订阅+按量 | 2026-05 升级：语义图谱、专家套件、自主巡检；送 Token 额度 | Serverless 资源组 109 元促销包（官网） |
| 阿里系/蚂蚁 | 瓴羊 Dataphin、蚂蚁 Agentar | 中台/平台 | 偏"建指标"与金融风控；Agentar BIRD 74.90(2025-09) | **未核实** |
| 腾讯云 | 腾讯云 BI / ChatBI | SaaS | 接混元、DeepSeek；**Excel/CSV/腾讯文档直连**；企微登录、移动端 | 促销 9.9 元/年（锚点意义＞真实 ARPU） |
| 腾讯音乐 | SuperSonic（开源） | 开源自部署 | 把 Chat BI 与 Headless BI（语义层）统一 | Apache-2.0 |
| 华为云 | DataArts / GaussDB | 私有化/云 | 治理与湖仓强，配盘古 | **产品页未取到正文，未核实** |
| 百度 | Sugar BI | SaaS/私有化 | 官网已改称"你的大模型商业分析助手" | **未核实** |
| 火山引擎 | DataWind / ByteHouse | 云 | 行为数据与 OLAP 底座 | **未核实**（JS 渲染） |
| 京东 | JoyDataAgent-SQL | 待证 | BIRD 76.19，仅 4B，性价比路线；"JoyBI"**未核实** | 未公开 |
| 帆软 | FineBI 7.0 / FineBI Next | 私有化为主 | **指标语义层重构**；Next＝分析 Agent（已上线）+ 场景 Agent（9 月·共创中）；自称 43000+ 客户、IDC 中国 BI 2017–24 第一（厂商口径） | License + 年维保 |
| 观远数据 | 观远BI/问数Agent/洞察Agent/DecideX | 私有化+SaaS | 消费零售纵深最深；**信创生态单列**；指标中心 | 项目制+订阅 |
| 思迈特 | SmartBI 白泽 V5 | 私有化 | 多智能体+ReAct+Skills；**统一指标模型 + 知识库 RAG**；**识别 Excel 模板自动取数填报** | 项目制，有信创版 |
| 永洪 | Megrez 天权/Friday/Polaris | 私有化+免费桌面 | 全家桶最全；**Desktop 桌面版 FREE** 抢 Excel 用户 | 免费引流+项目制 |
| Kyligence | DeepInsight / Zen | 私有化+云 | 自主深度推理洞察；Zen 做统一语义层；**Excel Copilot、WPS 多维分析** | 平安银行、泰康、欣和、Costa、斯凯奇、长安汽车、阿斯利康（官网） |
| 数势科技 | SwiftAgent | — | 曾为对标重点 | **官网 swiftagent.cn 已停放，全部细节未核实** |
| 百分点/亿信华辰 | 百思治理大模型等 | 私有化 | 已转数据治理+政务，问数非主线 | 政府/央国企项目制 |
| 明略/第四范式/澜舟/竹间 | DeepMiner、先知AIOS 5.0、对话式BI | 平台/方案 | 均非"企业库问数"主线；竹间**官网不可解析** | 未核实 |
| OceanBase | **DataPilot** + Agentbase | 数据库厂商向上 | 库内生 Agent，天然"数据不出库"；首批过安全可靠测评 | 随库/订阅 |
| SelectDB | SelectDB | OLAP | **"面向 Agent 的分析库"**：内置 AI 语义层消歧、原生 MCP | 10000+ 企业（官网口径） |
| StarRocks / PingCAP | StarRocks / TiDB | OLAP/DB | StarRocks 明打"为 Agent 服务、容忍未优化 SQL"；**TiDB Chat2Query 页已 404**，叙事转向 Agentic AI 记忆 | 开源+商业版 |
| 达梦 | — | 国产库 | BIRD 上 Blender-SQL+Qwen3.8-27B 74.51（2026-10），**国产方言 NL2SQL 已自证** | — |

**"ontology/指标平台"三种做法**：①**指标中台型**（Kyligence Zen、观远指标中心、百分点）——重但口径最稳，适合金融/央国企；②**语义层内嵌型**（FineBI 7.0、Quick BI、SuperSonic、SelectDB）——随问数交付，落地快、治理弱；③**知识库 RAG 型**（SmartBI 企业知识库、Quick BI "记忆知识"）——最像 ontology，但**可验证性最差，是可攻击点**。

## 3. 中美需求差异（5 条）

1. **数据源结构不同。** 欧美基于已建模数仓（dbt/Snowflake），语义清晰；中国是"ERP + 手工 Excel + 孤岛库"，没有 dbt 层。同一句"上月毛利率"，美国直接映射 dbt metric，中国要先拉齐口径。→ 产品必须**先吃文件、再吃库**。
2. **部署是硬约束而非偏好。** 欧美默认 SaaS 按席位；中国中大型客户默认私有化/专有云，**数据不出域写进合同**，信创点名 CPU（鲲鹏/海光）、OS（麒麟/统信）、库（达梦/金仓/OceanBase）、模型不得出境。→ 必须"可离线、可换模型、可换库"。
3. **口径治理是政治问题。** 中国痛点是"两位高管汇报出相差 1 亿的销售额"（帆软官网案例），买的是**"谁的数为准"的裁决机制**：指标 owner、版本、审批。欧美更多是 catalog/lineage 工程问题。
4. **交互习惯是"对话+报表+微信"。** 欧美走 Slack/Teams 嵌入；中国必须**企微/钉钉/飞书登录、移动端看板、日报周报推送**，最终交付常是**一张能贴进 PPT 的图**。
5. **评测与合规是门票。** 信通院评测、等保、ISO 27001/27018 是标书资格项（Quick BI 把"首批通过"当卖点）；欧美对应 SOC2 / EU AI Act。

## 4. 生态合作与渠道建议

1. **数据库/OLAP 厂商（最高优先）。** OceanBase DataPilot、SelectDB、StarRocks、达梦、GaussDB 都在抢"Agent 入口"，却不擅长分析体验与指标治理；它们要的是**证明"我的库跑问数更快更准"**——适合做联合 benchmark 与"方言适配包"。达梦在 BIRD 自证方言可行，说明厂商动机很强。
2. **BI 厂商做语义层互补而非替代。** Kyligence（Zen + Excel Copilot）、SmartBI（Excel 模板填报）有文件侧能力但缺"文件→受治理指标"闭环。以 **MCP/Skill 接入**（Quick BI 已开 QBI Skill/CLI，说明云厂商愿被集成）比正面替换现实。
3. **信创集成商/区域 SI（现金流）。** 最后一公里在 SI：带 POC、垫资、做等保。要提供**"SI 可交付包"**：离线镜像、国产库适配清单、标书素材。
4. **开源社区。** SuperSonic、DB-GPT、Chat2DB 是国内 NL2SQL 开发者入口，适配器/插件是低成本获客。

**定价锚点**：云 SaaS 订阅已被打到地板（腾讯云 BI 促销 9.9 元/年；Quick BI 三档；DataWorks 订阅+按量、109 元资源包、送 Token）；私有化仍是"License+首年实施+年维保"（具体金额**未核实**）；永洪 Desktop/云 FREE 做免费端引流。**结论：不要按席位定价**——客户会拿 9.9 元/年做锚。可行锚点是**"按数据域/Agent 数量 + 实施人天"**，并把 tokens 成本转嫁为 BYO model。

## 5. MintHub DataAgent 的 3 个 wedge

**Wedge 1｜"文件即席分析 → 一键升格为受治理指标"（最锋利）**
现状：所有厂商把 Excel 当数据源，**没人把文件里临时算出的口径沉淀成带 owner、版本、审批的指标**。SmartBI 只做到"模板→数据"（反向），Quick BI 即席分析仅专业版且与指标层割裂。
打法：业务拖一个 Excel 问数 → Agent 识别计算逻辑 → 提示"此口径与库内『毛利率』差 2.3pp，登记为新指标还是申请修订？" → 走审批。**同时命中"口径治理"与"Excel 文化"**，且欧美产品无强审批文化、不会优先做。

**Wedge 2｜"国产库方言 + 离线可换模型"交付包（最易签单）**
① 达梦/金仓/OceanBase/GaussDB/StarRocks 方言适配与查询改写（BIRD 证明可行但产品化不足）；② 全离线镜像 + 国产 CPU/OS 兼容清单；③ 信通院评测/等保材料模板。**把合规做成 SKU，不是做成文档。**
风险：Quick BI 已握评测资质，正面拼资质无胜算，应定位"帮你在私有化环境达到同等可信度"。

**Wedge 3｜"口径争议仲裁者"——CFO/经营分析会场景**
不做全员自助 BI（渠道打不过帆软/观远），做**一个高价值会议场景**：两个部门报出不同的数，Agent 当场归因（口径/时间窗/含税/渠道归属）并留痕。价值可被当场感知，且帆软正用这个故事教育市场——需求真实，但他们用"事前建指标"解决，MintHub 可用"事后解释+反哺指标"差异化。

**不建议做**：通用 ChatBI 前端（红海、被云厂商免费化）、NL2SQL 准确率军备竞赛（BIRD 已 82%，边际递减）、纯 SaaS 订阅（大客户不买）。

## 附：证据与链接

Quick BI https://www.aliyun.com/product/quick-bi ｜定价 https://www.aliyun.com/product/quick-bi/pricing ｜DataWorks https://www.aliyun.com/product/dataworks ｜FineBI https://www.finebi.com/ ｜FineBI Next https://www.fanruan.com/finebinext ｜观远 https://www.guandata.com/ ｜SmartBI https://www.smartbi.com.cn/ ｜永洪 https://www.yonghongtech.com/ ｜Kyligence https://cn.kyligence.io/ ｜腾讯云 BI https://cloud.tencent.com/product/bi ｜SuperSonic https://github.com/tencentmusic/supersonic ｜OceanBase https://www.oceanbase.com/ ｜SelectDB https://www.selectdb.com/ ｜StarRocks https://www.starrocks.io/ ｜PingCAP https://www.pingcap.com/ ｜Sugar BI https://cloud.baidu.com/product/sugar.html ｜百分点 http://www.percent.cn/ ｜明略 https://www.mininglamp.com/ ｜澜舟 https://www.langboat.com/ ｜第四范式 https://www.4paradigm.com/ ｜**BIRD 榜单** https://bird-bench.github.io/ ｜信通院 http://www.caict.ac.cn/（「大模型驱动的智能数据分析工具」评测存在性由 Quick BI"首批通过"佐证，**细则未核实**）

**未核实清单**：瓴羊、DataWind、DataArts、Agentar、JoyBI、数势、竹间、亿信华辰的具体能力与客户；所有厂商融资额；所有私有化报价。
