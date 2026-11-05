# 查询任务（dw）

## 问题

For each DLC, what is the DLC key, DLC name, the number of unique organizations, and the total number of assignable organizations, considering only DLCs that have at least one assignable organization, whose DLC name contains the word 'Office', and that are not the biology department? Additionally, for each such DLC, what is the average organization level of its assignable organizations? Do not return any rounded answers.

## 库

dw

## 涉及表

["FCLT_ORG_DLC_KEY", "FCLT_ORGANIZATION"]

## 连接键

[["FCLT_ORGANIZATION.DLC_KEY", "FCLT_ORG_DLC_KEY.DLC_KEY"]]

## 列映射

{"DLC key": ["FCLT_ORG_DLC_KEY.DLC_KEY"], "DLC name": ["FCLT_ORGANIZATION.DLC_NAME"], "number of unique organizations": ["FCLT_ORGANIZATION.FCLT_ORGANIZATION_KEY"], "total number of assignable organizations": ["FCLT_ORGANIZATION.ASSIGNABLE"], "at least one assignable organization": ["FCLT_ORGANIZATION.ASSIGNABLE"], "DLC name contains the word 'Office'": ["FCLT_ORGANIZATION.DLC_NAME"], "not the biology department": ["FCLT_ORGANIZATION.DLC_NAME"], "average organization level of its assignable organizations": ["FCLT_ORGANIZATION.ORGANIZATION_LEVEL"]}

## 领域知识

["\"biology department\" is predicated by \"LOWER(TABLE.DLC_NAME) = LOWER('Biology')\"", "\"Departments, Laboratories, and Centers\" are abbreviated by \"DLCs\""]

## 子问题

["For each DLC, what is the DLC key, DLC name, the number of unique organizations, and the total number of assignable organizations, considering only DLCs that have at least one assignable organization, whose DLC name contains the word 'Office', and that are not the biology department?"]
