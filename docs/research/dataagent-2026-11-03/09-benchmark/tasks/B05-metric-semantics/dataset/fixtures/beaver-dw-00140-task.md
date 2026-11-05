# 查询任务（dw）

## 问题

List, for each department that grants degrees, is not the Mathematics department (Course 18), and has a maximum CIP program code among its courses greater than 120000, the department name, the maximum CIP program code among its courses, the full name of the department, and the school name, as well as, for each school that has a department named "Political Science", the school name, the standard deviation (using STDDEV only and never STDDEV_POP) of the department budget codes among its departments, the full name of the school, and the number of unique subject codes offered by departments in that school. Indicate for each row whether it is a "Department" or "School" result in the Source column. The columns should be: department name, maximum CIP program code, department full name, school name, standard deviation (using STDDEV only and never STDDEV_POP) of department budget codes, school full name, number of unique subject codes, and Source. Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_COURSE_DESCRIPTION", "SIS_DEPARTMENT", "SIS_SUBJECT_CODE"]

## 连接键

[["SIS_COURSE_DESCRIPTION.DEPARTMENT", "SIS_DEPARTMENT.DEPARTMENT_CODE"], ["SIS_DEPARTMENT.SCHOOL_CODE", "SIS_SUBJECT_CODE.SCHOOL_CODE"]]

## 列映射

{"department name": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "maximum CIP program code": ["SIS_COURSE_DESCRIPTION.CIP_PROGRAM_CODE"], "department full name": ["SIS_DEPARTMENT.DEPARTMENT_FULL_NAME"], "school name": ["SIS_DEPARTMENT.SCHOOL_NAME"], "standard deviation of department budget codes": ["SIS_DEPARTMENT.DEPT_BUDGET_CODE"], "school full name": ["SIS_DEPARTMENT.SCHOOL_NAME"], "number of unique subject codes": ["SIS_SUBJECT_CODE.SUBJECT_CODE"], "grants degrees": ["SIS_DEPARTMENT.IS_DEGREE_GRANTING"], "Mathematics department (Course 18)": ["SIS_DEPARTMENT.DEPARTMENT_CODE"], "Political Science": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "Source": []}

## 领域知识

["\"degree-granting\" is predicated by \"TABLE.IS_DEGREE_GRANTING = 'Y'\"", "\"Political Science\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Political Science'\"", "\"Mathematics\" is predicated by \"TABLE.DEPARTMENT_CODE = '18'\"", "\"Political Science\" is predicated by \"TABLE.DEPARTMENT = '17'\""]

## 表结构

### SIS_DEPARTMENT

- 列：["DEPARTMENT_CODE", "DEPARTMENT_NAME", "DEPARTMENT_FULL_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "DEPT_BUDGET_CODE", "IS_DEGREE_GRANTING", "DEPT_NAME_IN_COMMENCEMENT_BK", "SCHOOL_NAME_IN_COMMENCEMENT_BK", "DEPARTMENT_NAME_HISTORY", "DEPARTMENT_LAST_ACTIVITY_DATE", "DLC_KEY", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "VARCHAR2", "DATE"]
- 示例：[["HPM", "Health Policy & Management", "HPM-Health Policy & Management", "T", "Whitaker Coll of HST;  HST", 160000.0, "Y", NaN, "Whitaker College of Health Sciences and Technology", NaN, "17-FEB-94", "D_WHIT", "19-DEC-24"], ["NIE", "Non-Institute Exchange Student", "NIE-Non-Institute Exchange Student", "Z", "Non-MIT", NaN, "N", NaN, NaN, NaN, "12-JUL-95", "D_CROSS_REG", "19-DEC-24"], ["WHIT", "Whi

## 子问题

["For each department, what is the maximum CIP program code among its courses, and what is the full name of the department, for departments that grant degrees, have a maximum CIP program code greater than 120000, and are not the Mathematics department (Course 18)?", "For each school, what is the standard deviation of the department budget codes among its departments, what is the full name of the school, and only include schools that have a department named \"Political Science\"?", "For each department, what is the maximum CIP program code among its courses, the full name of the department, and the school name, for departments that grant degrees, have a maximum CIP program code greater than 120000, and are not the Mathematics department (Course 18)?", "For each school, what is the standard deviation of the department budget codes among its departments, what is the full name of the school, and how many unique subject codes are offered by departments in that school? Only include schools that have a department named \"Political Science\"."]
