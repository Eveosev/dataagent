# 查询任务（dw）

## 问题

What is the minimum number of enrolled students in any subject offered and the total number of students enrolled, for subjects offered by departments that are degree granting, have at least one student in the MIT student directory, and are in the Mathematics department (Course 18)? Do not return any rounded answers.

## 库

dw

## 涉及表

["TIP_SUBJECT_OFFERED", "SIS_DEPARTMENT", "MIT_STUDENT_DIRECTORY"]

## 连接键

[["TIP_SUBJECT_OFFERED.OFFER_DEPT_CODE", "SIS_DEPARTMENT.DEPARTMENT_CODE"], ["SIS_DEPARTMENT.DEPARTMENT_CODE", "MIT_STUDENT_DIRECTORY.DEPARTMENT"]]

## 列映射

{"minimum number of enrolled students": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "total number of students enrolled": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "subjects offered": ["TIP_SUBJECT_OFFERED.OFFER_DEPT_CODE"], "departments that are degree granting": ["SIS_DEPARTMENT.IS_DEGREE_GRANTING"], "at least one student in the MIT student directory": ["MIT_STUDENT_DIRECTORY.DEPARTMENT"], "Mathematics department": ["SIS_DEPARTMENT.DEPARTMENT_CODE", "SIS_DEPARTMENT.DEPARTMENT_NAME"]}

## 领域知识

["\"math\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"Course 18\" is predicated by \"TABLE.DEPARTMENT_CODE = '18'\""]

## 表结构

### SIS_DEPARTMENT

- 列：["DEPARTMENT_CODE", "DEPARTMENT_NAME", "DEPARTMENT_FULL_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "DEPT_BUDGET_CODE", "IS_DEGREE_GRANTING", "DEPT_NAME_IN_COMMENCEMENT_BK", "SCHOOL_NAME_IN_COMMENCEMENT_BK", "DEPARTMENT_NAME_HISTORY", "DEPARTMENT_LAST_ACTIVITY_DATE", "DLC_KEY", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "VARCHAR2", "DATE"]
- 示例：[["HPM", "Health Policy & Management", "HPM-Health Policy & Management", "T", "Whitaker Coll of HST;  HST", 160000.0, "Y", NaN, "Whitaker College of Health Sciences and Technology", NaN, "17-FEB-94", "D_WHIT", "19-DEC-24"], ["NIE", "Non-Institute Exchange Student", "NIE-Non-Institute Exchange Student", "Z", "Non-MIT", NaN, "N", NaN, NaN, NaN, "12-JUL-95", "D_CROSS_REG", "19-DEC-24"], ["WHIT", "Whi

## 子问题

[]
