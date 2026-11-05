# 查询任务（dw）

## 问题

For each department, display the department's name, the range and variance of the total units for subjects offered by that department in the academic year 2022 and that are also listed in the CIS course catalog, as well as the range, variance, and standard deviation (using STDDEV only and never STDDEV_POP) of the total units for all courses offered by that department. Additionally, show the number of subjects in 2022 that have variable units and are listed in the CIS course catalog. Show the results ordered by the range of total units for subjects in 2022 in descending order. Do not return any rounded answers.

## 库

dw

## 涉及表

["COURSE_CATALOG_SUBJECT_OFFERED", "SIS_DEPARTMENT", "CIS_COURSE_CATALOG"]

## 连接键

[["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_CODE", "SIS_DEPARTMENT.DEPARTMENT_CODE"], ["CIS_COURSE_CATALOG.DEPARTMENT_CODE", "SIS_DEPARTMENT.DEPARTMENT_CODE"]]

## 列映射

{"department": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "department's name": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "range of the total units for subjects offered by that department in the academic year 2022 and that are also listed in the CIS course catalog": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS", "COURSE_CATALOG_SUBJECT_OFFERED.ACADEMIC_YEAR", "CIS_COURSE_CATALOG.DEPARTMENT_CODE"], "variance of the total units for subjects offered by that department in the academic year 2022 and that are also listed in the CIS course catalog": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS", "COURSE_CATALOG_SUBJECT_OFFERED.ACADEMIC_YEAR", "CIS_COURSE_CATALOG.DEPARTMENT_CODE"], "range of the total units for all courses offered by that department": ["CIS_COURSE_CATALOG.TOTAL_UNITS", "SIS_DEPARTMENT.DEPARTMENT_CODE"], "variance of the total units for all courses offered by that department": ["CIS_COURSE_CATALOG.TOTAL_UNITS", "SIS_DEPARTMENT.DEPARTMENT_CODE"], "standard deviation of the total units for all courses offered by that department": ["CIS_COURSE_CATALOG.TOTAL_UNITS", "SIS_DEPARTMENT.DEPARTMENT_CODE"], "number of subjects in 2022 that have variable units and are listed in the CIS course catalog": ["COURSE_CATALOG_SUBJECT_OFFERED.ACADEMIC_YEAR", "COURSE_CATALOG_SUBJECT_OFFERED.IS_VARIABLE_UNITS", "CIS_COURSE_CATALOG.DEPARTMENT_CODE"]}

## 领域知识

[]

## 表结构

### SIS_DEPARTMENT

- 列：["DEPARTMENT_CODE", "DEPARTMENT_NAME", "DEPARTMENT_FULL_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "DEPT_BUDGET_CODE", "IS_DEGREE_GRANTING", "DEPT_NAME_IN_COMMENCEMENT_BK", "SCHOOL_NAME_IN_COMMENCEMENT_BK", "DEPARTMENT_NAME_HISTORY", "DEPARTMENT_LAST_ACTIVITY_DATE", "DLC_KEY", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "VARCHAR2", "DATE"]
- 示例：[["HPM", "Health Policy & Management", "HPM-Health Policy & Management", "T", "Whitaker Coll of HST;  HST", 160000.0, "Y", NaN, "Whitaker College of Health Sciences and Technology", NaN, "17-FEB-94", "D_WHIT", "19-DEC-24"], ["NIE", "Non-Institute Exchange Student", "NIE-Non-Institute Exchange Student", "Z", "Non-MIT", NaN, "N", NaN, NaN, NaN, "12-JUL-95", "D_CROSS_REG", "19-DEC-24"], ["WHIT", "Whi

## 子问题

["For each department, provide the department's name and calculate the range and variance of the total units for subjects offered by that department in the academic year 2022 and that are also listed in the CIS course catalog.", "For each department, provide the department name and the range, variance, and standard deviation of the total units for courses offered by that department.", "For each department, display the department's name, the range and variance of the total units for subjects offered by that department in the academic year 2022 and that are also listed in the CIS course catalog, as well as the range, variance, and standard deviation of the total units for all courses offered by that department. Show the results ordered by the range of total units for subjects in 2022 in descending order."]
