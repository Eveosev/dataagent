# 查询任务（dw）

## 问题

For each department where the average total units for subjects offered by that department (considering only subjects with more than 0 total units) is greater than the overall average total units across all subjects, provide the department name, subject ID, total units, the department's average total units (considering only subjects with more than 0 total units and at least 1 enrolled student), the department's standard deviation (using STDDEV only and never STDDEV_POP) of total units (for the same set), and the deviation of each subject's total units from the department's average. List the results ordered by the department's standard deviation (using STDDEV only and never STDDEV_POP) of total units (descending), then department name, then subject ID. Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_COURSE_DESCRIPTION", "SUBJECT_OFFERED_SUMMARY", "SIS_DEPARTMENT"]

## 连接键

[["SIS_COURSE_DESCRIPTION.COURSE", "SUBJECT_OFFERED_SUMMARY.COURSE_NUMBER"], ["SIS_DEPARTMENT.DEPARTMENT_CODE", "SUBJECT_OFFERED_SUMMARY.OFFER_DEPT_CODE"]]

## 列映射

{"department": ["SIS_COURSE_DESCRIPTION.DEPARTMENT_NAME", "SIS_DEPARTMENT.DEPARTMENT_CODE", "SUBJECT_OFFERED_SUMMARY.OFFER_DEPT_CODE"], "department name": ["SIS_COURSE_DESCRIPTION.DEPARTMENT_NAME", "SIS_DEPARTMENT.DEPARTMENT_NAME"], "subject ID": ["SUBJECT_OFFERED_SUMMARY.SUBJECT_ID"], "total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"], "average total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"], "subjects offered by that department": ["SUBJECT_OFFERED_SUMMARY.OFFER_DEPT_CODE", "SIS_DEPARTMENT.DEPARTMENT_CODE"], "subjects with more than 0 total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"], "overall average total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"], "at least 1 enrolled student": ["SUBJECT_OFFERED_SUMMARY.NUM_ENROLLED_STUDENTS"], "department's average total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"], "department's standard deviation of total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"], "deviation of each subject's total units from the department's average": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"]}

## 领域知识

[]

## 表结构

### SUBJECT_OFFERED_SUMMARY

- 列：["SUBJECT_OFFERED_SUMMARY_KEY", "COMPOSITE_SUBJECT_KEY", "TERM_CODE", "COURSE_NUMBER", "SUBJECT_ID", "SUBJECT_ID_SORT", "SUBJECT_TITLE", "MASTER_SUBJECT_ID", "MASTER_SUBJECT_ID_SORT", "CLUSTER_TYPE", "CLUSTER_TYPE_DESC", "CLUSTER_LIST", "HGN_CODE", "HGN_CODE_DESC", "OFFER_DEPT_CODE", "OFFER_DEPT_NAME", "OFFER_SCHOOL_NAME", "RESPONSIBLE_FACULTY_NAME", "RESPONSIBLE_FACULTY_MIT_ID", "TOTAL_UNITS", "LECTURE_UNITS", "LAB_UNITS", "PREPARATION_UNITS", "SUBJECT_ENROLLMENT_NUMBER", "CLUSTER_ENROLLMENT_NUMBER", "WAREHOUSE_LOAD_DATE", "NUM_ENROLLED_STUDENTS", "SUBJECT_GROUPING_KEY", "SUBJECT_SUMMARY_KEY"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "DATE", "NUMBER", "VARCHAR2", "VARCHAR2"]
- 示例：[["HAS.13162017FA", "HAS.00002017FA", "2017FA", "HAS", "HAS.1316", "HAS.1316", "The Bone Studio", "HAS.0000", "HAS.0000", "S", "SWE: School-Wide Electives", "HAS.0000, HAS.0100, HAS.1112, HAS.1212, HAS.1221, HAS.1300, HAS.1303, HAS.1304, HAS.1306, HAS.1307, HAS.1313, HAS.1314, HAS.131", "H", "Higher level graduate program", "NIH", "Harvard Cross-Enrollment Prog", "Non-MIT", NaN, NaN, 21.0, 0.0, 21

## 子问题

["For each department, provide the department name and calculate the average and standard deviation of the total units for subjects offered by that department, considering only subjects with more than 0 total units.", "For each department, provide the department name and calculate the average and standard deviation of the total units for subjects offered by that department, considering only subjects with more than 0 total units and at least 1 enrolled student.", "For each department, provide the department name, average, and standard deviation of the total units for subjects offered by that department (considering only subjects with more than 0 total units), but only include departments where the average total units is greater than the overall average total units across all subjects.", "For each department, provide the department name, the average and standard deviation of the total units for subjects offered by that department (considering only subjects with more than 0 total units and at least 1 enrolled student), and show the deviation of each subject's total units from the department's average."]
