# 查询任务（dw）

## 问题

For the Mathematics department, what is the department name, the range, variance, and standard deviation (using STDDEV only and never STDDEV_POP) of the number of unique subject codes per course offered by that department (considering only degree-granting courses in Mathematics), as well as the variance and standard deviation (using STDDEV only and never STDDEV_POP) of the number of students in each student year for that department (considering only departments that are degree granting and are not the Biology department)? List the department name, subject code count range, subject code count variance, subject code count standard deviation (using STDDEV only and never STDDEV_POP), variance of number of students per student year, and standard deviation (using STDDEV only and never STDDEV_POP) of number of students per student year, in that order. Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_COURSE_DESCRIPTION", "SIS_DEPARTMENT", "SIS_SUBJECT_CODE", "MIT_STUDENT_DIRECTORY"]

## 连接键

[["SIS_COURSE_DESCRIPTION.DEPARTMENT", "SIS_DEPARTMENT.DEPARTMENT_CODE"], ["SIS_DEPARTMENT.DEPARTMENT_CODE", "SIS_SUBJECT_CODE.DEPARTMENT_CODE"], ["MIT_STUDENT_DIRECTORY.DEPARTMENT", "SIS_DEPARTMENT.DEPARTMENT_CODE"]]

## 列映射

{"Mathematics department": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "department name": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "subject code count range": ["SIS_SUBJECT_CODE.SUBJECT_CODE", "SIS_COURSE_DESCRIPTION.COURSE", "SIS_COURSE_DESCRIPTION.DEPARTMENT"], "subject code count variance": ["SIS_SUBJECT_CODE.SUBJECT_CODE", "SIS_COURSE_DESCRIPTION.COURSE", "SIS_COURSE_DESCRIPTION.DEPARTMENT"], "subject code count standard deviation": ["SIS_SUBJECT_CODE.SUBJECT_CODE", "SIS_COURSE_DESCRIPTION.COURSE", "SIS_COURSE_DESCRIPTION.DEPARTMENT"], "degree-granting courses": ["SIS_COURSE_DESCRIPTION.IS_DEGREE_GRANTING"], "variance of number of students per student year": ["MIT_STUDENT_DIRECTORY.STUDENT_YEAR", "SIS_DEPARTMENT.DEPARTMENT_NAME"], "standard deviation of number of students per student year": ["MIT_STUDENT_DIRECTORY.STUDENT_YEAR", "SIS_DEPARTMENT.DEPARTMENT_NAME"], "departments that are degree granting": ["SIS_DEPARTMENT.IS_DEGREE_GRANTING"], "not the Biology department": ["SIS_DEPARTMENT.DEPARTMENT_NAME"]}

## 领域知识

["\"degree-granting courses\" is predicated by \"TABLE.IS_DEGREE_GRANTING = 'Y'\"", "\"degree-granting\" is predicated by \"TABLE.IS_DEGREE_GRANTING = 'Y'\"", "\"Mathematics\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"Biology\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Biology'\""]

## 表结构

### SIS_DEPARTMENT

- 列：["DEPARTMENT_CODE", "DEPARTMENT_NAME", "DEPARTMENT_FULL_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "DEPT_BUDGET_CODE", "IS_DEGREE_GRANTING", "DEPT_NAME_IN_COMMENCEMENT_BK", "SCHOOL_NAME_IN_COMMENCEMENT_BK", "DEPARTMENT_NAME_HISTORY", "DEPARTMENT_LAST_ACTIVITY_DATE", "DLC_KEY", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "VARCHAR2", "DATE"]
- 示例：[["HPM", "Health Policy & Management", "HPM-Health Policy & Management", "T", "Whitaker Coll of HST;  HST", 160000.0, "Y", NaN, "Whitaker College of Health Sciences and Technology", NaN, "17-FEB-94", "D_WHIT", "19-DEC-24"], ["NIE", "Non-Institute Exchange Student", "NIE-Non-Institute Exchange Student", "Z", "Non-MIT", NaN, "N", NaN, NaN, NaN, "12-JUL-95", "D_CROSS_REG", "19-DEC-24"], ["WHIT", "Whi

### SIS_SUBJECT_CODE

- 列：["COURSE_NUMBER", "SUBJECT_CODE", "SUBJECT_CODE_DESC", "DEPARTMENT_CODE", "DEPARTMENT_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE"]
- 示例：[["S0", "S0", NaN, NaN, NaN, NaN, NaN, "19-DEC-24"], ["OGE", "OGE", "Office of Graduate Education", "OGE", "Office of Graduate Education", "Y", "MIT, academic", "19-DEC-24"], ["MCH", "MCH", "Photography", "NIA", "Non-Institute-MFA/MCA", "Z", "Non-MIT", "19-DEC-24"]]

## 子问题

["For each department, what is the department name, and what are the range, variance, and standard deviation of the number of unique subject codes per course offered by that department, considering only degree-granting courses in the Mathematics department?", "For each department, what is the department name and both the variance and standard deviation of the number of students in each student year for that department, considering only departments that are degree granting and are not the Biology department?"]
