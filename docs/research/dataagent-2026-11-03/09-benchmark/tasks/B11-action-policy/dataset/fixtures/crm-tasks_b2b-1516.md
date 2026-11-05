# CRMArena tasks_b2b / case_routing / idx 1516

## 必填业务知识

## Case Routing Policy
The case routing policy determines the best agent to assign the given new case based on the following criteria
- Issue Expertise: The agent who has closed the most cases associated with the issue most similar to the given case.
- Product Expertise: If there is a tie in issue expertise, the best agent is the one who has solved the most cases associated with the product most relevant to the given case.
- Workload: If there is still a tie, the best agent is the one that has least cases with Status not 'Closed'.


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

Use the case routing policy to determine the most suitable agent for the given case. Return only the Id of the agent.
## Given Case
- Case Subject: Unexpected Data Loss During Update
- Case Description: I recently experienced a significant issue while using the OptiPower Max. During a routine software update, I encountered unanticipated data loss. This incident has caused substantial operational setbacks for my business. I need immediate assistance to recover the lost data and ensure this does not happen in future updates.
