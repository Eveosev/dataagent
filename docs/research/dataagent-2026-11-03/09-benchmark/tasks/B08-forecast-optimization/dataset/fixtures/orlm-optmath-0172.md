Imagine you are managing the distribution of critical medical supplies across eight cities in a region. Each city has a specific supply or demand for these supplies, and your goal is to ensure that all cities receive the necessary resources while minimizing the total transportation cost. The transportation network connects these cities, and each route has a specific cost per unit of supply shipped, as well as a maximum capacity limit.

#### Cities and Their Supply/Demand:
- **City 0** has a net demand of **34 units** (it needs 34 more units than it currently has).
- **City 1** has a surplus of **11 units** (it can supply 11 units to other cities).
- **City 2** has a surplus of **22 units**.
- **City 3** has a surplus of **10 units**.
- **City 4** has a surplus of **2 units**.
- **City 5** has a surplus of **9 units**.
- **City 6** has a surplus of **6 units**.
- **City 7** has a net demand of **26 units**.

#### Transportation Costs and Capacities:
The cost of shipping one unit of supply between cities varies depending on the route. Below are the costs and maximum capacities for each route:

- **From City 0**:
  - To City 1: Cost = **9**, Capacity = **59**
  - To City 2: Cost = **8**, Capacity = **59**
  - To City 3: Cost = **8**, Capacity = **59**
  - To City 4: Cost = **9**, Capacity = **43**
  - To City 5: Cost = **10**, Capacity = **56**
  - To City 6: Cost = **10**, Capacity = **40**
  - To City 7: Cost = **9**, Capacity = **37**

- **From City 1**:
  - To City 0: Cost = **10**, Capacity = **36**
  - To City 2: Cost = **9**, Capacity = **36**
  - To City 3: Cost = **6**, Capacity = **40**
  - To City 4: Cost = **9**, Capacity = **39**
  - To City 5: Cost = **6**, Capacity = **57**
  - To City 6: Cost = **6**, Capacity = **44**
  - To City 7: Cost = **8**, Capacity = **56**

- **From City 2**:
  - To City 0: Cost = **6**, Capacity = **52**
  - To City 1: Cost = **6**, Capacity = **40**
  - To City 3: Cost = **6**, Capacity = **39**
  - To City 4: Cost = **7**, Capacity = **31**
  - To City 5: Cost = **9**, Capacity = **38**
  - To City 6: Cost = **6**, Capacity = **44**
  - To City 7: Cost = **10**, Capacity = **58**

- **From City 3**:
  - To City 0: Cost = **10**, Capacity = **30**
  - To City 1: Cost = **10**, Capacity = **49**
  - To City 2: Cost = **6**, Capacity = **52**
  - To City 4: Cost = **10**, Capacity = **47**
  - To City 5: Cost = **9**, Capacity = **47**
  - To City 6: Cost = **6**, Capacity = **30**
  - To City 7: Cost = **8**, Capacity = **34**

- **From City 4**:
  - To City 0: Cost = **6**, Capacity = **39**
  - To City 1: Cost = **8**, Capacity = **45**
  - To City 2: Cost = **9**, Capacity = **55**
  - To City 3: Cost = **8**, Capacity = **36**
  - To City 5: Cost = **6**, Capacity = **48**
  - To City 6: Cost = **6**, Capacity = **35**
  - To City 7: Cost = **10**, Capacity = **54**

- **From City 5**:
  - To City 0: Cost = **9**, Capacity = **43**
  - To City 1: Cost = **7**, Capacity = **58**
  - To City 2: Cost = **9**, Capacity = **49**
  - To City 3: Cost = **6**, Capacity = **33**
  - To City 4: Cost = **9**, Capacity = **59**
  - To City 6: Cost = **10**, Capacity = **30**
  - To City 7: Cost = **7**, Capacity = **59**

- **From City 6**:
  - To City 0: Cost = **10**, Capacity = **33**
  - To City 1: Cost = **7**, Capacity = **37**
  - To City 2: Cost = **6**, Capacity = **50**
  - To City 3: Cost = **7**, Capacity = **34**
  - To City 4: Cost = **9**, Capacity = **30**
  - To City 5: Cost = **6**, Capacity = **56**
  - To City 7: Cost = **10**, Capacity = **44**

- **From City 7**:
  - To City 0: Cost = **7**, Capacity = **46**
  - To City 1: Cost = **7**, Capacity = **58**
  - To City 2: Cost = **9**, Capacity = **60**
  - To City 3: Cost = **7**, Capacity = **34**
  - To City 4: Cost = **8**, Capacity = **39**
  - To City 5: Cost = **6**, Capacity = **57**
  - To City 6: Cost = **9**, Capacity = **42**

#### Objective:
Your task is to determine the optimal amount of supplies to ship between cities to meet all demands and surpluses while minimizing the total transportation cost. The shipments must respect the capacity limits of each route, and no negative shipments are allowed.

#### Constraints:
1. **Flow Balance**: For each city, the total amount of supplies shipped into the city must equal the total amount shipped out, adjusted for the city's supply or demand.
2. **Capacity Limits**: The amount of supplies shipped on any route cannot exceed the maximum capacity for that route.
3. **Non-Negativity**: All shipments must be non-negative.

By solving this problem, you will ensure that all cities receive the necessary medical supplies at the lowest possible transportation cost.