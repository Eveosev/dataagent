# 查询任务（dw）

## 问题

For the Mathematics department (Course 18), provide the department name, the average, range, and variance of the total units for subjects offered by that department (considering only subjects with more than 0 enrolled students and total units greater than 0), and also include the standard deviation (using STDDEV only and never STDDEV_POP) of the total units for Mathematics, considering only departments that are degree granting, have offered more than 5 subjects, and are not the Chemistry department (Course 5). Additionally, for the Mathematics department, include the department's school name and department phone number. Present the results in the order of department name. Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_DEPARTMENT", "SUBJECT_OFFERED_SUMMARY", "MIT_STUDENT_DIRECTORY"]

## 连接键

[["SIS_DEPARTMENT.DEPARTMENT_CODE", "SUBJECT_OFFERED_SUMMARY.OFFER_DEPT_CODE"], ["MIT_STUDENT_DIRECTORY.DEPARTMENT", "SIS_DEPARTMENT.DEPARTMENT_CODE"]]

## 列映射

{"Mathematics department": ["SIS_DEPARTMENT.DEPARTMENT_NAME", "SIS_DEPARTMENT.DEPARTMENT_CODE"], "department name": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "average of the total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"], "range of the total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"], "variance of the total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"], "standard deviation of the total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"], "subjects offered": ["SUBJECT_OFFERED_SUMMARY.SUBJECT_ID"], "enrolled students": ["SUBJECT_OFFERED_SUMMARY.NUM_ENROLLED_STUDENTS"], "total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"], "degree granting": ["SIS_DEPARTMENT.IS_DEGREE_GRANTING"], "Chemistry department": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "school name": ["SIS_DEPARTMENT.SCHOOL_NAME"], "department phone number": ["SIS_ADMIN_DEPARTMENT.DEPARTMENT_PHONE_NUMBER"]}

## 领域知识

["\"math\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"Chemistry\" is predicated by \"TABLE.OFFER_DEPT_NAME = 'Chemistry'\"", "\"Course 18\" is predicated by \"TABLE.DEPARTMENT_CODE = '18'\"", "\"Course 5\" is predicated by \"TABLE.OFFER_DEPT_NAME = 'Chemistry'\""]

## 表结构

### SUBJECT_OFFERED_SUMMARY

- 列：["SUBJECT_OFFERED_SUMMARY_KEY", "COMPOSITE_SUBJECT_KEY", "TERM_CODE", "COURSE_NUMBER", "SUBJECT_ID", "SUBJECT_ID_SORT", "SUBJECT_TITLE", "MASTER_SUBJECT_ID", "MASTER_SUBJECT_ID_SORT", "CLUSTER_TYPE", "CLUSTER_TYPE_DESC", "CLUSTER_LIST", "HGN_CODE", "HGN_CODE_DESC", "OFFER_DEPT_CODE", "OFFER_DEPT_NAME", "OFFER_SCHOOL_NAME", "RESPONSIBLE_FACULTY_NAME", "RESPONSIBLE_FACULTY_MIT_ID", "TOTAL_UNITS", "LECTURE_UNITS", "LAB_UNITS", "PREPARATION_UNITS", "SUBJECT_ENROLLMENT_NUMBER", "CLUSTER_ENROLLMENT_NUMBER", "WAREHOUSE_LOAD_DATE", "NUM_ENROLLED_STUDENTS", "SUBJECT_GROUPING_KEY", "SUBJECT_SUMMARY_KEY"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "DATE", "NUMBER", "VARCHAR2", "VARCHAR2"]
- 示例：[["HAS.13162017FA", "HAS.00002017FA", "2017FA", "HAS", "HAS.1316", "HAS.1316", "The Bone Studio", "HAS.0000", "HAS.0000", "S", "SWE: School-Wide Electives", "HAS.0000, HAS.0100, HAS.1112, HAS.1212, HAS.1221, HAS.1300, HAS.1303, HAS.1304, HAS.1306, HAS.1307, HAS.1313, HAS.1314, HAS.131", "H", "Higher level graduate program", "NIH", "Harvard Cross-Enrollment Prog", "Non-MIT", NaN, NaN, 21.0, 0.0, 21

## 子问题

["For each department, give the department name and calculate the average, range, and variance of the total units for subjects offered by that department, considering only subjects with more than 0 enrolled students and total units greater than 0, and restrict the results to the Mathematics department (Course 18).", "For each department, what is the department name and the standard deviation of the total units of subjects offered by that department, considering only departments that have offered more than 5 subjects, are degree granting, and are not the Chemistry department (Course 5)?", "For the Mathematics department (Course 18), provide the department name, the average, range, and variance of the total units for subjects offered by that department (considering only subjects with more than 0 enrolled students and total units greater than 0), and also include the standard deviation of the total units for Mathematics, considering only departments that are degree granting, have offered more than 5 subjects, and are not the Chemistry department (Course 5). Present the results in the order of department name."]
