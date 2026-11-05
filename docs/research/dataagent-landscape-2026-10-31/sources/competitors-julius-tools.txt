> ## Documentation Index
> Fetch the complete documentation index at: https://julius.ai/docs/llms.txt
> Use this file to discover all available pages before exploring further.

# Tools & capabilities

> As Julius works, it calls tools: running code, querying data, researching the web, and building finished deliverables.

When you give Julius a task, it takes actions, not only text replies. Each action is a **tool**: running code, querying a database, searching the web, building a slide deck. You'll see each step labeled in the chat as it happens, like **Generated code**, **Searched internet**, or **Created slides**. Expand any step to see what Julius did.

You never invoke these yourself. Julius decides which tools to use based on your request, your model, your plan, and the data you've connected.

> [!TIP]
>
> Tools also drive your [credit](https://julius.ai/docs/billing/credits-overview.md) usage. Running code, searching the web, or generating a deck costs more than a simple text answer.

***

## Core tools

### Run code

The tool behind most of what Julius does. Julius writes **Python** or **R** and runs it in a secure cloud [container](https://julius.ai/docs/get-started/containers.md) to clean data, run analysis, build models, and produce charts. Code runs automatically, and Julius installs any libraries it needs.

In the chat this appears as **Generating code → Generated code**. You can read the code, copy it, and see its output inline.

> Clean this dataset and show me the correlation between spend and revenue

### Edit files (apply patch)

When Julius works with files or code, it can make **surgical edits** instead of rewriting everything, changing only the lines that need to change. Long files and scripts stay intact as it iterates.

In the chat this appears as **Editing file → Edited file**, with a diff of what changed.

### Build visualizations

Julius generates **interactive charts** from your data (bar, line, scatter, and more) that you can hover and read in the browser. For static charts, see [Data visualizations](https://julius.ai/docs/get-started/data-visualizations.md). For full dashboards and apps, see [Interactive artifacts](https://julius.ai/docs/artifacts/interactive-artifacts.md).

In the chat this appears as **Generating visualization → Generated visualization**.

### Create presentations

Julius builds a complete **presentation** from a prompt, file, research, or analysis. It can create the story, charts, visuals, layout, and styling, then deliver the presentation as HTML, PowerPoint, PDF, PNG, Google Slides, or another useful format.

In the chat this appears as **Creating slides → Created slides**. See [AI Presentation Maker](https://julius.ai/docs/create-presentations.md) for prompting tips, templates, formats, and sharing options.

> Turn this analysis into a 10-slide deck for my team

### Build websites

Julius creates **websites and web apps** from plain-language instructions. It writes the page, previews it in the browser, and lets you refine the copy, design, and interactions in chat before publishing it to a shareable link.

Open the **Build Website** tab or ask for a website in any conversation. See [AI Website Builder](https://julius.ai/docs/create-websites.md).

> Build a responsive launch page from this product brief and include an early-access form

### Generate images

Julius can **create and edit images** from a description: diagrams, illustrations, or visuals for a deck or report.

In the chat this appears as **Generating image → Generated image**.

### Generate videos

Julius can **prompt to make videos from scratch or animate your images directly**. Use it for short clips, animated explainers, or bringing a static chart or image to life.

Accessible through the **Video** tab in the chat interface.

In the chat this appears as **Generating video → Generated video**.

> Animate this chart so the bars grow in one at a time

***

## Working with your data

### Query connected databases

When you've connected a database or warehouse, Julius writes and runs **SQL** against it directly. That covers Postgres, MySQL, SQL Server, Snowflake, BigQuery, Databricks, and more. You'll see steps like **Querying BigQuery → Queried BigQuery**. See [Data Connectors](https://julius.ai/docs/data-connectors/overview.md).

### Explore your schema

Before querying an unfamiliar database, Julius can **search the schema** to find the right tables and columns, so it writes correct SQL instead of guessing. This shows up as **Searching schema** and **Looked up schema**.

### Pull financial and market data

For finance questions, Julius can pull **market and financial datasets** (prices, fundamentals, filings, and macro data) and analyze them like any other source. This appears as **Querying financial data → Queried financial data**.

***

## Research & assistance tools

### Search the web

Julius can **search the internet** to pull in current information your data doesn't contain, like context, definitions, or recent events. This appears as **Searching internet → Searched internet**.

### Write reports

Julius can produce a long-form, structured **report** from your conversation and revise it section by section. See [Reports](https://julius.ai/docs/artifacts/reports.md).

### Ask you a question

When a request is ambiguous, Julius may pause to **ask you a quick clarifying question** rather than guess, so the work matches what you wanted.

***

> [!NOTE]
>
> The available tools vary by model, plan, and the data sources you've connected. The list above is what Julius *can* do, not a fixed menu shown every time.

***

## Related

* [Artifacts](https://julius.ai/docs/artifacts/overview.md): the deliverables these tools produce
* [Containers](https://julius.ai/docs/get-started/containers.md): the sandbox where code runs
* [Data Connectors](https://julius.ai/docs/data-connectors/overview.md): connect your databases and warehouses
* [Understanding credits](https://julius.ai/docs/billing/credits-overview.md): how tool usage affects credits

> [!NOTE]
>
> Wondering whether Julius can do something specific? Ask it in the chat, or email [**team@julius.ai**](mailto:team@julius.ai).


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.