# 查询任务（dw）

## 问题

For each department that is degree granting, not Chemistry (Course 5), and has at least 100 total enrolled students in subjects it offers, what is the department name, the total number of enrolled students in its subjects, and, if the department is in the School of Engineering (excluding Management, Course 15), what is the maximum number of enrolled students in any subject it offered in the 2019FA term and the name of that subject with the maximum enrollment? Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_COURSE_DESCRIPTION", "SIS_DEPARTMENT", "SUBJECT_OFFERED_SUMMARY", "TIP_SUBJECT_OFFERED", "SIS_SUBJECT_CODE"]

## 连接键

[["SIS_COURSE_DESCRIPTION.DEPARTMENT", "SIS_DEPARTMENT.DEPARTMENT_CODE"], ["SIS_DEPARTMENT.DEPARTMENT_CODE", "SUBJECT_OFFERED_SUMMARY.OFFER_DEPT_CODE"], ["SIS_DEPARTMENT.DEPARTMENT_CODE", "TIP_SUBJECT_OFFERED.OFFER_DEPT_CODE"], ["SIS_DEPARTMENT.DEPARTMENT_CODE", "SIS_SUBJECT_CODE.DEPARTMENT_CODE"]]

## 列映射

{"department name": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "degree granting": ["SIS_DEPARTMENT.IS_DEGREE_GRANTING"], "Chemistry (Course 5)": ["SIS_DEPARTMENT.DEPARTMENT_CODE"], "total number of enrolled students": ["SUBJECT_OFFERED_SUMMARY.NUM_ENROLLED_STUDENTS"], "subjects it offers": ["SUBJECT_OFFERED_SUMMARY.OFFER_DEPT_CODE", "TIP_SUBJECT_OFFERED.OFFER_DEPT_CODE"], "School of Engineering": ["SIS_DEPARTMENT.SCHOOL_NAME"], "Management (Course 15)": ["SIS_DEPARTMENT.DEPARTMENT_CODE"], "maximum number of enrolled students in any subject": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "subject name with the maximum enrollment": ["TIP_SUBJECT_OFFERED.SUBJECT_TITLE"], "2019FA term": ["TIP_SUBJECT_OFFERED.TERM_CODE"]}

## 领域知识

["\"Chemistry\" is predicated by \"TABLE.OFFER_DEPT_NAME = 'Chemistry'\"", "\"degree-granting\" is predicated by \"TABLE.IS_DEGREE_GRANTING = 'Y'\"", "\"Course 5\" is predicated by \"TABLE.OFFER_DEPT_NAME = 'Chemistry'\"", "\"Chemistry\" is predicated by \"TABLE.DEPARTMENT_CODE = '5'\"", "\"Course 15\" is predicated by \"UPPER(TABLE.SIS_ADMIN_DEPARTMENT_NAME) = 'MANAGEMENT'\"", "\"Management\" is predicated by \"TABLE.DEPARTMENT_CODE = '15'\""]

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

["For each department, give the department name and calculate the total number of enrolled students in subjects offered by departments that are degree granting, have at least 100 total enrolled students, and are not the Chemistry department (Course 5).", "For each department in the School of Engineering, what is the maximum number of enrolled students in any subject offered by that department in the term 2019FA, what is the name of the subject with that maximum enrollment, and restrict the results to only degree-granting departments and exclude the Department of Management (Course 15)?"]
