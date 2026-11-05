# 查询任务（dw）

## 问题

List the top 10 departments by the number of subjects they offered, including the department name, the school name, and the subject code description, for departments that are degree granting, have offered at least one subject in the 'Engineering' school, and are not the 'Political Science' department (Course 17). Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_SUBJECT_CODE", "SIS_DEPARTMENT", "SUBJECT_OFFERED_SUMMARY"]

## 连接键

[["SIS_SUBJECT_CODE.DEPARTMENT_CODE", "SIS_DEPARTMENT.DEPARTMENT_CODE"], ["SIS_DEPARTMENT.DEPARTMENT_CODE", "SUBJECT_OFFERED_SUMMARY.OFFER_DEPT_CODE"]]

## 列映射

{"departments": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "number of subjects offered": ["SUBJECT_OFFERED_SUMMARY.SUBJECT_OFFERED_SUMMARY_KEY"], "department name": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "school name": ["SIS_DEPARTMENT.SCHOOL_NAME", "SUBJECT_OFFERED_SUMMARY.OFFER_SCHOOL_NAME"], "subject code description": ["SIS_SUBJECT_CODE.SUBJECT_CODE_DESC"], "degree granting": ["SIS_DEPARTMENT.IS_DEGREE_GRANTING"], "Engineering school": ["SUBJECT_OFFERED_SUMMARY.OFFER_SCHOOL_NAME"], "Political Science": ["SIS_DEPARTMENT.DEPARTMENT_NAME", "SIS_DEPARTMENT.DEPARTMENT_CODE"]}

## 领域知识

["\"Political Science\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Political Science'\"", "\"Course 17\" is predicated by \"TABLE.DEPARTMENT_CODE = '17'\""]

## 表结构

### SIS_DEPARTMENT

- 列：["DEPARTMENT_CODE", "DEPARTMENT_NAME", "DEPARTMENT_FULL_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "DEPT_BUDGET_CODE", "IS_DEGREE_GRANTING", "DEPT_NAME_IN_COMMENCEMENT_BK", "SCHOOL_NAME_IN_COMMENCEMENT_BK", "DEPARTMENT_NAME_HISTORY", "DEPARTMENT_LAST_ACTIVITY_DATE", "DLC_KEY", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "VARCHAR2", "DATE"]
- 示例：[["HPM", "Health Policy & Management", "HPM-Health Policy & Management", "T", "Whitaker Coll of HST;  HST", 160000.0, "Y", NaN, "Whitaker College of Health Sciences and Technology", NaN, "17-FEB-94", "D_WHIT", "19-DEC-24"], ["NIE", "Non-Institute Exchange Student", "NIE-Non-Institute Exchange Student", "Z", "Non-MIT", NaN, "N", NaN, NaN, NaN, "12-JUL-95", "D_CROSS_REG", "19-DEC-24"], ["WHIT", "Whi

## 子问题

[]
