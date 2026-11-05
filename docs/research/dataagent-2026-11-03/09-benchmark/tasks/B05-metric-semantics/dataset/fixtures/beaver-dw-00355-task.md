# 查询任务（dw）

## 问题

For each of the top 10 space units by the number of rooms they contain, display the space unit name, the count of rooms, the department hierarchy name associated with the space unit, the average organization level for organizations in that hierarchy, the standard deviation (using STDDEV only and never STDDEV_POP) of the organization level for organizations in that hierarchy, and the total square footage of all rooms in the space unit. Do not return any rounded answers.

## 库

dw

## 涉及表

["MASTER_DEPT_HIERARCHY", "FCLT_ORGANIZATION", "SPACE_DETAIL", "SPACE_UNIT"]

## 连接键

[["FCLT_ORGANIZATION.DLC_KEY", "MASTER_DEPT_HIERARCHY.DLC_KEY"], ["SPACE_DETAIL.SPACE_UNIT_KEY", "SPACE_UNIT.SPACE_UNIT_KEY"]]

## 列映射

{"space unit name": ["SPACE_UNIT.SPACE_UNIT"], "number of rooms": ["SPACE_DETAIL.BUILDING_ROOM", "SPACE_UNIT.SPACE_UNIT_KEY"], "count of rooms": ["SPACE_DETAIL.BUILDING_ROOM", "SPACE_UNIT.SPACE_UNIT_KEY"], "department hierarchy name": ["MASTER_DEPT_HIERARCHY.DLC_NAME", "SPACE_UNIT.DLC_KEY"], "average organization level": ["FCLT_ORGANIZATION.ORGANIZATION_LEVEL", "MASTER_DEPT_HIERARCHY.DLC_NAME"], "standard deviation of the organization level": ["FCLT_ORGANIZATION.ORGANIZATION_LEVEL", "MASTER_DEPT_HIERARCHY.DLC_NAME"], "total square footage": ["SPACE_DETAIL.ROOM_SQUARE_FOOTAGE", "SPACE_UNIT.SPACE_UNIT_KEY"]}

## 领域知识

[]

## 表结构

### FCLT_ORGANIZATION

- 列：["FCLT_ORGANIZATION_KEY", "ORGANIZATION_ID", "ORGANIZATION", "ORGANIZATION_NAME", "FCLT_ORG_PARENT_KEY", "ORG_PARENT", "FCLT_MAJOR_ORG_KEY", "MAJOR_ORG", "ORGANIZATION_LEVEL", "ORGANIZATION_NUMBER", "ORGANIZATION_SORT", "ASSIGNABLE", "COURSE", "DESCRIPTION", "WAREHOUSE_LOAD_DATE", "DLC_KEY", "DLC_NAME", "HR_DEPARTMENT_CODE_OLD", "HR_ORG_UNIT_ID", "HR_DEPARTMENT_NAME"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2"]
- 示例：[[188, 188, "LI&PHL", "LING & PHIL", 244.0, "S H&SS", 230, "PROVST", 5, 94000.0, 101060147.0, 1, "24", "Department of Linguistics and Philosophy", "19-DEC-24", "D_L&P", "Linguistics & Philosophy", 94000.0, 10000367.0, "Linguistics & Philosophy"], [121, 121, "CARDSV", "CARD SERVICES", 160.0, "ENTSVC", 129, "CHNCLR", 6, 862000.0, 101030310.0, 1, NaN, NaN, "19-DEC-24", "D_MITCARD", "MIT Card Office",

### SPACE_DETAIL

- 列：["BUILDING_KEY", "FLOOR_KEY", "SPACE_UNIT_KEY", "SPACE_USAGE_KEY", "BUILDING_ROOM", "BUILDING_ROOM_NAME", "ROOM_NUMBER", "ROOM_SQUARE_FOOTAGE", "ROOM_COUNTER", "BUILDING_COMPONENT", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "NUMBER", "VARCHAR2", "DATE"]
- 示例：[["3", "4", 65000.0, 54, "3-470F", "3-470F", "70F", 321, 1, "3", "19-DEC-24"], ["14", "4", 93800.0, 54, "14N-485", "14N-485", "85", 150, 1, "14N", "19-DEC-24"], ["1", "2", 446700.0, 13, "1-221E", "1-221E", "21E", 6, 1, "1", "19-DEC-24"]]

## 子问题

["For each department hierarchy, give the department hierarchy name and find the average and standard deviation of the organization level for organizations in that hierarchy.", "List the top 10 space units by the number of rooms they contain, showing the space unit name and the count of rooms for each.", "For each of the top 10 space units by the number of rooms they contain, display the space unit name, the count of rooms, the department hierarchy name associated with the space unit, the average organization level for organizations in that hierarchy, and the standard deviation of the organization level for organizations in that hierarchy."]
