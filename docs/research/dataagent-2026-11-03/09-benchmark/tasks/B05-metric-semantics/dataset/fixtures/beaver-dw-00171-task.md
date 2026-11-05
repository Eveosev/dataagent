# 查询任务（dw）

## 问题

For the Physics department (Course 8), what is the department's full name, the range and variance of CIP program codes among its degree-granting courses, and the range and variance of the department budget codes for all subject codes associated with the department? List the department's full name, CIP code range, CIP code variance, budget code range, and budget code variance in that order. Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_COURSE_DESCRIPTION", "SIS_DEPARTMENT", "SIS_ADMIN_DEPARTMENT", "SIS_SUBJECT_CODE"]

## 连接键

[["SIS_COURSE_DESCRIPTION.DEPARTMENT", "SIS_DEPARTMENT.DEPARTMENT_CODE"], ["SIS_ADMIN_DEPARTMENT.SIS_ADMIN_DEPARTMENT_CODE", "SIS_DEPARTMENT.DEPARTMENT_CODE"], ["SIS_DEPARTMENT.DEPARTMENT_CODE", "SIS_SUBJECT_CODE.DEPARTMENT_CODE"]]

## 列映射

{"Physics department (Course 8)": ["SIS_DEPARTMENT.DEPARTMENT_CODE"], "department's full name": ["SIS_DEPARTMENT.DEPARTMENT_FULL_NAME"], "CIP program codes": ["SIS_COURSE_DESCRIPTION.CIP_PROGRAM_CODE"], "degree-granting courses": ["SIS_COURSE_DESCRIPTION.IS_DEGREE_GRANTING"], "department budget codes": ["SIS_DEPARTMENT.DEPT_BUDGET_CODE"], "subject codes": ["SIS_SUBJECT_CODE.DEPARTMENT_CODE"]}

## 领域知识

["\"degree-granting\" is predicated by \"TABLE.IS_DEGREE_GRANTING = 'Y'\"", "\"Mathematics\" is predicated by \"TABLE.DEPARTMENT_CODE = '18'\""]

## 表结构

### SIS_DEPARTMENT

- 列：["DEPARTMENT_CODE", "DEPARTMENT_NAME", "DEPARTMENT_FULL_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "DEPT_BUDGET_CODE", "IS_DEGREE_GRANTING", "DEPT_NAME_IN_COMMENCEMENT_BK", "SCHOOL_NAME_IN_COMMENCEMENT_BK", "DEPARTMENT_NAME_HISTORY", "DEPARTMENT_LAST_ACTIVITY_DATE", "DLC_KEY", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "VARCHAR2", "DATE"]
- 示例：[["HPM", "Health Policy & Management", "HPM-Health Policy & Management", "T", "Whitaker Coll of HST;  HST", 160000.0, "Y", NaN, "Whitaker College of Health Sciences and Technology", NaN, "17-FEB-94", "D_WHIT", "19-DEC-24"], ["NIE", "Non-Institute Exchange Student", "NIE-Non-Institute Exchange Student", "Z", "Non-MIT", NaN, "N", NaN, NaN, NaN, "12-JUL-95", "D_CROSS_REG", "19-DEC-24"], ["WHIT", "Whi

### SIS_ADMIN_DEPARTMENT

- 列：["SIS_ADMIN_DEPARTMENT_CODE", "SIS_ADMIN_DEPARTMENT_NAME", "DEPARTMENT_PHONE_AREA_CODE", "DEPARTMENT_PHONE_NUMBER", "CLEARING_COST_COLLECTOR", "LAST_ACTIVITY_DATE", "WAREHOUSE_LOAD_DATE"]
- 类型：["DATE", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE"]
- 示例：[["19-DEC-24", "OLS", "Purchasing and Stores", NaN, NaN, NaN, "10-MAR-94"], ["19-DEC-24", "UEO", "Undergraduate Education Office", NaN, NaN, NaN, "05-NOV-91"], ["19-DEC-24", "AS", "Air Science", NaN, NaN, NaN, "03-NOV-92"]]

## 子问题

["For each department, what is the department's full name, and what are the range and variance of CIP program codes among its courses, considering only degree-granting courses in the Mathematics department (Course 18)?", "For each department, provide the department's full name and calculate the range and variance of the department budget codes for all subject codes associated with that department, considering only departments that grant degrees, and restrict the results to the Mathematics department (Course 18).", "For the Mathematics department (Course 18), what is the department's full name, the range and variance of CIP program codes among its degree-granting courses, and the range and variance of the department budget codes for all subject codes associated with the department? List the department's full name, CIP code range, CIP code variance, budget code range, and budget code variance in that order."]
