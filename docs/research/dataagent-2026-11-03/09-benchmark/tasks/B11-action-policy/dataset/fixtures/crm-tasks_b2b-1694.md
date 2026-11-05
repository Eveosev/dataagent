# CRMArena tasks_b2b / lead_routing / idx 1694

## 必填业务知识


        ## Lead Routing Policy
        The lead routing policy determines the best agent to assign the given new lead based on the following criteria:
        - Territory Match: First, find the territory that matches the lead's region by comparing with the territory description (comma-separated list of states/regions).
        - Quote Success: Among agents associated with the matching territory, select those with the highest number of quotes with status "Accepted" (find the agent ID through the associated opportunity ID).
        - Workload Balance: If there's still a tie, select the agent with the fewest unconverted (open) leads.
        
        ## Lead's region: VT
        

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

You are growth-minded, constantly seeking opportunities for personal and professional development.

## 问题

For this lead, which agent is the most suitable for assignment? Return only the Id of the agent.
