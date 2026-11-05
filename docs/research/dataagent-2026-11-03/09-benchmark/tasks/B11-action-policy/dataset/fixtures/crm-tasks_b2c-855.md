# CRMArena tasks_b2c / sales_amount_understanding / idx 855

## 必填业务知识


        ## Sales Amount Policy
        - Definition: The sales amount for an order is calculated as the product of the quantity and the unit price from the Order object (Quantity * UnitPrice). An opportunity is eligible if its associated contract has a company signed date that falls within the time interval of interest.
        
        - Today's date: 2023-07-28

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

You are communication-focused, valuing clear and transparent information sharing.

## 问题

Identify the agent who achieved the highest sales in orders over the past four quarters. Return only the Id of the agent. 
