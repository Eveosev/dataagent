# 查询任务（dw）

## 问题

List, for each department, the department code, department name, average total units, range of total units, variance of total units, minimum number of enrolled students, average department budget code, and the reason for inclusion ('UnitsStats' for departments that are degree granting, not Chemistry or Biology, and have subjects with more than zero enrolled students, and 'MathStats' for Mathematics departments with number of enrolled students between 1 and 10 or department budget code at least 90000, and department budget code between 90000 and 200000). The columns should be shown in the order: department code, department name, average total units, range of total units, variance of total units, minimum number of enrolled students, average department budget code, and reason. Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_ADMIN_DEPARTMENT", "SIS_DEPARTMENT", "SUBJECT_OFFERED_SUMMARY", "TIP_SUBJECT_OFFERED", "SIS_SUBJECT_CODE"]

## 连接键

[["SIS_ADMIN_DEPARTMENT.SIS_ADMIN_DEPARTMENT_CODE", "SIS_DEPARTMENT.DEPARTMENT_CODE"], ["SIS_DEPARTMENT.DEPARTMENT_CODE", "SUBJECT_OFFERED_SUMMARY.OFFER_DEPT_CODE"], ["SIS_DEPARTMENT.DEPARTMENT_CODE", "TIP_SUBJECT_OFFERED.OFFER_DEPT_CODE"], ["SIS_DEPARTMENT.DEPARTMENT_CODE", "SIS_SUBJECT_CODE.DEPARTMENT_CODE"]]

## 列映射

{"department code": ["SIS_DEPARTMENT.DEPARTMENT_CODE"], "department name": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "average total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"], "range of total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"], "variance of total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"], "minimum number of enrolled students": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "average department budget code": ["SIS_DEPARTMENT.DEPT_BUDGET_CODE"], "reason for inclusion": ["SIS_DEPARTMENT.IS_DEGREE_GRANTING", "SUBJECT_OFFERED_SUMMARY.OFFER_DEPT_NAME", "SUBJECT_OFFERED_SUMMARY.NUM_ENROLLED_STUDENTS", "SIS_DEPARTMENT.DEPARTMENT_NAME", "TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS", "SIS_DEPARTMENT.DEPT_BUDGET_CODE"]}

## 领域知识

["\"biology and chemistry department\" is predicated by \"TABLE.OFFER_DEPT_NAME IN ('Chemistry', 'Biology')\"", "\"math\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"Course 5\" is predicated by \"TABLE.OFFER_DEPT_NAME = 'Chemistry'\"", "\"Course 7\" is predicated by \"TABLE.OFFER_DEPT_NAME = 'Biology'\"", "\"Course 18\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\""]

## 表结构

### SIS_DEPARTMENT

- 列：["DEPARTMENT_CODE", "DEPARTMENT_NAME", "DEPARTMENT_FULL_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "DEPT_BUDGET_CODE", "IS_DEGREE_GRANTING", "DEPT_NAME_IN_COMMENCEMENT_BK", "SCHOOL_NAME_IN_COMMENCEMENT_BK", "DEPARTMENT_NAME_HISTORY", "DEPARTMENT_LAST_ACTIVITY_DATE", "DLC_KEY", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "VARCHAR2", "DATE"]
- 示例：[["HPM", "Health Policy & Management", "HPM-Health Policy & Management", "T", "Whitaker Coll of HST;  HST", 160000.0, "Y", NaN, "Whitaker College of Health Sciences and Technology", NaN, "17-FEB-94", "D_WHIT", "19-DEC-24"], ["NIE", "Non-Institute Exchange Student", "NIE-Non-Institute Exchange Student", "Z", "Non-MIT", NaN, "N", NaN, NaN, NaN, "12-JUL-95", "D_CROSS_REG", "19-DEC-24"], ["WHIT", "Whi

### SUBJECT_OFFERED_SUMMARY

- 列：["SUBJECT_OFFERED_SUMMARY_KEY", "COMPOSITE_SUBJECT_KEY", "TERM_CODE", "COURSE_NUMBER", "SUBJECT_ID", "SUBJECT_ID_SORT", "SUBJECT_TITLE", "MASTER_SUBJECT_ID", "MASTER_SUBJECT_ID_SORT", "CLUSTER_TYPE", "CLUSTER_TYPE_DESC", "CLUSTER_LIST", "HGN_CODE", "HGN_CODE_DESC", "OFFER_DEPT_CODE", "OFFER_DEPT_NAME", "OFFER_SCHOOL_NAME", "RESPONSIBLE_FACULTY_NAME", "RESPONSIBLE_FACULTY_MIT_ID", "TOTAL_UNITS", "LECTURE_UNITS", "LAB_UNITS", "PREPARATION_UNITS", "SUBJECT_ENROLLMENT_NUMBER", "CLUSTER_ENROLLMENT_NUMBER", "WAREHOUSE_LOAD_DATE", "NUM_ENROLLED_STUDENTS", "SUBJECT_GROUPING_KEY", "SUBJECT_SUMMARY_KEY"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "DATE", "NUMBER", "VARCHAR2", "VARCHAR2"]
- 示例：[["HAS.13162017FA", "HAS.00002017FA", "2017FA", "HAS", "HAS.1316", "HAS.1316", "The Bone Studio", "HAS.0000", "HAS.0000", "S", "SWE: School-Wide Electives", "HAS.0000, HAS.0100, HAS.1112, HAS.1212, HAS.1221, HAS.1300, HAS.1303, HAS.1304, HAS.1306, HAS.1307, HAS.1313, HAS.1314, HAS.131", "H", "Higher level graduate program", "NIH", "Harvard Cross-Enrollment Prog", "Non-MIT", NaN, NaN, 21.0, 0.0, 21

### TIP_SUBJECT_OFFERED

- 列：["TIP_SUBJECT_OFFERED_KEY", "TERM_CODE", "IS_NO_COURSE_MATERIAL", "MASTER_COURSE_NUMBER", "MASTER_COURSE_NUMBER_SORT", "MASTER_COURSE_NUMBER_DESC", "MASTER_SUBJECT_ID", "MASTER_SUBJECT_ID_SORT", "COURSE_NUMBER", "COURSE_NUMBER_SORT", "COURSE_NUMBER_DESC", "SUBJECT_ID", "SUBJECT_ID_SORT", "SUBJECT_TITLE", "OFFER_DEPT_CODE", "OFFER_DEPT_NAME", "OFFER_SCHOOL_NAME", "RESPONSIBLE_FACULTY_NAME", "RESPONSIBLE_FACULTY_MIT_ID", "NUM_ENROLLED_STUDENTS", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "DATE"]
- 示例：[["0166830002017JA", "2017JA", NaN, "16", " 16", "Aeronautics and Astronautics", "16.683", "16.683", "16", " 16", "Aeronautics and Astronautics", "16.683", " 16.683", "Sem Aeronautics & Astronautics", "16", "Aeronautics and Astronautics", "Engineering", "Branch, Claude", 910358479.0, 0, "20-DEC-24"], ["21M3410002005FA", "2005FA", NaN, "21M", "21M", "Music and Theater Arts", "21M.341", "21M.341", "

## 子问题

["For each department, give the department name and calculate the average, range, and variance of the total units for subjects offered by that department, considering only departments that are degree granting, subjects with more than zero enrolled students, and excluding the Chemistry and Biology departments.", "For each department give the department code, the department name, the minimum number of enrolled students and the average department budget code, where the number of enrolled students is between 1 and 10 or the department budget code is at least 90000, and the department budget code is between 90000 and 200000, for departments that are Mathematics (Course 18)?"]
