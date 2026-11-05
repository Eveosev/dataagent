# 查询任务（dw）

## 问题

For each department hierarchy, provide the department hierarchy name, the average and standard deviation (using STDDEV only and never STDDEV_POP) of the organization level for organizations in that hierarchy, and for each department in that hierarchy, give the department's name, the maximum and minimum area of rooms assigned to that department (considering only rooms with an area greater than 40), and the difference between the department's average room area and the overall average room area for all such rooms. Present the results ordered by department hierarchy name and then by the difference in average area in descending order. Do not return any rounded answers.

## 库

dw

## 涉及表

["MASTER_DEPT_HIERARCHY", "FCLT_ORGANIZATION", "FCLT_ORG_DLC_KEY", "FCLT_ROOMS"]

## 连接键

[["FCLT_ORGANIZATION.DLC_KEY", "MASTER_DEPT_HIERARCHY.DLC_KEY"], ["FCLT_ORGANIZATION.FCLT_ORGANIZATION_KEY", "FCLT_ORG_DLC_KEY.FCLT_ORGANIZATION_KEY"], ["FCLT_ORGANIZATION.FCLT_ORGANIZATION_KEY", "FCLT_ROOMS.FCLT_ORGANIZATION_KEY"]]

## 列映射

{"department hierarchy": ["MASTER_DEPT_HIERARCHY.DLC_NAME"], "department hierarchy name": ["MASTER_DEPT_HIERARCHY.DLC_NAME"], "average of the organization level": ["FCLT_ORGANIZATION.ORGANIZATION_LEVEL"], "standard deviation of the organization level": ["FCLT_ORGANIZATION.ORGANIZATION_LEVEL"], "organizations in that hierarchy": ["FCLT_ORGANIZATION.DLC_KEY"], "department's name": ["FCLT_ORGANIZATION.ORGANIZATION_NAME"], "maximum area of rooms": ["FCLT_ROOMS.AREA"], "minimum area of rooms": ["FCLT_ROOMS.AREA"], "rooms assigned to that department": ["FCLT_ROOMS.FCLT_ORGANIZATION_KEY"], "area greater than 40": ["FCLT_ROOMS.AREA"], "department's average room area": ["FCLT_ROOMS.AREA"], "overall average room area": ["FCLT_ROOMS.AREA"], "difference between the department's average room area and the overall average room area": ["FCLT_ROOMS.AREA"]}

## 领域知识

[]

## 表结构

### FCLT_ORGANIZATION

- 列：["FCLT_ORGANIZATION_KEY", "ORGANIZATION_ID", "ORGANIZATION", "ORGANIZATION_NAME", "FCLT_ORG_PARENT_KEY", "ORG_PARENT", "FCLT_MAJOR_ORG_KEY", "MAJOR_ORG", "ORGANIZATION_LEVEL", "ORGANIZATION_NUMBER", "ORGANIZATION_SORT", "ASSIGNABLE", "COURSE", "DESCRIPTION", "WAREHOUSE_LOAD_DATE", "DLC_KEY", "DLC_NAME", "HR_DEPARTMENT_CODE_OLD", "HR_ORG_UNIT_ID", "HR_DEPARTMENT_NAME"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2"]
- 示例：[[188, 188, "LI&PHL", "LING & PHIL", 244.0, "S H&SS", 230, "PROVST", 5, 94000.0, 101060147.0, 1, "24", "Department of Linguistics and Philosophy", "19-DEC-24", "D_L&P", "Linguistics & Philosophy", 94000.0, 10000367.0, "Linguistics & Philosophy"], [121, 121, "CARDSV", "CARD SERVICES", 160.0, "ENTSVC", 129, "CHNCLR", 6, 862000.0, 101030310.0, 1, NaN, NaN, "19-DEC-24", "D_MITCARD", "MIT Card Office",

### FCLT_ORG_DLC_KEY

- 列：["FCLT_ORGANIZATION_KEY", "DLC_KEY"]
- 类型：["VARCHAR2", "VARCHAR2"]
- 示例：[[133, "D_CAC"], [254, NaN], [248, "D_MECHE"]]

## 子问题

["For each department hierarchy, give the department hierarchy name and find the average and standard deviation of the organization level for organizations in that hierarchy.", "For each department, give the department's name and calculate the range and variance of the areas of rooms assigned to it, considering only rooms with an area greater than 40.", "For each department hierarchy and its departments, give the department hierarchy name, the average and standard deviation of the organization level for organizations in that hierarchy, the department's name, and the range and variance of the areas of rooms assigned to that department (considering only rooms with an area greater than 40). Present the results ordered by department hierarchy name and then by area range in descending order."]
