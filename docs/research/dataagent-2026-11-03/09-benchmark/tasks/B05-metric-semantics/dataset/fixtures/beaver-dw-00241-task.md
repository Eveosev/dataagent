# 查询任务（dw）

## 问题

For each department and academic year where the subject enrollment number is greater than 10, provide the department name, academic year, number of unique subjects, minimum total units offered, and the variance of the number of enrolled students in courses with at least one enrolled student and course materials with a material status of 'RQ'. Also, for each department that has the variance of enrolled students in such courses but does not appear in the first group, include the department name and the variance, with academic year, number of unique subjects, and minimum total units as null. Do not return any rounded answers.

## 库

dw

## 涉及表

["COURSE_CATALOG_SUBJECT_OFFERED", "ACADEMIC_TERMS", "SUBJECT_SUMMARY", "TIP_DETAIL", "TIP_SUBJECT_OFFERED"]

## 连接键

[["ACADEMIC_TERMS.TERM_CODE", "COURSE_CATALOG_SUBJECT_OFFERED.TERM_CODE"], ["ACADEMIC_TERMS.TERM_CODE", "SUBJECT_SUMMARY.TERM_CODE"], ["TIP_DETAIL.TIP_SUBJECT_OFFERED_KEY", "TIP_SUBJECT_OFFERED.TIP_SUBJECT_OFFERED_KEY"]]

## 列映射

{"department": ["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_NAME", "TIP_SUBJECT_OFFERED.OFFER_DEPT_NAME"], "academic year": ["ACADEMIC_TERMS.ACADEMIC_YEAR"], "subject enrollment number": ["SUBJECT_SUMMARY.SUBJECT_ENROLLMENT_NUMBER"], "number of unique subjects": ["COURSE_CATALOG_SUBJECT_OFFERED.SUBJECT_ID"], "minimum total units offered": ["SUBJECT_SUMMARY.TOTAL_UNITS"], "variance of the number of enrolled students": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "courses with at least one enrolled student": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "course materials with a material status of 'RQ'": ["TIP_DETAIL.TIP_MATERIAL_STATUS_KEY"]}

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

### TIP_DETAIL

- 列：["TIP_SUBJECT_OFFERED_KEY", "TIP_MATERIAL_KEY", "TIP_MATERIAL_STATUS_KEY", "TERM_CODE", "SUBJECT_ID", "ISBN", "RECORD_COUNT", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "DATE"]
- 示例：[["0043700002010FA", "0262731223 Critical vehicles : writings, projects, interviews / KrzysztWodiczko, Krzysztof.Cambridge, Mass19992010FA", "RC", "2010FA", "4.370", "0262731223 ", 1, "20-DEC-24"], ["21G4020002017SP", "9781285675312EBK NEUE HORIZONTE82017SP", "EO", "2017SP", "21G.402", "9781285675312", 1, "20-DEC-24"], ["0106260002014SP", "N/ACourse has no materials2014SP", "NM", "2014SP", "10.626

## 子问题

["For each department and academic year where the subject enrollment number is greater than 10, provide the number of unique subjects and the minimum total units offered.", "For each department, what is the department name and the variance of the number of enrolled students in courses that have at least one enrolled student and have course materials with a material status of 'RQ'?"]
