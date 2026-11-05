> ## Documentation Index
> Fetch the complete documentation index at: https://julius.ai/docs/llms.txt
> Use this file to discover all available pages before exploring further.

# Overview

> Learn how to securely connect Julius to your data warehouses and databases to analyze your data directly without uploading files.

## What is a Data Connector?

A **Data Connector** lets you connect Julius to your data warehouses (PostgreSQL, BigQuery, Snowflake, etc.) by providing your database credentials. You can then analyze your data directly without downloading and uploading files.

> [!TIP]
>
> Once a connector is enabled, it's available for your entire chat session. Julius can access and query your data across all messages in that session.

## Benefits of Using Data Connectors

* **Real-time Analysis:** Query live data directly from your production databases
* **No File Management:** Skip the hassle of downloading, uploading, and managing data files
* **Always Up-to-Date:** Work with the latest data without manual exports
* **Secure Connection:** Your credentials are encrypted and your data never leaves your control
* **Team Collaboration:** Share access to the same data sources across your team

## Getting to Data Connectors Settings

1. Navigate to your **Settings** by clicking on your profile in the top right corner
2. Select **Data Connectors** from the settings menu
3. Or go directly to: [julius.ai/settings/data\_connectors](https://julius.ai/settings/data_connectors)

## Supported Database Types

Julius currently supports connections to the following database types:

> [card] [PostgreSQL](https://julius.ai/docs/data-connectors/postgres.md)
>
> Connect to PostgreSQL databases and data warehouses

> [card] [MySQL](https://julius.ai/docs/data-connectors/mysql.md)
>
> Connect to MySQL databases

> [card] [SQL Server](https://julius.ai/docs/data-connectors/sqlserver.md)
>
> Connect to Microsoft SQL Server

> [card] [Snowflake](https://julius.ai/docs/data-connectors/snowflake.md)
>
> Connect to Snowflake cloud data warehouse

> [card] [BigQuery](https://julius.ai/docs/data-connectors/bigquery.md)
>
> Connect to Google BigQuery data warehouse

> [card] [Supabase](https://julius.ai/docs/data-connectors/supabase.md)
>
> Connect to Supabase-hosted Postgres

> [card] [Google Ads](https://julius.ai/docs/data-connectors/google-ads.md)
>
> Connect to Google Ads for campaign analysis and optimization

> [card] [Meta Ads](https://julius.ai/docs/data-connectors/meta-ads.md)
>
> Connect to Meta (Facebook/Instagram) Ads for social advertising insights

## Built-in Data Tools

Beyond the connectors you set up yourself, Julius has built-in tools that reach external data on your behalf , no configuration required. Julius decides when to use them based on your question.

> [card] Web Search
>
> Julius can search the live web for news, background, documentation, and other fresh information using a native web search tool. Results are grounded with citations, and searches can be scoped to specific domains via custom agents.

> [card] Financial Market Data
>
> Julius can pull US equity data , fundamentals, filings (10-K/10-Q/8-K), earnings, insider trades, institutional holdings, historical prices, and interest rates , directly into your chat for analysis.

> [!NOTE]
>
> Built-in tools run on Julius credits , the same usage-based system as the rest of Julius. No separate plan or setup required.

## Security & Trust

* **SOC 2 Type 2 Certified:** Julius meets strict security standards for handling sensitive data
* **Encryption:** All credentials and data are encrypted both in transit and at rest
* **No Data Storage:** Julius doesn't permanently store your data - it only queries what you request
* **Access Control:** Only you can access connections you create

> [card] [Learn More About Security](https://julius.ai/security)
>
> Visit our Security & Trust Center to learn more about how Julius protects your data and maintains compliance standards.

## How Data Connectors Work

1. **Setup:** Provide your database credentials through our secure connection form
2. **Connect:** Julius establishes an encrypted connection to your database
3. **Query:** Ask Julius questions about your data in natural language
4. **Analyze:** Julius writes and executes SQL queries automatically
5. **Visualize:** Get results, charts, and insights without writing any code

> [!WARNING]
>
> Always coordinate with your database administrator when setting up data connectors to ensure proper security and performance guidelines are followed.

## Sharing your Data-Connection with your Team

If you have a Team and want to set up the Data Connection for your team members, here's how:

**1. Navigate to the Data Connector Page**

go to your Data Connector page at: [https://julius.ai/data-connectors](https://julius.ai/data-connectors)

**2. Share the Connector**

Click on the kebab icon and then 'Share with Team'

![Share connector with team in Data Connectors](https://mintcdn.com/julius-d061c216/FYM8NUtCrVJzhSKO/images/data-connectors/overview/data-connectors-share-with-team.png?fit=max\&auto=format\&n=FYM8NUtCrVJzhSKO\&q=85\&s=dccf8ca6b8f9f4b1221779b37a2e2325)

**3. Connection will now show up for all team members under Team Connections**

Users on the respective team will be able to select the connection and use it in their own conversations within Julius.

## Getting Started

Choose your database type above and follow the setup guide.

***

> [!NOTE]
>
> Reach out to [**team@julius.ai**](mailto:team@julius.ai) for support or to ask questions not answered in our documentation.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.