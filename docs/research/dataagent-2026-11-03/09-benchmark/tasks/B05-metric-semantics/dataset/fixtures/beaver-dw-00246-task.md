# 查询任务（dw）

## 问题

For each subject that appears both among subjects offered in the term '2017FA' (for which the range, variance, and standard deviation (using STDDEV only and never STDDEV_POP) of the record counts of tip materials are calculated) and among subjects offered in the term '2016SP' with a school code of 'E' (for which the department name, course description, and a row number within a window of 2 preceding and 1 following rows ordered by subject title are assigned), give the subject title, the range of record counts, the variance of record counts, the standard deviation (using STDDEV only and never STDDEV_POP) of record counts, the department name, the course description, and the window row number, in that order. Do not return any rounded answers.

## 库

dw

## 涉及表

["TIP_DETAIL", "SUBJECT_OFFERED_SUMMARY", "SIS_SUBJECT_CODE", "SIS_COURSE_DESCRIPTION"]

## 连接键

[["SUBJECT_OFFERED_SUMMARY.TERM_CODE", "TIP_DETAIL.TERM_CODE"], ["SIS_COURSE_DESCRIPTION.COURSE", "SIS_SUBJECT_CODE.COURSE_NUMBER"], ["SIS_COURSE_DESCRIPTION.COURSE", "SUBJECT_OFFERED_SUMMARY.COURSE_NUMBER"]]

## 列映射

{"subject": ["SUBJECT_OFFERED_SUMMARY.SUBJECT_TITLE"], "subjects offered in the term '2017FA'": ["SUBJECT_OFFERED_SUMMARY.TERM_CODE"], "record counts of tip materials": ["TIP_DETAIL.RECORD_COUNT"], "range of record counts": ["TIP_DETAIL.RECORD_COUNT"], "variance of record counts": ["TIP_DETAIL.RECORD_COUNT"], "standard deviation of record counts": ["TIP_DETAIL.RECORD_COUNT"], "subjects offered in the term '2016SP'": ["SUBJECT_OFFERED_SUMMARY.TERM_CODE"], "school code of 'E'": ["SIS_SUBJECT_CODE.SCHOOL_CODE"], "department name": ["SIS_COURSE_DESCRIPTION.DEPARTMENT_NAME"], "course description": ["SIS_COURSE_DESCRIPTION.COURSE_DESCRIPTION"], "row number within a window": [], "subject title": ["SUBJECT_OFFERED_SUMMARY.SUBJECT_TITLE"]}

## 领域知识

[]

## 表结构

### SUBJECT_OFFERED_SUMMARY

- 列：["SUBJECT_OFFERED_SUMMARY_KEY", "COMPOSITE_SUBJECT_KEY", "TERM_CODE", "COURSE_NUMBER", "SUBJECT_ID", "SUBJECT_ID_SORT", "SUBJECT_TITLE", "MASTER_SUBJECT_ID", "MASTER_SUBJECT_ID_SORT", "CLUSTER_TYPE", "CLUSTER_TYPE_DESC", "CLUSTER_LIST", "HGN_CODE", "HGN_CODE_DESC", "OFFER_DEPT_CODE", "OFFER_DEPT_NAME", "OFFER_SCHOOL_NAME", "RESPONSIBLE_FACULTY_NAME", "RESPONSIBLE_FACULTY_MIT_ID", "TOTAL_UNITS", "LECTURE_UNITS", "LAB_UNITS", "PREPARATION_UNITS", "SUBJECT_ENROLLMENT_NUMBER", "CLUSTER_ENROLLMENT_NUMBER", "WAREHOUSE_LOAD_DATE", "NUM_ENROLLED_STUDENTS", "SUBJECT_GROUPING_KEY", "SUBJECT_SUMMARY_KEY"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "DATE", "NUMBER", "VARCHAR2", "VARCHAR2"]
- 示例：[["HAS.13162017FA", "HAS.00002017FA", "2017FA", "HAS", "HAS.1316", "HAS.1316", "The Bone Studio", "HAS.0000", "HAS.0000", "S", "SWE: School-Wide Electives", "HAS.0000, HAS.0100, HAS.1112, HAS.1212, HAS.1221, HAS.1300, HAS.1303, HAS.1304, HAS.1306, HAS.1307, HAS.1313, HAS.1314, HAS.131", "H", "Higher level graduate program", "NIH", "Harvard Cross-Enrollment Prog", "Non-MIT", NaN, NaN, 21.0, 0.0, 21

### SIS_SUBJECT_CODE

- 列：["COURSE_NUMBER", "SUBJECT_CODE", "SUBJECT_CODE_DESC", "DEPARTMENT_CODE", "DEPARTMENT_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE"]
- 示例：[["S0", "S0", NaN, NaN, NaN, NaN, NaN, "19-DEC-24"], ["OGE", "OGE", "Office of Graduate Education", "OGE", "Office of Graduate Education", "Y", "MIT, academic", "19-DEC-24"], ["MCH", "MCH", "Photography", "NIA", "Non-Institute-MFA/MCA", "Z", "Non-MIT", "19-DEC-24"]]

## 子问题

["For each subject, give the subject title and the range, variance, and standard deviation of the record counts of tip materials for that subject, considering only subjects offered in the term '2017FA'.", "For subjects offered in the term '2016SP' with a school code of 'E', show the subject title, department name, and course description, and assign row numbers within a window of 2 preceding and 1 following rows ordered by subject title."]
