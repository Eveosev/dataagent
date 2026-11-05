# CRMArena tasks_b2c / transfer_count / idx 1230

## 必填业务知识

## Transfer Count Policy
- Definition: The number of instances a case was reassigned or transferred from one agent to another. Each transfer from agent A to agent B adds to the transfer count for agent A.
- In the queries that specify 'agents managed/queries x cases' -- this filter applies to both the first agent that the case was first assigned to and the agent that the case was transferred to. This means that if an agent has 2 cases that was initially assigned to itself by admin and 1 case transferred from another agent, a filter like 'handled/managed at least 3 cases' would not filter this agent out.
- For cases that have NOT been transferred to an other agent, there will be only ONE 'Owner Assignment', and for those that have been transferred, there will be MORE THAN ONE 'Owner Assignment'. 

## Today's date: 2022-12-03

## 可选领域知识

# Domain Details
## Quarters of the Year
- Q1: January 1 to March 31 (both inclusive).
- Q2: April 1 to June 30 (both inclusive).
- Q3: July 1 to September 30 (both inclusive).
- Q4: October 1 to December 31 (both inclusive).
## Seasons
- Winter (2024): December 1, 2024 to February 28/29, 2025 (both inclusive), specifying the year to avoid ambiguity.
- Spring: March 1 to May 31 (both inclusive).
- Summer: June 1 to August 31 (both inclusive).
- Autumn/Fall: September 1 to November 30 (both inclusive).
## Time Periods
- Past 2 quarters: This refers to any timeframe spanning two quarters back from a specified `end_date`. (i.e. begins on the date calculated by subtracting six months from the end_date and ends on the end_date) That translates to a six-month period retrospectively from the `end_date`.
- Issue Significantly More Than Other Months: This means there is a month where the number of cases reported are larger than all other months.

## 用户画像

You are collaborative and team-oriented, valuing input from all stakeholders before making decisions.

## 问题

Identify the agent with the highest number of transfers in the last 3 months among those who dealt with more than 3 cases. Return only the Id of the agent.
