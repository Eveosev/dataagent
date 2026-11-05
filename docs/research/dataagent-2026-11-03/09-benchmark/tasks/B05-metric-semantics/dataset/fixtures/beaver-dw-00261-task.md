# 查询任务（dw）

## 问题

For organizations with an organization level of 5, show the organization name, organization ID, DLC name, HR org unit title, HR department name, HR org unit level, and assign row numbers within each HR department name group ordered by organization name. For each such organization, also show each room with area greater than 200 and assignable major use that belongs to the organization, including the building room, floor, room number, space ID, area, major use name, major use description, and the minimum area value over each major use group, ordered by HR department name, organization name, and major use. Do not return any rounded answers.

## 库

dw

## 涉及表

["FCLT_ORGANIZATION", "HR_ORG_UNIT", "FCLT_MAJOR_USE", "FCLT_ROOMS"]

## 连接键

[["FCLT_ORGANIZATION.DLC_KEY", "HR_ORG_UNIT.DLC_KEY"], ["FCLT_MAJOR_USE.FCLT_MAJOR_USE_KEY", "FCLT_ROOMS.FCLT_MAJOR_USE_KEY"]]

## 列映射

{"organization level of 5": ["FCLT_ORGANIZATION.ORGANIZATION_LEVEL"], "organization name": ["FCLT_ORGANIZATION.ORGANIZATION_NAME"], "organization ID": ["FCLT_ORGANIZATION.ORGANIZATION_ID"], "DLC name": ["HR_ORG_UNIT.DLC_NAME"], "HR org unit title": ["HR_ORG_UNIT.HR_ORG_UNIT_TITLE"], "HR department name": ["HR_ORG_UNIT.HR_DEPARTMENT_NAME"], "HR org unit level": ["HR_ORG_UNIT.HR_ORG_UNIT_LEVEL"], "room with area greater than 200": ["FCLT_ROOMS.AREA"], "assignable major use": ["FCLT_MAJOR_USE.ASSIGNABLE"], "building room": ["FCLT_ROOMS.BUILDING_ROOM"], "floor": ["FCLT_ROOMS.FLOOR"], "room number": ["FCLT_ROOMS.ROOM"], "space ID": ["FCLT_ROOMS.SPACE_ID"], "area": ["FCLT_ROOMS.AREA"], "major use name": ["FCLT_MAJOR_USE.MAJOR_USE"], "major use description": ["FCLT_MAJOR_USE.DESCRIPTION"], "minimum area value over each major use group": ["FCLT_ROOMS.AREA", "FCLT_MAJOR_USE.FCLT_MAJOR_USE_KEY"]}

## 领域知识

[]

## 表结构

### HR_ORG_UNIT

- 列：["HR_ORG_UNIT_KEY", "HR_ORG_UNIT_ID", "HR_ORG_UNIT_TITLE", "HR_ORG_UNIT_LEVEL", "HR_DEPARTMENT_ID", "HR_DEPARTMENT_CODE", "HR_DEPARTMENT_CODE_OLD", "HR_DEPARTMENT_NAME", "HR_DEPARTMENT_NAME_LONG", "HR_DEPARTMENT_NAME_ALPHA", "ORG_HIER_SCHOOL_AREA_NAME", "ORG_HIER_TOP_LEVEL_NAME", "ORG_HIER_ROOT_NAME", "HR_ORG_LEVEL1_ID", "HR_ORG_LEVEL1_SORT", "HR_ORG_LEVEL1_NAME", "HR_ORG_LEVEL2_ID", "HR_ORG_LEVEL2_SORT", "HR_ORG_LEVEL2_NAME", "HR_ORG_LEVEL3_ID", "HR_ORG_LEVEL3_SORT", "HR_ORG_LEVEL3_NAME", "HR_ORG_LEVEL4_ID", "HR_ORG_LEVEL4_SORT", "HR_ORG_LEVEL4_NAME", "HR_ORG_LEVEL5_ID", "HR_ORG_LEVEL5_SORT", "HR_ORG_LEVEL5_NAME", "HR_ORG_LEVEL6_ID", "HR_ORG_LEVEL6_SORT", "HR_ORG_LEVEL6_NAME", "HR_ORG_LEVEL7_ID", "HR_ORG_LEVEL7_SORT", "HR_ORG_LEVEL7_NAME", "DLC_KEY", "DLC_NAME", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE"]
- 示例：[["O10002409", 10002409, "LL-Facilities Services Department", "SUB DEPARTMENT", 10000581.0, "HR-310000", 310000.0, "Lincoln Laboratory", "Lincoln Laboratory", "Lincoln Laboratory", "Provost Area", "Provost Area", "MIT-All", 10000000.0, 1.0, "MIT-All", 10000001.0, 2.0, "Provost Area", 10000581.0, 121.0, "Lincoln Laboratory", 10002409.0, 261.0, "LL-Facilities Services Department", NaN, NaN, NaN, NaN

### FCLT_MAJOR_USE

- 列：["FCLT_MAJOR_USE_KEY", "MAJOR_USE", "DESCRIPTION", "ASSIGNABLE", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE"]
- 示例：[[101, "BLDG SRV", "BLDG SERVICE AREA", 0, "19-DEC-24"], [114, "ZUSE", "ZUSE ICR ONLY", 1, "19-DEC-24"], [103, "CLASSRMS", "CLASSROOMS", 1, "19-DEC-24"]]

## 子问题

["For organizations with an organization level of 5, show the organization name, organization ID, DLC name, HR org unit title, HR department name, HR org unit level, and assign row numbers within each HR department name group ordered by organization name.", "For each room with area greater than 200 and assignable major use, show the building room, floor, room number, space ID, area, major use name, major use description, and the minimum area value over each major use group, ordered by major use."]
