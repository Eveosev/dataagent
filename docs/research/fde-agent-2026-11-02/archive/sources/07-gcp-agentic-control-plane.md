# Google Cloud Next '26: Delivering the Agentic Control Plane | TWIML - The Voice of Machine Learning & AI

Google Cloud Next '26: Delivering the Agentic Control Plane | TWIML - The Voice of Machine Learning & AI 

About Contact Newsletter 
Twiml icon youtube Twiml icon X/twitter Twiml icon linkedin Twiml icon Facebook Twiml icon instagram 

- Podcast 
- Publications 
- Library 
- Community 
- Blog 

- About 
- Contact 
- Newsletter 

- Podcast 
- Publications 
- Library 
- Community 
- Blog 

Twiml icon youtube 
Twiml icon linkedin 
Twiml icon X/twitter 
Twiml icon Facebook 
Twiml icon instagram 

# Google Cloud Next '26: Delivering the Agentic Control Plane April 28, 2026 

I’ve been covering Google Cloud Next for several years now and, recently at least, each spring brings a new chapter in an ongoing story: how do you build an enterprise-grade agent platform when the definition of each of those words keeps changing underneath you? 
Each of the past two years brought a major architectural pivot. In 2024 it was the introduction of agents as a new type of enterprise software and Vertex AI Agent Builder as the platform for building them. In 2025 it was a code-first rebuild of the platform around the Agent Development Kit, Agent Engine, and Agent Garden. As I wrote in recapping last year’s event, it felt like Google was catching up to its own ambitions. 
This year felt different. The center of gravity has moved further down the stack, into the unglamorous but essential work of actually running agents in production. Most of the meaningful new product introduced at Next ‘26 lives in the Govern and Optimize layers of the new Agent Platform, tackling unsexy necessities like identity, registry, gateway, anomaly detection, simulation, evaluation, and observability for agents. It’s the operational layer the platform has been missing, and its arrival suggests Google has been paying close attention to what’s actually hard about deploying agents at enterprise scale. 
That said, Google’s appetite for disruptive product and brand restructuring continues to play out here, and the relearning tax it imposes on customers and partners is significant, and a theme worth examining as we recap last week’s news. 
## Vertex AI is Dead Dying. Long Live Gemini Enterprise. 
Case in point, Vertex AI, the brand Google has been building up for half a decade as its unified AI development platform, is being retired. 
In its place sits the new Gemini Enterprise Agent Platform . Per Google, “all Vertex AI services and roadmap evolutions will be delivered exclusively through the Agent Platform, rather than as a standalone service.” The model building, model tuning, Model Garden, and agent tooling that used to sit under Vertex AI now sit inside Agent Platform, alongside a substantial set of new capabilities oriented at building, deploying, governing, and operating fleets of agents at enterprise scale. 
Above the Agent Platform sits the Gemini Enterprise app , the no-code, knowledge-worker-facing surface that evolved out of last year’s Agentspace. Sitting alongside it is an expanded Agent Marketplace stocked with partner-built agents from Adobe, Salesforce, ServiceNow, Workday, and others. Together, the three pieces form what Google is now calling Gemini Enterprise. 
Though I’ve been critical of Google Cloud’s brand and platform churn in prior posts, I do ultimately think killing the Vertex brand is the right move. “Vertex AI” had become a confusing parallel to the Gemini Enterprise brand. When I sat down with Riyaz Habibbhai, Director of Cloud AI Product Marketing, to record an episode of the TWIML Briefing Room at the event , he described the customer pain bluntly: prospects buying the Gemini Enterprise App were routinely asking, “do I also need to buy Vertex?” The answer was that Vertex was what powered Gemini Enterprise App, but the brand bifurcation was an active drag on adoption and an internal tax on Google’s own roadmap (which capabilities land where, which SDK, which docs, which billing line). Considering that the market for enterprise AI agents is many times larger than the MLOps market that gave birth to Vertex AI, folding it into Gemini Enterprise resolves a source of current and future friction. 

That said, while the brand unification is largely complete (though website and docs updates will continue over the next few weeks), the underlying API picture is unfortunately murkier. According to multiple sources at Google, the distinct Gemini ( google.genai ) and Vertex AI ( vertexai ) APIs will continue to coexist, despite the developer confusion this has caused since the launch of the Gemini API and Google AI Studio at the end of 2023. Indefinitely; not just for some well-defined transition period after which developers will have a unified API to learn and use. 
Consider the following code for creating an agent using the ADK: 
from google.adk.agents import Agent
from vertexai.agent_engines import AdkApp

agent = Agent(
 model=model, # Required.
 name='currency_exchange_agent', # Required.
 generate_content_config=generate_content_config, # Optional.
)
app = AdkApp(agent=agent) 
Wait, I thought Vertex was dead??? 
## The Agent Platform: Build, Scale, Govern, Optimize 
Beyond the rebrand brand consolidation, Google Cloud introduced new capabilities across the Agent Platform this year, and especially in its lower layers. Google has organized Gemini Enterprise Agent Platform around four verbs, Build , Scale , Govern , and Optimize , and each corresponds to a set of named services. 
### Build 
The Build layer is anchored on ADK and the new low-code Agent Studio . ADK 2.0 (Beta) adds three new orchestration primitives: graph-based workflows (deterministic, with explicit control over how tasks are routed and executed), collaborative agents (aka multi-agent or agent teams, with coordinator agents managing multiple subagents), and dynamic workflows (code-based logic for iterative loops and decision-based branching). ADK also now supports Skills across Python, Go, and TypeScript, allowing agents to dynamically discover and execute domain-specific skills. Speaking to the success and adoption of the ADK, Google says more than six trillion tokens a month are already flowing through ADK agents. 
Agent Studio is itself the consolidation of two prior tools, the old Vertex AI Studio and the Agent Designer experience, into a single visual builder. You can now build agents and multi-agent flows using natural language prompts, and deploy them directly to Agent Runtime without an export step, or export them and continue working on your agent in ADK code. This continuum from prompting to visual to code is an important hint at the cohesiveness of the platform, and the fulfillment in shipping product of a direction that Google hinted at with the Agentspace launch last year. 
Two other Build-layer pieces worth flagging: a new Agents CLI (Alpha) that bundles seven skills for managing the ADK lifecycle and can be installed into Gemini CLI, Claude Code, or Codex, turning your existing coding assistant into an Agent Platform expert; and an expanded Agent Garden with 10+ new “atomic” agents that serve as reusable building blocks for multi-agent systems. 
### Scale 
The Scale layer is about the operational characteristics required to run agents in production: managed runtime, persistent state, isolated execution, and long-term context. The connecting thread across the Scale features is support for the kinds of complex, real-world workloads that don’t fit neatly into the request/response model. 
The re-engineered Agent Runtime is now GA, with sub-second cold starts, support for long-running agents that hold state and execute autonomously for up to seven days, BYOC (C=containers) for custom runtime images, scaling to 3,000 agents per project, language support across Python, Java, TypeScript, and Go, and a “local equals cloud” guarantee that locally developed ADK agents behave identically when deployed. Agent Sandbox (also GA) provides a hardened environment for executing model-generated code and computer-use tasks; Computer Use sandboxes and a Snapshot API for stateful long-running async workflows are coming shortly after Next. Agent Sessions (GA) handles multi-turn state with custom session ID support that lets you map agent interactions to your existing CRM or database records. Agent Memory Bank (GA) provides long-term context with new Memory Profiles for high-accuracy, low-latency recall of user-specific facts. 
These new capabilities offer, in the aggregate, the most capable production runtime Google has shipped for agents. The early reference customer roster, including Comcast, L’Oreal, Macquarie Bank, and PayPal, is encouraging. 
### Govern 
Govern is where the bulk of this year’s net-new platform investment landed, and an area where I think Google has a strong relative story. 
Agent Identity (GA) is a new native IAM type. Built on the CNCF SPIFFE standard, it assigns every agent a unique cryptographic ID, supports least-privilege access policies, binds access tokens to the agent runtime, and ensures non-repudiable auditing of every agent action. Agent Registry (Preview) is the central catalog of agents, MCP servers, and endpoints across your organization, covering Google-built, customer-built, and third-party assets, with integration to ADK and Apigee API hub for automated registration. Agent Gateway (Private Preview) is the central control plane between agents and the tools and data they interact with, enforcing access policies, tool-use rules, and security policies through a single point, while mediating between different agentic protocols like A2A, MCP, REST, and gRPC. Model Armor , which has been around for a while, is now integrated directly into Agent Gateway to defend against prompt injection, tool poisoning, and data leakage at the infrastructure layer rather than inside individual applications. 
There is also Agent Anomaly Detection (Preview) for flagging unusual agent reasoning, an Agent Security dashboard that unifies threat detection and risk analysis, and Agent Compliance capabilities. If you’ve been the CISO listening to your developers tell you about the cool agent they want to ship but haven’t known what to say, this is the architectural answer the category needed. 
### Optimize 
Optimize is the other area where almost everything is net new at Next ‘26. Agent Simulation stress-tests agents against synthetic users and virtualized tools before shipping, with automatic scoring on task success and safety. Agent Evaluation continuously scores agents against live traffic with multi-turn autoraters that score the logic of an entire conversation rather than single responses. Agent Observability (Public Preview, GA later in Q2) provides turnkey dashboards, trace visualization, and the ability to inspect the directed acyclic graph of agent execution end-to-end. Agent Optimizer automatically clusters failures and proposes refined system instructions to improve accuracy. 
The Simulation/Evaluation/Observability/Optimizer loop is exactly what you want from an agent platform at this stage of the industry’s maturation. Most in this space have very simple takes focused on the review and evaluation of traces; Google is the first hyperscaler to ship a credible, integrated offering. 
### Availability 
A notable change relative to prior years is that this year’s announcements arrived with the product mostly in hand. Past Next events have created some frustration by announcing products that sounded exciting but were not immediately accessible. Last year’s Agentspace is a good example; there was no public access path for months after announcement, and when one was eventually publicized, it was sales-gated, geared toward large enterprises, and required a services engagement to deploy. Contrast that with this year: I was able to access Gemini Enterprise Agent Platform and explore the console and documentation during Next itself. That’s a significant and laudable change! 
There is obviously a lot here, and not all of it is equally mature. But all-in-all Google Cloud has delivered a substantially more complete enterprise agent platform than what they, or any of their contemporaries, had on offer just prior to Next. 
Google still has work to do on rounding out the documentation and user/developer experience for some of the newer capabilities, but the pace of filling in missing pieces has noticeably picked up. 
## Infrastructure, Data, and Workspace News 
### Two Chips and an Interconnect for the Agentic Era 
One of the unexpected highlights of this year’s Next was getting a few minutes to chat with the legendary Jeff Dean , Chief Scientist of Google DeepMind and Google Research. 

Was great to chat at The Future of AI Infrastructure event @JeffDean ! #GoogleCloudNext pic.twitter.com/tRLiaDxbDV — Sam Charrington (@samcharrington) April 22, 2026 
Jeff and I reminisced about our nearly decade-old podcast interview , and in particular the story of the back-of-the-envelope calculation that he recounted that ultimately resulted in the creation of the first Google Tensor Processing Unit, or TPU. 
Fast forward to this year’s Next, where Google announced for the first time in the history of the program, that it would ship its 8th generation processor as two distinct chips optimized for two distinct workloads. 
TPU 8t is focused on training new frontier models. A TPU 8t pod now scales to 9,600 chips with 2 PB of shared high-bandwidth memory, delivering 121 ExaFLOPs of compute. Google is claiming nearly 3x the compute per pod over Ironwood (the 7th gen TPU), a 10x speedup in storage access via TPUDirect, and “near-linear” scaling to more than one million chips in a single logical cluster. They are also targeting 97%+ “goodput” through automated fault handling, telemetry, and optical circuit switching, which at frontier-training scale translates to days of extra training time. 
TPU 8i is an inference-focused chip, and the more consequential announcement of the two in my view. It is designed for the latency-sensitive, high-concurrency workloads characteristic of agent swarms, and in particular for Mixture-of-Experts models and long-context reasoning. The headline specs: 288 GB HBM, 384 MB on-chip SRAM (3x Ironwood, sized explicitly for the KV cache footprint of reasoning models), 19.2 Tb/s ICI bandwidth, and a new on-chip Collectives Acceleration Engine that offloads global operations and cuts on-chip latency by up to 5x. The new Boardfly topology reduces the maximum network diameter of a 1,024-chip pod from 16 hops to 7 hops, a more than 50% reduction that targets exactly the all-to-all traffic patterns that frontier reasoning models generate. Net result: 80% better performance per dollar on inference vs. the prior generation. 
Both chips run on Google’s custom Axion Arm-based CPU hosts, are cooled by Google’s 4th-gen liquid cooling, and deliver 2x better performance per watt over Ironwood. They support native JAX, MaxText, PyTorch (including the new TorchTPU integration), SGLang, and vLLM. General availability is targeted for later this year. 
Paired with the new TPUs is Virgo Network , Google’s new megascale data center fabric. Virgo delivers 4x the bandwidth per accelerator of its predecessor, 40% lower fabric latency, and a collapsed-fabric architecture that supports 47 Pb/s of non-blocking bisection bandwidth. With Virgo and TPU 8t, Google can connect 134,000 TPUs in a single data center and more than one million across multiple data center sites into what is effectively one seamless supercomputer, orchestrated by Pathways and JAX! Virgo also supports NVIDIA Vera Rubin (A5X), scaling to 80,000 GPUs in one data center and 960,000 across sites. 
### Agentic Data Cloud: Plumbing for Agent-Scale Context 
Agents are only as smart as the context they can reason over, which is why the introduction of Agentic Data Cloud is also interesting. Agentic Data Cloud brings together a number of existing and new components including the evolved Knowledge Catalog . The Knowledge Catalog aggregates business context across your entire data estate, including third-party sources like Salesforce Data360, SAP, ServiceNow, and Workday. It continuously enriches that context by profiling actual usage, and exposes it via a hybrid semantic/lexical/reranked search stack that enforces existing access control policies at retrieval time. 
Underneath the Knowledge Catalog sit a set of performance and openness updates: Lightning Engine for Apache Spark (2x price-perf vs. the leading proprietary alternative), Managed Lustre at 10 TB/s (10x year-over-year), Bigtable’s new in-memory tier for sub-millisecond reads, BigQuery fluid scaling reducing autoscaling costs by up to 34%, Spanner Omni untethering Spanner from Google Cloud to run anywhere, and bi-directional federation via Apache Iceberg REST Catalog with Databricks Unity, Snowflake Polaris, and AWS Glue. 
Taken together, this is the plumbing behind the agent story. Knowledge Catalog plus an AI-native cross-cloud Data Lakehouse is Google’s answer to the agent-context problem, and it extends the openness-as-differentiation posture the company is running across the rest of the stack. 
### Workspace Intelligence: Continuing the Theme of Context 
Continuing the theme of context, the big Workspace announcement this year is a new layer called Workspace Intelligence , which provides a unified substrate of real-time retrieval, an organizational knowledge graph, workflow awareness and memory, and web grounding, shared across both human users and agents. The idea is that Workspace becomes the enterprise context layer that surfaces the same understanding of your organization to a person writing a doc and to an agent running in the background on their behalf. I also found the new Inbox in Gemini Enterprise, which gives employees a unified hub for monitoring and interacting with agents, to be an interesting indication of where Google thinks things are heading. 
## Key Takeaways 
- Vertex AI is gone. Saying goodbye to a half-decade of brand equity is not easy, but the upside is a cleaner story: Gemini Enterprise is the product, Agent Platform is the developer surface, Gemini Enterprise App is the knowledge worker surface, and the Marketplace is where partners plug in. 
- The platform is (mostly) ready. This is the most complete enterprise agent platform Google has ever shipped, with a thoughtfully organized Build/Scale/Govern/Optimize structure with features that solve real-world challenges faced by enterprise agent builders. There will undoubtedly be rough edges but the bones are there. 
- The announcements actually shipped. A meaningful contrast to past Next years, where so much was tagged “coming soon,” this year’s launches were almost all in preview or GA at announcement. As I told Riyaz on camera, “in prior years, much of the platform announcements were things that were coming soon. This time I went in and it was all there waiting for me.” The DX, docs, and console were in step with the keynote in a way I haven’t seen Google Cloud execute in years. 
- Inference is the strategic workload. Splitting the TPU line into dedicated training and inference chips is the loudest signal Google has sent about where it believes AI spend is heading. Silicon ships on long cycles, so this was a bet placed years ago on what today’s workloads would require. They seem to have bet well. 
- Openness is a wedge. With Claude in the Model Garden, MCP everywhere, Iceberg federation with Cross-Cloud Interconnect, Spanner Omni running off-cloud, support for a variety of agent frameworks, and many more examples, Google is clearly betting that customers running multi-cloud, multi-model, multi-agent, and multi-platform environments will reward the vendor that is least hostile to that reality. 
- Customer momentum is real. Google Cloud has amassed an impressive number of large, blue-chip enterprises ready to talk about their agentic AI successes in print and on stage. 
## Opportunities and Challenges 
- Complexity is growing. The Agent Platform surface area is large: ADK, Agent Studio, Agent Runtime, Memory Bank, Memory Profiles, Agent Sandbox, Agent Sessions, Agent Registry, Agent Gateway, Agent Identity, Agent Simulation, Agent Evaluation, Agent Observability, Agent Optimizer, Model Armor, Model Garden, AP2, A2A, MCP, BYO-MCP, A2UI, and more. There’s significant innovation in there, but Google’s developer education and advocacy machine has to catch up to this surface fast, or the platform will be perceived as powerful but bewildering. 
- “Agent washing” makes platform choice hard. Every tech giant now claims a comprehensive enterprise agent platform, and the language has converged to the point where customers struggle to differentiate. Google’s pitch—full stack, real roadmap, demonstrated cost/efficiency—is sound, but standing out in a sea of similar-sounding claims is itself now the marketing challenge. 
- Customer stories reflect where the platform was, not necessarily where it is. Google Cloud holds up customer stories as proof points of the modern agentic era. The caveat is that many of these were built against an earlier, simpler definition of what an agent is and what Google Cloud’s platform could do. The bar has moved considerably, and it’s worth asking how many of today’s showcase deployments would clear it. 
- Proof will be in long-lived workloads. Long-running agents with persistent memory in sandboxed environments are genuinely new product capabilities. It will be interesting to see what happens when enterprise developers start trying to build non-trivial workflows and hit the inevitable edge cases. I’ll be watching closely. 
- MCP governance is still a work in progress. “MCP everywhere” is a welcome posture: every Google Cloud service now has an MCP endpoint, and BYO-MCP support is built into key product surfaces. But fully wiring MCP into Google’s enterprise governance fabric (identity, gateway, policy enforcement) is a work in progress. Customers running cross-tool MCP architectures should size their governance assumptions accordingly. 
## Conclusion 
Google Cloud Next ‘26 was, more than anything, a delivery event. The vision had been articulated, a course correction made, and this year the company showed up with a platform it wants enterprises to adopt, run, and scale on. The combination of the Gemini Enterprise app, the Gemini Enterprise Agent Platform, the 8th-gen TPUs, the Virgo fabric, the Data Cloud and Knowledge Catalog, and the partner ecosystem plays adds up to the most coherent integrated story Google Cloud has ever told about AI. 
No other hyperscaler has assembled quite what Google is offering: agent tooling, silicon optimized for the agent workload, data fabric architected for agent-scale context, security architected for agent-scale risk, and a knowledge worker surface to put it all in the hands of everyone in the enterprise, all integrated by design. 
“Google Cloud CEO Thomas Kurian closed his day one keynote with a question that doubled as a challenge: ‘The platform is ready, so what will you build?’ 
It’s the right question, and its answer will be the measure of everything Google Cloud shipped this week. 

View tweet 
If you’re building on Google’s platform, I’d love to hear from you! Also, I’ll be at Google I/O in just a few weeks, where I expect the company to launch new frontier models and updated agentic tools and harnesses. Stay tuned for my thoughts and reflections, and let me know if you’ll be there too! 

## Social Media Highlights 

Excited to be back in Vegas for #GoogleCloudNext . I'll be covering the event as it unfolds, right here. Stay tuned, exciting announcements and updates to come! pic.twitter.com/twYwQRBiuS — Sam Charrington (@samcharrington) April 22, 2026 

. @sundarpichai Nearly 75% of new code @Google is AI generated, up from 50% last year. Completed complex migration 6x faster that before. @googlecloud #GoogleCloudNext pic.twitter.com/iutsyArGGP — Sam Charrington (@samcharrington) April 22, 2026 

Sundar announcing Gemini Enterprise Agent Platform. Idea is mission control for an enterprise's agents. [More details to come obvs.] @googlecloud #GoogleCloudNext pic.twitter.com/LuHdBiLErM — Sam Charrington (@samcharrington) April 22, 2026 

Digging into Gemini Enterprise and the Gemini Enterprise Agent Platform: 

- Low-code agent studio 
- Agent registry 
- Tools & skills registries 
- Observability tools 
- Agent marketplace 

and more. @googlecloud #GoogleCloudNext pic.twitter.com/G7Jh7vr3zq — Sam Charrington (@samcharrington) April 22, 2026 

Amin announcing @google new 8th generation TPUs. For the first time, two new chips in a generation, TPU 8t and TPU 8i, optimized for training and inference respectively. @googlecloud #GoogleCloudNext pic.twitter.com/7q29LBlNZm — Sam Charrington (@samcharrington) April 22, 2026 

Summary of new TPU specs. Google really leaning in to inference with the new 8i chip. Nearly 10x inference flops and 7x memory capacity per pod, vs prior generation. @googlecloud #GoogleCloudNext pic.twitter.com/kpAotd4cGb — Sam Charrington (@samcharrington) April 22, 2026 

New high performance Virgo Network allows months of training to be compressed to weeks. TPUs orchestrated by JAX. Nvidia VR also supported. @googlecloud #GoogleCloudNext pic.twitter.com/TanlpVQ6JG — Sam Charrington (@samcharrington) April 22, 2026 

. @Citadel Securities case study. Running workloads 2-4x as fast with 30% lower cost. Empowers company quants to test more/all of their ideas, vs having to be selective. @googlecloud #GoogleCloudNext pic.twitter.com/9GpOP0Q0GA — Sam Charrington (@samcharrington) April 22, 2026 

Agentic Data Cloud news: Lightning Engine for Spark (2x price-perf), Managed Lustre at 10 TB/s, Bigtable in-memory tier for sub-ms reads, and BigQuery fluid scaling cutting autoscale cost ~34%. The plumbing story behind the agent story. @googlecloud #GoogleCloudNext pic.twitter.com/lKzR7JW6k3 — Sam Charrington (@samcharrington) April 22, 2026 

Google's Agentic Defense pitch : Threat intel + SecOps + Wiz as one unified stack. New threat hunting, detection engineering, third-party context agents. Model armor plugged into agent gateway, and Wiz now covering AWS Agentcore, Azure Copilot Studio, and Salesforce Agentforce… pic.twitter.com/fPdGeWvkTf — Sam Charrington (@samcharrington) April 22, 2026 

The big @GoogleWorkspace story this year is focused on building comprehensive enterprise context for agents and humans via new Workspace Intelligence feature: realtime retrieval, knowledge graph, workflow awareness & memory, and web grounding, but lots of point feature updates… pic.twitter.com/WFwaUtnd5B — Sam Charrington (@samcharrington) April 22, 2026 

© 2026 CloudPulse Strategies 
All rights reserved 

About TWIML + 
- About 
- Contact 
- Newsletter 
Popular Content + 
- Podcast Episodes 
- Podcast Series 
- Podcast Topics 
Connect with Us + 
- YouTube 
- X 
- LinkedIn 
- Facebook 
- Instagram 
Our Policies + 
- Privacy Policy 
- Terms of Service 

© 2026 CloudPulse Strategies 
All rights reserved 