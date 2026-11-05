# 查询任务（dw）

## 问题

For each school, what is the variance and standard deviation (using STDDEV only and never STDDEV_POP) of CIP program codes among all degree-granting courses offered by departments in that school, restricted to the Mathematics department (Course 18), and for each department name and school name where the department is degree granting and the department is Mathematics, what is the number of unique courses and the minimum CIP program code from the course descriptions? Additionally, for each such school, what is the total number of subject codes associated with the Mathematics department? Please provide the school name, variance of CIP program code, standard deviation (using STDDEV only and never STDDEV_POP) of CIP program code, department name, number of unique courses, minimum CIP program code, and the total number of subject codes, in that order. Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_COURSE_DESCRIPTION", "SIS_DEPARTMENT", "SIS_SUBJECT_CODE"]

## 连接键

[["SIS_COURSE_DESCRIPTION.DEPARTMENT", "SIS_DEPARTMENT.DEPARTMENT_CODE"], ["SIS_DEPARTMENT.DEPARTMENT_CODE", "SIS_SUBJECT_CODE.DEPARTMENT_CODE"]]

## 列映射

{"school": ["SIS_DEPARTMENT.SCHOOL_NAME"], "variance of CIP program codes": ["SIS_COURSE_DESCRIPTION.CIP_PROGRAM_CODE"], "standard deviation of CIP program codes": ["SIS_COURSE_DESCRIPTION.CIP_PROGRAM_CODE"], "degree-granting courses": ["SIS_COURSE_DESCRIPTION.IS_DEGREE_GRANTING"], "departments": ["SIS_DEPARTMENT.DEPARTMENT_CODE", "SIS_DEPARTMENT.DEPARTMENT_NAME"], "Mathematics department (Course 18)": ["SIS_DEPARTMENT.DEPARTMENT_CODE", "SIS_DEPARTMENT.DEPARTMENT_NAME"], "department name": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "school name": ["SIS_DEPARTMENT.SCHOOL_NAME"], "number of unique courses": ["SIS_COURSE_DESCRIPTION.COURSE"], "minimum CIP program code": ["SIS_COURSE_DESCRIPTION.CIP_PROGRAM_CODE"], "course descriptions": ["SIS_COURSE_DESCRIPTION.CIP_PROGRAM_CODE", "SIS_COURSE_DESCRIPTION.COURSE"], "subject codes": ["SIS_SUBJECT_CODE.SUBJECT_CODE"], "total number of subject codes": ["SIS_SUBJECT_CODE.SUBJECT_CODE"]}

## 领域知识

["\"degree-granting\" is predicated by \"TABLE.IS_DEGREE_GRANTING = 'Y'\"", "\"math\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"Course 18\" is predicated by \"TABLE.DEPARTMENT_CODE = '18'\"", "\"Course 18\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\""]

## 表结构

### SIS_DEPARTMENT

- 列：["DEPARTMENT_CODE", "DEPARTMENT_NAME", "DEPARTMENT_FULL_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "DEPT_BUDGET_CODE", "IS_DEGREE_GRANTING", "DEPT_NAME_IN_COMMENCEMENT_BK", "SCHOOL_NAME_IN_COMMENCEMENT_BK", "DEPARTMENT_NAME_HISTORY", "DEPARTMENT_LAST_ACTIVITY_DATE", "DLC_KEY", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "VARCHAR2", "DATE"]
- 示例：[["HPM", "Health Policy & Management", "HPM-Health Policy & Management", "T", "Whitaker Coll of HST;  HST", 160000.0, "Y", NaN, "Whitaker College of Health Sciences and Technology", NaN, "17-FEB-94", "D_WHIT", "19-DEC-24"], ["NIE", "Non-Institute Exchange Student", "NIE-Non-Institute Exchange Student", "Z", "Non-MIT", NaN, "N", NaN, NaN, NaN, "12-JUL-95", "D_CROSS_REG", "19-DEC-24"], ["WHIT", "Whi

## 子问题

["For each school, what is the variance and standard deviation of CIP program codes among all courses offered by departments in that school, restricted to the Mathematics department (Course 18) and only for degree-granting courses?", "For each department name and school name, where the department is degree granting and the department is Mathematics (Course 18), provide the number of unique courses and the minimum CIP program code from the course descriptions.", "For each school, what is the variance and standard deviation of CIP program codes among all degree-granting courses offered by departments in that school, restricted to the Mathematics department (Course 18), and for each department name and school name where the department is degree granting and the department is Mathematics, what is the number of unique courses and the minimum CIP program code from the course descriptions? Please provide the school name, variance of CIP program code, standard deviation of CIP program code, department name, number of unique courses, and minimum CIP program code, in that order."]
