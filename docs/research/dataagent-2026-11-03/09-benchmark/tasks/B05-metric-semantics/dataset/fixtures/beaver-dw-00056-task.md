# 查询任务（dw）

## 问题

List, for each department, the department name, the range, variance, and standard deviation (using STDDEV only and never STDDEV_POP) of the number of enrolled students per subject offered by that department in the 2022FA term (only including departments that grant degrees and excluding the Electrical Engineering and Computer Science department), as well as the department name and the total number of enrolled students in subjects offered by the School of Engineering in terms where the total units for the subject are greater than 6 (excluding the Chemistry department), along with the reason for inclusion ('DeptStats' for the first set and 'EngrEnrolled' for the second set). Show the columns in this order: department name, enrolled range, enrolled variance, enrolled standard deviation (using STDDEV only and never STDDEV_POP), total enrolled, and reason. Do not return any rounded answers.

## 库

dw

## 涉及表

["TIP_SUBJECT_OFFERED", "SIS_DEPARTMENT", "COURSE_CATALOG_SUBJECT_OFFERED", "SUBJECT_OFFERED", "SUBJECT_SUMMARY"]

## 连接键

[["SIS_DEPARTMENT.DEPARTMENT_CODE", "TIP_SUBJECT_OFFERED.OFFER_DEPT_CODE"], ["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_CODE", "SIS_DEPARTMENT.DEPARTMENT_CODE"], ["SUBJECT_OFFERED.TERM_CODE", "TIP_SUBJECT_OFFERED.TERM_CODE"], ["SUBJECT_OFFERED.TERM_CODE", "SUBJECT_SUMMARY.TERM_CODE"]]

## 列映射

{"department name": ["SIS_DEPARTMENT.DEPARTMENT_NAME", "TIP_SUBJECT_OFFERED.OFFER_DEPT_NAME"], "range of the number of enrolled students per subject": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "variance of the number of enrolled students per subject": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "standard deviation of the number of enrolled students per subject": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "2022FA term": ["TIP_SUBJECT_OFFERED.TERM_CODE"], "departments that grant degrees": ["SIS_DEPARTMENT.IS_DEGREE_GRANTING"], "Electrical Engineering and Computer Science department": ["SIS_DEPARTMENT.DEPARTMENT_CODE"], "total number of enrolled students": ["SUBJECT_SUMMARY.SUBJECT_ENROLLMENT_NUMBER"], "School of Engineering": ["TIP_SUBJECT_OFFERED.OFFER_SCHOOL_NAME"], "total units for the subject": ["SUBJECT_SUMMARY.TOTAL_UNITS"], "Chemistry department": ["TIP_SUBJECT_OFFERED.OFFER_DEPT_NAME"]}

## 领域知识

["\"degree-granting\" is predicated by \"TABLE.IS_DEGREE_GRANTING = 'Y'\"", "\"Chemistry\" is predicated by \"TABLE.OFFER_DEPT_NAME = 'Chemistry'\"", "\"Electrical Engineering and Computer Science\" is predicated by \"TABLE.DEPARTMENT_CODE = '6'\"", "\"Course 5\" is predicated by \"TABLE.OFFER_DEPT_NAME = 'Chemistry'\""]

## 表结构

### SIS_DEPARTMENT

- 列：["DEPARTMENT_CODE", "DEPARTMENT_NAME", "DEPARTMENT_FULL_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "DEPT_BUDGET_CODE", "IS_DEGREE_GRANTING", "DEPT_NAME_IN_COMMENCEMENT_BK", "SCHOOL_NAME_IN_COMMENCEMENT_BK", "DEPARTMENT_NAME_HISTORY", "DEPARTMENT_LAST_ACTIVITY_DATE", "DLC_KEY", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "VARCHAR2", "DATE"]
- 示例：[["HPM", "Health Policy & Management", "HPM-Health Policy & Management", "T", "Whitaker Coll of HST;  HST", 160000.0, "Y", NaN, "Whitaker College of Health Sciences and Technology", NaN, "17-FEB-94", "D_WHIT", "19-DEC-24"], ["NIE", "Non-Institute Exchange Student", "NIE-Non-Institute Exchange Student", "Z", "Non-MIT", NaN, "N", NaN, NaN, NaN, "12-JUL-95", "D_CROSS_REG", "19-DEC-24"], ["WHIT", "Whi

### COURSE_CATALOG_SUBJECT_OFFERED

- 列：["ACADEMIC_YEAR", "TERM_CODE", "SUBJECT_ID", "SUBJECT_CODE", "SUBJECT_NUMBER", "SOURCE_SUBJECT_ID", "PRINT_SUBJECT_ID", "IS_PRINTED_IN_BULLETIN", "DEPARTMENT_CODE", "DEPARTMENT_NAME", "EFFECTIVE_TERM_CODE", "SUBJECT_SHORT_TITLE", "SUBJECT_TITLE", "IS_VARIABLE_UNITS", "LECTURE_UNITS", "LAB_UNITS", "PREPARATION_UNITS", "TOTAL_UNITS", "DESIGN_UNITS", "GRADE_TYPE", "GRADE_TYPE_DESC", "GRADE_RULE", "GRADE_RULE_DESC", "HGN_CODE", "HGN_DESC", "HGN_EXCEPT", "GIR_ATTRIBUTE", "GIR_ATTRIBUTE_DESC", "COMM_REQ_ATTRIBUTE", "COMM_REQ_ATTRIBUTE_DESC", "TUITION_ATTRIBUTE", "TUITION_ATTRIBUTE_DESC", "WRITE_REQ_ATTRIBUTE", "WRITE_REQ_ATTRIBUTE_DESC", "SUPERVISOR_ATTRIBUTE", "SUPERVISOR_ATTRIBUTE_DESC", "PREREQUISITES", "SUBJECT_DESCRIPTION", "JOINT_SUBJECTS", "SCHOOL_WIDE_ELECTIVES", "MEETS_WITH_SUBJECTS", "EQUIVALENT_SUBJECTS", "IS_OFFERED_THIS_YEAR", "IS_OFFERED_FALL_TERM", "IS_OFFERED_IAP", "IS_OFFERED_SPRING_TERM", "IS_OFFERED_SUMMER_TERM", "FALL_INSTRUCTORS", "SPRING_INSTRUCTORS", "STATUS_CHANGE", "LAST_ACTIVITY_DATE", "WAREHOUSE_LOAD_DATE", "MASTER_SUBJECT_ID", "HASS_ATTRIBUTE", "HASS_ATTRIBUTE_DESC", "TERM_DURATION", "GLOBAL_REGIONS", "GLOBAL_COUNTRIES", "ON_LINE_PAGE_NUMBER", "SECTION_ID", "IS_MASTER_SECTION", "IS_LECTURE_SECTION", "IS_LAB_SECTION", "IS_RECITATION_SECTION", "IS_DESIGN_SECTION", "RESPONSIBLE_FACULTY_NAME", "RESPONSIBLE_FACULTY_MIT_ID", "MEET_TIME", "MEET_PLACE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2"]
- 示例：[[2006, "2006FA", "18.781", "18", "781", "18.781", "18.781", "Y", "18", "Mathematics", "2006FA", "Theory of Numbers", "Theory of Numbers", "N", 3, 0, 9, 12, 0, "L", "Letter graded", "N", "Not repeatable for credit", "U", "Undergraduate", NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, "An elementary introduction to number theory with no algebraic prerequisites. Primes, congruences, qua

### SUBJECT_OFFERED

- 列：["SUBJECT_KEY", "SUBJECT_OFFERED_SUMMARY_KEY", "MASTER_SUBJECT_KEY", "COMPOSITE_SUBJECT_KEY", "TERM_CODE", "MASTER_COURSE_NUMBER", "MASTER_COURSE_NUMBER_SORT", "MASTER_COURSE_NUMBER_DESC", "MASTER_SUBJECT_ID", "MASTER_SUBJECT_ID_SORT", "COURSE_NUMBER", "COURSE_NUMBER_SORT", "COURSE_NUMBER_DESC", "SUBJECT_ID", "SUBJECT_ID_SORT", "SUBJECT_TITLE", "SECTION_ID", "IS_MASTER_SECTION", "IS_LECTURE_SECTION", "IS_LAB_SECTION", "IS_RECITATION_SECTION", "IS_DESIGN_SECTION", "OFFER_DEPT_CODE", "OFFER_DEPT_NAME", "OFFER_SCHOOL_NAME", "RESPONSIBLE_FACULTY_NAME", "RESPONSIBLE_FACULTY_MIT_ID", "MEET_TIME", "MEET_PLACE", "CLUSTER_TYPE", "CLUSTER_TYPE_DESC", "CLUSTER_LIST", "HGN_CODE", "HGN_CODE_DESC", "FORM_TYPE", "FORM_TYPE_DESC", "SUBJECT_ENROLLMENT_NUMBER", "SECTION_ENROLLMENT_NUMBER", "CLUSTER_ENROLLMENT_NUMBER", "EVALUATE_THIS_SUBJECT", "IS_OSE_SUBJECT", "IS_CREATED_BY_DATA_WAREHOUSE", "SUBJECT_GROUPING_KEY", "WAREHOUSE_LOAD_DATE", "NUM_ENROLLED_STUDENTS", "SUBJECT_SUMMARY_KEY", "IS_REPEATABLE_SUBJECT"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "VARCHAR2", "NUMBER", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "NUMBER", "VARCHAR2", "VARCHAR2"]
- 示例：[["HAA47270002012SU", "HAA.47272012SU", "HAA00000002012SU", "HAA.00002012SU", "2012SU", "HAA", "HAA", "Harvard, Arts and Sciences", "HAA.0000", "HAA.0000", "HAA", "HAA", "Harvard, Arts and Sciences", "HAA.4727", "HAA.4727", "ENG 90 qm:Metaphysical Poetry", 0, "Y", "N", "N", "N", "N", "NIH", "Harvard Cross-Enrollment Prog", "Non-MIT", NaN, NaN, NaN, NaN, "S", "SWE: School-Wide Electives", "HAA.0000

## 子问题

["For each department, provide the department name and the range, variance, and standard deviation of the number of enrolled students per subject offered by that department in the 2022FA term, but only include departments that grant degrees and exclude the Electrical Engineering and Computer Science department (Course 6).", "For each department, give the department name and calculate the total number of enrolled students in subjects offered by the School of Engineering in terms where the total units for the subject are greater than 6, but only include departments that are not 'Chemistry' (Course 5)."]
