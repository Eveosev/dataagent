# 查询任务（dw）

## 问题

For rooms located on floor 2 with access level 1, show the building room, building component, floor, space usage, space unit code, access level, organization name, organization, department name, department code, and the minimum access level over each department code group, along with the department long name, department hierarchy level 3 name, the number of unique facility organization keys, the minimum organization unit ID, and the department hierarchy level 2 name for departments where the department hierarchy type is 'Standard Hierarchy' and the organization unit level is 'DEPARTMENTS'. Order the results by department code and department hierarchy level 3 name. Do not return any rounded answers.

## 库

dw

## 涉及表

["ZPM_ROOMS_LOAD", "FCLT_ORGANIZATION", "HR_ORG_UNIT", "FCLT_ORG_DLC_KEY", "MASTER_DEPT_HIERARCHY"]

## 连接键

[["FCLT_ORGANIZATION.HR_ORG_UNIT_ID", "ZPM_ROOMS_LOAD.HR_ORG_UNIT_ID"], ["FCLT_ORGANIZATION.HR_ORG_UNIT_ID", "HR_ORG_UNIT.HR_ORG_UNIT_ID"], ["FCLT_ORG_DLC_KEY.DLC_KEY", "MASTER_DEPT_HIERARCHY.DLC_KEY"], ["HR_ORG_UNIT.DLC_KEY", "MASTER_DEPT_HIERARCHY.DLC_KEY"]]

## 列映射

{"rooms": ["ZPM_ROOMS_LOAD.BUILDING_ROOM"], "building room": ["ZPM_ROOMS_LOAD.BUILDING_ROOM"], "building component": ["ZPM_ROOMS_LOAD.BUILDING_COMPONENT"], "floor": ["ZPM_ROOMS_LOAD.FLOOR"], "space usage": ["ZPM_ROOMS_LOAD.SPACE_USAGE"], "space unit code": ["ZPM_ROOMS_LOAD.SPACE_UNIT_CODE"], "access level": ["ZPM_ROOMS_LOAD.ACCESS_LEVEL"], "organization name": ["FCLT_ORGANIZATION.ORGANIZATION_NAME"], "organization": ["FCLT_ORGANIZATION.ORGANIZATION"], "department name": ["HR_ORG_UNIT.HR_DEPARTMENT_NAME"], "department code": ["HR_ORG_UNIT.HR_DEPARTMENT_CODE"], "minimum access level": ["ZPM_ROOMS_LOAD.ACCESS_LEVEL", "HR_ORG_UNIT.HR_DEPARTMENT_CODE"], "department long name": ["HR_ORG_UNIT.HR_DEPARTMENT_NAME_LONG"], "department hierarchy level 3 name": ["MASTER_DEPT_HIERARCHY.MASTER_DEPT_HIER_LEVEL_3_NAME"], "number of unique facility organization keys": ["FCLT_ORG_DLC_KEY.FCLT_ORGANIZATION_KEY"], "minimum organization unit ID": ["HR_ORG_UNIT.HR_ORG_UNIT_ID"], "department hierarchy level 2 name": ["MASTER_DEPT_HIERARCHY.MASTER_DEPT_HIER_LEVEL_2_NAME"], "department hierarchy type": ["MASTER_DEPT_HIERARCHY.HIERARCHY_TYPE"], "organization unit level": ["HR_ORG_UNIT.HR_ORG_UNIT_LEVEL"]}

## 领域知识

[]

## 表结构

### FCLT_ORGANIZATION

- 列：["FCLT_ORGANIZATION_KEY", "ORGANIZATION_ID", "ORGANIZATION", "ORGANIZATION_NAME", "FCLT_ORG_PARENT_KEY", "ORG_PARENT", "FCLT_MAJOR_ORG_KEY", "MAJOR_ORG", "ORGANIZATION_LEVEL", "ORGANIZATION_NUMBER", "ORGANIZATION_SORT", "ASSIGNABLE", "COURSE", "DESCRIPTION", "WAREHOUSE_LOAD_DATE", "DLC_KEY", "DLC_NAME", "HR_DEPARTMENT_CODE_OLD", "HR_ORG_UNIT_ID", "HR_DEPARTMENT_NAME"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2"]
- 示例：[[188, 188, "LI&PHL", "LING & PHIL", 244.0, "S H&SS", 230, "PROVST", 5, 94000.0, 101060147.0, 1, "24", "Department of Linguistics and Philosophy", "19-DEC-24", "D_L&P", "Linguistics & Philosophy", 94000.0, 10000367.0, "Linguistics & Philosophy"], [121, 121, "CARDSV", "CARD SERVICES", 160.0, "ENTSVC", 129, "CHNCLR", 6, 862000.0, 101030310.0, 1, NaN, NaN, "19-DEC-24", "D_MITCARD", "MIT Card Office",

### HR_ORG_UNIT

- 列：["HR_ORG_UNIT_KEY", "HR_ORG_UNIT_ID", "HR_ORG_UNIT_TITLE", "HR_ORG_UNIT_LEVEL", "HR_DEPARTMENT_ID", "HR_DEPARTMENT_CODE", "HR_DEPARTMENT_CODE_OLD", "HR_DEPARTMENT_NAME", "HR_DEPARTMENT_NAME_LONG", "HR_DEPARTMENT_NAME_ALPHA", "ORG_HIER_SCHOOL_AREA_NAME", "ORG_HIER_TOP_LEVEL_NAME", "ORG_HIER_ROOT_NAME", "HR_ORG_LEVEL1_ID", "HR_ORG_LEVEL1_SORT", "HR_ORG_LEVEL1_NAME", "HR_ORG_LEVEL2_ID", "HR_ORG_LEVEL2_SORT", "HR_ORG_LEVEL2_NAME", "HR_ORG_LEVEL3_ID", "HR_ORG_LEVEL3_SORT", "HR_ORG_LEVEL3_NAME", "HR_ORG_LEVEL4_ID", "HR_ORG_LEVEL4_SORT", "HR_ORG_LEVEL4_NAME", "HR_ORG_LEVEL5_ID", "HR_ORG_LEVEL5_SORT", "HR_ORG_LEVEL5_NAME", "HR_ORG_LEVEL6_ID", "HR_ORG_LEVEL6_SORT", "HR_ORG_LEVEL6_NAME", "HR_ORG_LEVEL7_ID", "HR_ORG_LEVEL7_SORT", "HR_ORG_LEVEL7_NAME", "DLC_KEY", "DLC_NAME", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE"]
- 示例：[["O10002409", 10002409, "LL-Facilities Services Department", "SUB DEPARTMENT", 10000581.0, "HR-310000", 310000.0, "Lincoln Laboratory", "Lincoln Laboratory", "Lincoln Laboratory", "Provost Area", "Provost Area", "MIT-All", 10000000.0, 1.0, "MIT-All", 10000001.0, 2.0, "Provost Area", 10000581.0, 121.0, "Lincoln Laboratory", 10002409.0, 261.0, "LL-Facilities Services Department", NaN, NaN, NaN, NaN

### FCLT_ORG_DLC_KEY

- 列：["FCLT_ORGANIZATION_KEY", "DLC_KEY"]
- 类型：["VARCHAR2", "VARCHAR2"]
- 示例：[[133, "D_CAC"], [254, NaN], [248, "D_MECHE"]]

## 子问题

["For rooms located on floor 2 with access level 1, show the building room, building component, floor, space usage, space unit code, access level, organization name, organization, department name, department code, and the minimum access level over each department code group, ordered by department code.", "For each department long name and department hierarchy level 3 name where the department hierarchy type is 'Standard Hierarchy' and the organization unit level is 'DEPARTMENTS', give the number of unique facility organization keys and the minimum organization unit ID.", "For rooms located on floor 2 with access level 1, show the building room, building component, floor, space usage, space unit code, access level, organization name, organization, department name, department code, and the minimum access level over each department code group, along with the department long name, department hierarchy level 3 name, the number of unique facility organization keys, and the minimum organization unit ID for departments where the department hierarchy type is 'Standard Hierarchy' and the organization unit level is 'DEPARTMENTS'. Order the results by department code and department hierarchy level 3 name."]
