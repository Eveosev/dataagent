# 查询任务（dw）

## 问题

For each school, list the school name, the variance and standard deviation (using STDDEV only and never STDDEV_POP) of CIP program codes among all degree-granting courses offered by departments in that school restricted to the Mathematics department (Course 18), as well as the average, range, and variance of the total units for degree-granting courses with non-null total units offered by the Mathematics department in that school. Additionally, for each school, include the number of unique Mathematics courses offered and the maximum total units among those courses. Present the results in the order of school name. Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_COURSE_DESCRIPTION", "SIS_DEPARTMENT", "SIS_SUBJECT_CODE", "CIS_COURSE_CATALOG"]

## 连接键

[["SIS_COURSE_DESCRIPTION.DEPARTMENT", "SIS_DEPARTMENT.DEPARTMENT_CODE"], ["SIS_DEPARTMENT.DEPARTMENT_CODE", "SIS_SUBJECT_CODE.DEPARTMENT_CODE"], ["SIS_COURSE_DESCRIPTION.COURSE", "SIS_SUBJECT_CODE.SUBJECT_CODE"], ["CIS_COURSE_CATALOG.SUBJECT_CODE", "SIS_SUBJECT_CODE.SUBJECT_CODE"]]

## 列映射

{"school": ["SIS_DEPARTMENT.SCHOOL_NAME", "SIS_COURSE_DESCRIPTION.SCHOOL_NAME"], "school name": ["SIS_DEPARTMENT.SCHOOL_NAME", "SIS_COURSE_DESCRIPTION.SCHOOL_NAME"], "variance of CIP program codes": ["SIS_COURSE_DESCRIPTION.CIP_PROGRAM_CODE"], "standard deviation of CIP program codes": ["SIS_COURSE_DESCRIPTION.CIP_PROGRAM_CODE"], "degree-granting courses": ["SIS_COURSE_DESCRIPTION.IS_DEGREE_GRANTING"], "departments in that school": ["SIS_DEPARTMENT.DEPARTMENT_CODE", "SIS_DEPARTMENT.SCHOOL_NAME"], "Mathematics department (Course 18)": ["SIS_DEPARTMENT.DEPARTMENT_CODE", "SIS_DEPARTMENT.DEPARTMENT_NAME"], "average of total units": ["CIS_COURSE_CATALOG.TOTAL_UNITS"], "range of total units": ["CIS_COURSE_CATALOG.TOTAL_UNITS"], "variance of total units": ["CIS_COURSE_CATALOG.TOTAL_UNITS"], "non-null total units": ["CIS_COURSE_CATALOG.TOTAL_UNITS"], "number of unique Mathematics courses": ["SIS_COURSE_DESCRIPTION.COURSE"], "maximum total units": ["CIS_COURSE_CATALOG.TOTAL_UNITS"]}

## 领域知识

["\"degree-granting\" is predicated by \"TABLE.IS_DEGREE_GRANTING = 'Y'\"", "\"math\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"Course 18\" is predicated by \"TABLE.DEPARTMENT_CODE = '18'\"", "\"Course 18\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\""]

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

["For each school, what is the variance and standard deviation of CIP program codes among all courses offered by departments in that school, restricted to the Mathematics department (Course 18) and only for degree-granting courses?", "For each school, provide the school name and calculate the average, range, and variance of the total units for courses offered by that school, considering only courses that are degree granting, have a non-null total units value, and are offered by the Mathematics department (Course 18).", "For each school, list the school name, the variance and standard deviation of CIP program codes among all degree-granting courses offered by departments in that school restricted to the Mathematics department (Course 18), as well as the average, range, and variance of the total units for degree-granting courses with non-null total units offered by the Mathematics department in that school. Present the results in the order of school name."]
