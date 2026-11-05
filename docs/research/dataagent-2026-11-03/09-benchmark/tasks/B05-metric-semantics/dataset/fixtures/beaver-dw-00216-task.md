# 查询任务（dw）

## 问题

For each organization, show the organization name, the number of associated space units, and whether the organization is a 'LARGE_HOLDER' (at least 20% more space units than the average), 'SMALL_HOLDER' (at least 20% fewer space units than the average), or 'AVERAGE_HOLDER' otherwise. Do not return any rounded answers.

## 库

dw

## 涉及表

["FCLT_ORG_DLC_KEY", "FCLT_ORGANIZATION", "SPACE_UNIT"]

## 连接键

[["FCLT_ORGANIZATION.DLC_KEY", "FCLT_ORG_DLC_KEY.DLC_KEY"], ["FCLT_ORGANIZATION.DLC_KEY", "SPACE_UNIT.DLC_KEY"]]

## 列映射

{"organization": ["FCLT_ORGANIZATION.ORGANIZATION_NAME"], "organization name": ["FCLT_ORGANIZATION.ORGANIZATION_NAME"], "number of associated space units": ["SPACE_UNIT.SPACE_UNIT_KEY"], "space units": ["SPACE_UNIT.SPACE_UNIT_KEY"]}

## 领域知识

[]

## 表结构

### FCLT_ORGANIZATION

- 列：["FCLT_ORGANIZATION_KEY", "ORGANIZATION_ID", "ORGANIZATION", "ORGANIZATION_NAME", "FCLT_ORG_PARENT_KEY", "ORG_PARENT", "FCLT_MAJOR_ORG_KEY", "MAJOR_ORG", "ORGANIZATION_LEVEL", "ORGANIZATION_NUMBER", "ORGANIZATION_SORT", "ASSIGNABLE", "COURSE", "DESCRIPTION", "WAREHOUSE_LOAD_DATE", "DLC_KEY", "DLC_NAME", "HR_DEPARTMENT_CODE_OLD", "HR_ORG_UNIT_ID", "HR_DEPARTMENT_NAME"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2"]
- 示例：[[188, 188, "LI&PHL", "LING & PHIL", 244.0, "S H&SS", 230, "PROVST", 5, 94000.0, 101060147.0, 1, "24", "Department of Linguistics and Philosophy", "19-DEC-24", "D_L&P", "Linguistics & Philosophy", 94000.0, 10000367.0, "Linguistics & Philosophy"], [121, 121, "CARDSV", "CARD SERVICES", 160.0, "ENTSVC", 129, "CHNCLR", 6, 862000.0, 101030310.0, 1, NaN, NaN, "19-DEC-24", "D_MITCARD", "MIT Card Office",

## 子问题

["List the top 10 organizations by the number of associated space units, showing the organization name and the count of space units for each."]
