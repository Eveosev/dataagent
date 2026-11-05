# 查询任务（dw）

## 问题

List, for each department, the department name and the coefficient of variation (using STDDEV only and never STDDEV_POP) of the total units for subjects offered by that department in the 2022 academic year (only for degree-granting departments and excluding the 'Political Science' department), and for each department and subject code where the department is degree granting and is Mathematics (Course 18), the department name, subject code, the number of subject codes, and the minimum department budget code. Show the department name, coefficient of variation (using STDDEV only and never STDDEV_POP), subject code, subject code count, and minimum department budget code, in that order. Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_SUBJECT_CODE", "SIS_DEPARTMENT", "COURSE_CATALOG_SUBJECT_OFFERED"]

## 连接键

[["SIS_DEPARTMENT.DEPARTMENT_CODE", "SIS_SUBJECT_CODE.DEPARTMENT_CODE"], ["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_CODE", "SIS_DEPARTMENT.DEPARTMENT_CODE"]]

## 列映射

{"department": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "department name": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "coefficient of variation": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS"], "total units": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS"], "subjects offered": ["COURSE_CATALOG_SUBJECT_OFFERED.SUBJECT_CODE"], "2022 academic year": ["COURSE_CATALOG_SUBJECT_OFFERED.ACADEMIC_YEAR"], "degree-granting departments": ["SIS_DEPARTMENT.IS_DEGREE_GRANTING"], "Political Science": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "subject code": ["SIS_SUBJECT_CODE.SUBJECT_CODE"], "Mathematics (Course 18)": ["SIS_DEPARTMENT.DEPARTMENT_NAME", "SIS_DEPARTMENT.DEPARTMENT_CODE"], "number of subject codes": ["SIS_SUBJECT_CODE.SUBJECT_CODE"], "minimum department budget code": ["SIS_DEPARTMENT.DEPT_BUDGET_CODE"]}

## 领域知识

["\"degree-granting\" is predicated by \"TABLE.IS_DEGREE_GRANTING = 'Y'\"", "\"math\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"Political Science\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Political Science'\"", "\"Course 18\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"Mathematics\" is predicated by \"TABLE.DEPARTMENT_CODE = '18'\""]

## 表结构

### SIS_DEPARTMENT

- 列：["DEPARTMENT_CODE", "DEPARTMENT_NAME", "DEPARTMENT_FULL_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "DEPT_BUDGET_CODE", "IS_DEGREE_GRANTING", "DEPT_NAME_IN_COMMENCEMENT_BK", "SCHOOL_NAME_IN_COMMENCEMENT_BK", "DEPARTMENT_NAME_HISTORY", "DEPARTMENT_LAST_ACTIVITY_DATE", "DLC_KEY", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "VARCHAR2", "DATE"]
- 示例：[["HPM", "Health Policy & Management", "HPM-Health Policy & Management", "T", "Whitaker Coll of HST;  HST", 160000.0, "Y", NaN, "Whitaker College of Health Sciences and Technology", NaN, "17-FEB-94", "D_WHIT", "19-DEC-24"], ["NIE", "Non-Institute Exchange Student", "NIE-Non-Institute Exchange Student", "Z", "Non-MIT", NaN, "N", NaN, NaN, NaN, "12-JUL-95", "D_CROSS_REG", "19-DEC-24"], ["WHIT", "Whi

## 子问题

["For each department, give the department name and the coefficient of variation of the total units for subjects offered by that department in the 2022 academic year, but only include departments that are degree-granting and exclude the 'Political Science' department.", "For each department and subject code where the department is degree granting and the department is Mathematics (Course 18), provide the number of subject codes and the minimum department budget code."]
