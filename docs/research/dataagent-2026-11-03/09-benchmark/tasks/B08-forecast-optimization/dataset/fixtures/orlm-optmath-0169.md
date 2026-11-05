 Inventory Management with Backlogging in a Retail Supply Chain

You are managing the inventory and ordering process for a retail supply chain over a 19-week period. Your goal is to minimize the total costs associated with ordering, holding inventory, and backlogging unmet demand, while ensuring that customer demand is met as efficiently as possible. The costs and constraints are as follows:

#### **Cost Components:**
1. **Ordering Costs**: Each time an order is placed in a given week, a fixed cost is incurred. These costs vary by week and are as follows:
   - Week 1: \$930, Week 2: \$881, Week 3: \$925, Week 4: \$808, Week 5: \$711, Week 6: \$785, Week 7: \$997, Week 8: \$820, Week 9: \$843, Week 10: \$631, Week 11: \$726, Week 12: \$1,071, Week 13: \$741, Week 14: \$1,157, Week 15: \$916, Week 16: \$791, Week 17: \$1,055, Week 18: \$932, Week 19: \$794.

2. **Variable Ordering Costs**: In addition to the fixed costs, there is a variable cost per unit ordered in each week. These costs are:
   - Week 1: \$40, Week 2: \$26, Week 3: \$38, Week 4: \$20, Week 5: \$25, Week 6: \$22, Week 7: \$40, Week 8: \$39, Week 9: \$25, Week 10: \$26, Week 11: \$34, Week 12: \$25, Week 13: \$26, Week 14: \$27, Week 15: \$27, Week 16: \$35, Week 17: \$23, Week 18: \$26, Week 19: \$36.

3. **Inventory Holding Costs**: Holding inventory at the end of each week incurs a cost per unit. These costs are:
   - Week 1: \$19, Week 2: \$16, Week 3: \$24, Week 4: \$23, Week 5: \$24, Week 6: \$23, Week 7: \$20, Week 8: \$21, Week 9: \$21, Week 10: \$25, Week 11: \$15, Week 12: \$20, Week 13: \$24, Week 14: \$16, Week 15: \$16, Week 16: \$16, Week 17: \$19, Week 18: \$15, Week 19: \$20.

4. **Backlogging Costs**: If demand cannot be met in a given week, the unmet demand is backlogged to the next week, incurring a cost per backlogged unit. These costs are:
   - Week 1: \$55, Week 2: \$54, Week 3: \$71, Week 4: \$58, Week 5: \$51, Week 6: \$55, Week 7: \$45, Week 8: \$52, Week 9: \$60, Week 10: \$52, Week 11: \$52, Week 12: \$52, Week 13: \$76, Week 14: \$50, Week 15: \$47, Week 16: \$66, Week 17: \$70, Week 18: \$48, Week 19: \$69.

#### **Demand Constraints:**
- The demand for each week must be met either by the inventory on hand, the units ordered in that week, or by backlogging to the next week. The demand for each week is as follows:
  - Week 1: 495 units, Week 2: 316 units, Week 3: 375 units, Week 4: 467 units, Week 5: 418 units, Week 6: 398 units, Week 7: 533 units, Week 8: 525 units, Week 9: 361 units, Week 10: 452 units, Week 11: 470 units, Week 12: 378 units, Week 13: 302 units, Week 14: 463 units, Week 15: 438 units, Week 16: 383 units, Week 17: 377 units, Week 18: 429 units, Week 19: 324 units.

#### **Inventory and Backlogging Rules:**
- The inventory at the start of Week 1 and the end of Week 19 must be zero.
- The backlogged demand at the start of Week 1 and the end of Week 19 must also be zero.
- The amount ordered in any week cannot exceed the total demand over the 19-week period (7,904 units) if an order is placed in that week.

#### **Objective:**
Your task is to determine the optimal ordering schedule, inventory levels, and backlogged amounts for each week to minimize the total cost, which includes fixed ordering costs, variable ordering costs, inventory holding costs, and backlogging costs.

#### **Key Decisions:**
1. **Order Placement**: Decide whether to place an order in each week (a binary decision: yes or no).
2. **Order Quantity**: Determine the number of units to order in each week.
3. **Inventory Levels**: Decide how much inventory to hold at the end of each week.
4. **Backlogged Demand**: Determine the amount of unmet demand to backlog to the next week.

By carefully balancing these decisions, you aim to minimize the total cost while ensuring that all customer demand is met either immediately or through backlogging.