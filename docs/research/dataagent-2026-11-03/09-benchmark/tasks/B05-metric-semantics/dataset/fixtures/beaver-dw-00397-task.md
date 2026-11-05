# 查询任务（dw）

## 问题

For each department, give the department name and find the average and standard deviation (using STDDEV only and never STDDEV_POP) of the total units for subjects offered by that department in the School of Engineering during the Fall 2016 term, but exclude the departments of Chemistry and Biology. Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_COURSE_DESCRIPTION", "SIS_DEPARTMENT", "SUBJECT_OFFERED_SUMMARY"]

## 连接键

[["SIS_COURSE_DESCRIPTION.DEPARTMENT", "SIS_DEPARTMENT.DEPARTMENT_CODE"], ["SIS_DEPARTMENT.DEPARTMENT_CODE", "SUBJECT_OFFERED_SUMMARY.OFFER_DEPT_CODE"]]

## 列映射

{"department": ["SIS_COURSE_DESCRIPTION.DEPARTMENT_NAME"], "department name": ["SIS_COURSE_DESCRIPTION.DEPARTMENT_NAME"], "average of the total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"], "standard deviation of the total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"], "subjects offered by that department": ["SUBJECT_OFFERED_SUMMARY.OFFER_DEPT_CODE"], "School of Engineering": ["SUBJECT_OFFERED_SUMMARY.OFFER_SCHOOL_NAME"], "Fall 2016 term": ["SUBJECT_OFFERED_SUMMARY.TERM_CODE"], "departments of Chemistry and Biology": ["SIS_COURSE_DESCRIPTION.DEPARTMENT_NAME", "SIS_DEPARTMENT.DEPARTMENT_CODE"]}

## 领域知识

["\"biology and chemistry department\" is predicated by \"TABLE.OFFER_DEPT_NAME IN ('Chemistry', 'Biology')\"", "\"Chemistry\" is predicated by \"TABLE.DEPARTMENT_CODE = '5'\"", "\"Biology\" is predicated by \"TABLE.DEPARTMENT_CODE = '7'\""]

## 表结构

### SIS_DEPARTMENT

- 列：["DEPARTMENT_CODE", "DEPARTMENT_NAME", "DEPARTMENT_FULL_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "DEPT_BUDGET_CODE", "IS_DEGREE_GRANTING", "DEPT_NAME_IN_COMMENCEMENT_BK", "SCHOOL_NAME_IN_COMMENCEMENT_BK", "DEPARTMENT_NAME_HISTORY", "DEPARTMENT_LAST_ACTIVITY_DATE", "DLC_KEY", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "VARCHAR2", "DATE"]
- 示例：[["HPM", "Health Policy & Management", "HPM-Health Policy & Management", "T", "Whitaker Coll of HST;  HST", 160000.0, "Y", NaN, "Whitaker College of Health Sciences and Technology", NaN, "17-FEB-94", "D_WHIT", "19-DEC-24"], ["NIE", "Non-Institute Exchange Student", "NIE-Non-Institute Exchange Student", "Z", "Non-MIT", NaN, "N", NaN, NaN, NaN, "12-JUL-95", "D_CROSS_REG", "19-DEC-24"], ["WHIT", "Whi

## 子问题

[]
