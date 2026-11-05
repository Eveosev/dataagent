# 查询任务（dw）

## 问题

For each department where the total number of organizations associated with that department whose parent is 'EXECVP' or 'CHNCLR' is greater than 5, give the department name, the total number of organizations, the DLC name, the average organization number, the standard deviation (using STDDEV only and never STDDEV_POP) of the organization numbers for assignable organizations associated with that DLC, and the HR organization unit title, ordering the results by the total number of organizations in descending order and then by the standard deviation (using STDDEV only and never STDDEV_POP) of the organization numbers in descending order. Do not return any rounded answers.

## 库

dw

## 涉及表

["FCLT_ORG_DLC_KEY", "FCLT_ORGANIZATION", "HR_ORG_UNIT"]

## 连接键

[["FCLT_ORGANIZATION.DLC_KEY", "FCLT_ORG_DLC_KEY.DLC_KEY"], ["FCLT_ORGANIZATION.DLC_KEY", "HR_ORG_UNIT.DLC_KEY"], ["FCLT_ORGANIZATION.FCLT_ORGANIZATION_KEY", "FCLT_ORG_DLC_KEY.FCLT_ORGANIZATION_KEY"]]

## 列映射

{"department": ["HR_ORG_UNIT.HR_DEPARTMENT_NAME"], "total number of organizations": ["FCLT_ORGANIZATION.FCLT_ORGANIZATION_KEY"], "organizations associated with that department": ["FCLT_ORGANIZATION.FCLT_ORGANIZATION_KEY", "HR_ORG_UNIT.HR_DEPARTMENT_NAME"], "parent is 'EXECVP' or 'CHNCLR'": ["FCLT_ORGANIZATION.ORG_PARENT"], "department name": ["HR_ORG_UNIT.HR_DEPARTMENT_NAME"], "DLC name": ["FCLT_ORGANIZATION.DLC_NAME"], "average organization number": ["FCLT_ORGANIZATION.ORGANIZATION_NUMBER"], "standard deviation of the organization numbers": ["FCLT_ORGANIZATION.ORGANIZATION_NUMBER"], "assignable organizations": ["FCLT_ORGANIZATION.ASSIGNABLE"], "HR organization unit title": ["HR_ORG_UNIT.HR_ORG_UNIT_TITLE"]}

## 领域知识

[]

## 表结构

### FCLT_ORGANIZATION

- 列：["FCLT_ORGANIZATION_KEY", "ORGANIZATION_ID", "ORGANIZATION", "ORGANIZATION_NAME", "FCLT_ORG_PARENT_KEY", "ORG_PARENT", "FCLT_MAJOR_ORG_KEY", "MAJOR_ORG", "ORGANIZATION_LEVEL", "ORGANIZATION_NUMBER", "ORGANIZATION_SORT", "ASSIGNABLE", "COURSE", "DESCRIPTION", "WAREHOUSE_LOAD_DATE", "DLC_KEY", "DLC_NAME", "HR_DEPARTMENT_CODE_OLD", "HR_ORG_UNIT_ID", "HR_DEPARTMENT_NAME"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2"]
- 示例：[[188, 188, "LI&PHL", "LING & PHIL", 244.0, "S H&SS", 230, "PROVST", 5, 94000.0, 101060147.0, 1, "24", "Department of Linguistics and Philosophy", "19-DEC-24", "D_L&P", "Linguistics & Philosophy", 94000.0, 10000367.0, "Linguistics & Philosophy"], [121, 121, "CARDSV", "CARD SERVICES", 160.0, "ENTSVC", 129, "CHNCLR", 6, 862000.0, 101030310.0, 1, NaN, NaN, "19-DEC-24", "D_MITCARD", "MIT Card Office",

## 子问题

["For each department, give the department name and calculate the total number of organizations associated with that department for organizations whose parent is 'EXECVP' or 'CHNCLR', with the total number of organizations greater than 5.", "For each DLC, provide the DLC name and calculate the average and standard deviation of the organization numbers for organizations associated with that DLC, considering only organizations that are assignable.", "For each department where the total number of organizations associated with that department whose parent is 'EXECVP' or 'CHNCLR' is greater than 5, give the department name, the total number of organizations, the DLC name, the average organization number, and the standard deviation of the organization numbers for assignable organizations associated with that DLC, ordering the results by the total number of organizations in descending order and then by the standard deviation of the organization numbers in descending order."]
