# 查询任务（dw）

## 问题

For subjects offered in the academic year 2024 with a total of 12 units, and for subjects offered in the term 2019FA from the same department, show the subject code, subject number, subject title, department name, term description, the rank of each 2024 subject within its department ordered by subject code, the 2019FA subject ID, number of enrolled students in 2019FA, department full name, the row number of each 2019FA subject within its department name group ordered by subject ID, and the school name for each department. Order the results by department name, subject code, and 2019FA subject ID. Do not return any rounded answers.

## 库

dw

## 涉及表

["COURSE_CATALOG_SUBJECT_OFFERED", "ACADEMIC_TERMS", "SUBJECT_SUMMARY", "TIP_SUBJECT_OFFERED", "SIS_DEPARTMENT"]

## 连接键

[["ACADEMIC_TERMS.TERM_CODE", "COURSE_CATALOG_SUBJECT_OFFERED.EFFECTIVE_TERM_CODE"], ["ACADEMIC_TERMS.TERM_CODE", "SUBJECT_SUMMARY.TERM_CODE"], ["SIS_DEPARTMENT.DEPARTMENT_CODE", "TIP_SUBJECT_OFFERED.OFFER_DEPT_CODE"]]

## 列映射

{"subjects offered in the academic year 2024": ["COURSE_CATALOG_SUBJECT_OFFERED.ACADEMIC_YEAR"], "total of 12 units": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS"], "subjects offered in the term 2019FA": ["TIP_SUBJECT_OFFERED.TERM_CODE"], "subject code": ["COURSE_CATALOG_SUBJECT_OFFERED.SUBJECT_CODE"], "subject number": ["COURSE_CATALOG_SUBJECT_OFFERED.SUBJECT_NUMBER"], "subject title": ["COURSE_CATALOG_SUBJECT_OFFERED.SUBJECT_TITLE", "TIP_SUBJECT_OFFERED.SUBJECT_TITLE"], "department name": ["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_NAME", "SIS_DEPARTMENT.DEPARTMENT_NAME"], "term description": ["ACADEMIC_TERMS.TERM_DESCRIPTION"], "rank of each 2024 subject within its department ordered by subject code": ["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_NAME", "COURSE_CATALOG_SUBJECT_OFFERED.SUBJECT_CODE"], "2019FA subject ID": ["TIP_SUBJECT_OFFERED.SUBJECT_ID"], "number of enrolled students in 2019FA": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "department full name": ["SIS_DEPARTMENT.DEPARTMENT_FULL_NAME"], "row number of each 2019FA subject within its department name group ordered by subject ID": ["SIS_DEPARTMENT.DEPARTMENT_NAME", "TIP_SUBJECT_OFFERED.SUBJECT_ID"], "school name for each department": ["SIS_DEPARTMENT.SCHOOL_NAME"]}

## 领域知识

[]

## 表结构

### ACADEMIC_TERMS

- 列：["ACADEMIC_TERMS_KEY", "TERM_CODE", "TERM_DESCRIPTION", "TERM_SELECTOR", "TERM_START_DATE", "TERM_END_DATE", "ACADEMIC_YEAR", "ACADEMIC_YEAR_DESC", "IS_CURRENT_TERM", "IS_REGULAR_TERM", "TERM_STATUS_INDICATOR", "TERM_STATUS", "FINANCIAL_AID_YEAR", "DEGREE_YEAR", "LAST_DAY_OF_FINAL_EXAM", "PRE_REGISTRATION_START_DAY", "REGISTRATION_DAY", "FIRST_DAY_OF_CLASSES", "LAST_DAY_OF_CLASSES", "ADD_DATE", "DROP_DATE", "GRADUATE_AWARD_START_DATE", "GRADUATE_AWARD_END_DATE", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE"]
- 示例：[["2003JA", "2003JA", "January Term 2002-2003", "2003JA-January Term 2002-2003", "06-JAN-03", "02-FEB-03", 2003, "Academic Year 2002-2003", "N", "N", "P", "Previous", NaN, NaN, "31-JAN-03", "29-NOV-02", "06-JAN-03", "06-JAN-03", "31-JAN-03", NaN, NaN, NaN, NaN, "19-DEC-24"], ["2027JA", "2027JA", "January Term 2026-2027", "2027JA-January Term 2026-2027", "04-JAN-27", "29-JAN-27", 2027, "Academic Ye

### SUBJECT_SUMMARY

- 列：["SUBJECT_SUMMARY_KEY", "TERM_CODE", "SUBJECT_ID", "SUBJECT_ID_SORT", "SUBJECT_TITLE", "SUBJECT_OR_CLUSTER", "MASTER_SUBJECT_ID", "MASTER_SUBJECT_ID_SORT", "ULT_MASTER_SUBJECT_ID", "CLUSTER_TYPE", "CLUSTER_TYPE_DESC", "CLUSTER_LIST", "DEPARTMENT_CODE", "DEPARTMENT_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "TOTAL_UNITS", "LECTURE_UNITS", "LAB_UNITS", "PREP_UNITS", "DESIGN_UNITS", "SUBJECT_ENROLLMENT_NUMBER", "CLUSTER_ENROLLMENT_NUMBER", "SUBJECT_GROUP_ID", "SUBJECT_ENROLLMENT_FIRST_WEEK", "CLUSTER_ENROLLMENT_FIRST_WEEK", "SUBJECT_ENROLLMENT_FIFTH_WEEK", "CLUSTER_ENROLLMENT_FIFTH_WEEK", "SUBJECT_ENROLLMENT_CREDIT", "SUBJECT_ENROLLMENT_LISTEN", "CLUSTER_ENROLLMENT_CREDIT", "CLUSTER_ENROLLMENT_LISTEN", "SUBJECT_ENROLLMENT_1ST_CREDIT", "SUBJECT_ENROLLMENT_1ST_LISTEN", "CLUSTER_ENROLLMENT_1ST_CREDIT", "CLUSTER_ENROLLMENT_1ST_LISTEN", "SUBJECT_ENROLLMENT_5TH_CREDIT", "SUBJECT_ENROLLMENT_5TH_LISTEN", "CLUSTER_ENROLLMENT_5TH_CREDIT", "CLUSTER_ENROLLMENT_5TH_LISTEN", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "VARCHAR2", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "DATE"]
- 示例：[["2.UR2019FA", "2019FA", "2.UR", "  2.UR", "Undergraduate Research", "2.UR", "2.UR", "  2.UR", "2.UR", NaN, NaN, NaN, "2", "Mechanical Engineering", "E", "Engineering", 1.0, 0.0, 1.0, 0.0, 0.0, 7, NaN, "679673EE2BF43692E0533D2F0912F028", 7, 7, 7, 7, 7, 0, 7, 0, 7, 0, 7, 0, 7, 0, 7, 0, "20-DEC-24"], ["HAA.89682009SP", "2009SP", "HAA.8968", "HAA.8968", "Yiddish Cb:Advanced II", "HAA.0000, HAA.0021,

### TIP_SUBJECT_OFFERED

- 列：["TIP_SUBJECT_OFFERED_KEY", "TERM_CODE", "IS_NO_COURSE_MATERIAL", "MASTER_COURSE_NUMBER", "MASTER_COURSE_NUMBER_SORT", "MASTER_COURSE_NUMBER_DESC", "MASTER_SUBJECT_ID", "MASTER_SUBJECT_ID_SORT", "COURSE_NUMBER", "COURSE_NUMBER_SORT", "COURSE_NUMBER_DESC", "SUBJECT_ID", "SUBJECT_ID_SORT", "SUBJECT_TITLE", "OFFER_DEPT_CODE", "OFFER_DEPT_NAME", "OFFER_SCHOOL_NAME", "RESPONSIBLE_FACULTY_NAME", "RESPONSIBLE_FACULTY_MIT_ID", "NUM_ENROLLED_STUDENTS", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "DATE"]
- 示例：[["0166830002017JA", "2017JA", NaN, "16", " 16", "Aeronautics and Astronautics", "16.683", "16.683", "16", " 16", "Aeronautics and Astronautics", "16.683", " 16.683", "Sem Aeronautics & Astronautics", "16", "Aeronautics and Astronautics", "Engineering", "Branch, Claude", 910358479.0, 0, "20-DEC-24"], ["21M3410002005FA", "2005FA", NaN, "21M", "21M", "Music and Theater Arts", "21M.341", "21M.341", "

## 子问题

["For subjects offered in the academic year 2024 with a total of 12 units, show the subject code, subject number, subject title, department name, term description, and the rank of each subject within its department ordered by subject code.", "For subjects offered in the term 2019FA, show the subject ID, subject title, number of enrolled students, department name, department full name, and assign row numbers within each department name group ordered by subject ID.", "For subjects offered in the academic year 2024 with a total of 12 units, and for subjects offered in the term 2019FA from the same department, show the subject code, subject number, subject title, department name, term description, the rank of each 2024 subject within its department ordered by subject code, the 2019FA subject ID, number of enrolled students in 2019FA, department full name, and the row number of each 2019FA subject within its department name group ordered by subject ID. Order the results by department name, subject code, and 2019FA subject ID."]
