# 查询任务（dw）

## 问题

For departments that are among both the top 10 by number of non-repeatable-for-credit subjects offered in the fall term (across all academic years) and the top 5 by total subject units in the academic term with term code '2009SP', display for each such department: the department name, academic year, number of non-repeatable-for-credit subjects offered in the fall term, subject code, subject title, the department's total units in '2009SP', the subject title with the highest units in that department in '2009SP', and the number of subjects offered by that department in '2009SP'. List the results ordered by total units in '2009SP' (descending), then department name, academic year, and subject code. Do not return any rounded answers.

## 库

dw

## 涉及表

["SUBJECT_OFFERED", "ACADEMIC_TERMS", "COURSE_CATALOG_SUBJECT_OFFERED", "SUBJECT_SUMMARY"]

## 连接键

[["ACADEMIC_TERMS.TERM_CODE", "SUBJECT_OFFERED.TERM_CODE"], ["ACADEMIC_TERMS.TERM_CODE", "COURSE_CATALOG_SUBJECT_OFFERED.EFFECTIVE_TERM_CODE"], ["ACADEMIC_TERMS.TERM_CODE", "SUBJECT_SUMMARY.TERM_CODE"]]

## 列映射

{"departments": ["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_NAME", "SUBJECT_SUMMARY.DEPARTMENT_NAME"], "top 10 by number of non-repeatable-for-credit subjects offered in the fall term": ["COURSE_CATALOG_SUBJECT_OFFERED.GRADE_RULE_DESC", "COURSE_CATALOG_SUBJECT_OFFERED.IS_OFFERED_FALL_TERM", "SUBJECT_OFFERED.SUBJECT_KEY", "COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_NAME", "ACADEMIC_TERMS.ACADEMIC_YEAR"], "top 5 by total subject units in the academic term with term code '2009SP'": ["SUBJECT_SUMMARY.TOTAL_UNITS", "ACADEMIC_TERMS.TERM_CODE", "SUBJECT_SUMMARY.DEPARTMENT_NAME"], "department name": ["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_NAME", "SUBJECT_SUMMARY.DEPARTMENT_NAME"], "academic year": ["ACADEMIC_TERMS.ACADEMIC_YEAR"], "number of non-repeatable-for-credit subjects offered in the fall term": ["SUBJECT_OFFERED.SUBJECT_KEY", "COURSE_CATALOG_SUBJECT_OFFERED.GRADE_RULE_DESC", "COURSE_CATALOG_SUBJECT_OFFERED.IS_OFFERED_FALL_TERM"], "subject code": ["COURSE_CATALOG_SUBJECT_OFFERED.SUBJECT_CODE"], "subject title": ["COURSE_CATALOG_SUBJECT_OFFERED.SUBJECT_TITLE"], "total units in '2009SP'": ["SUBJECT_SUMMARY.TOTAL_UNITS", "ACADEMIC_TERMS.TERM_CODE"], "subject title with the highest units in that department in '2009SP'": ["SUBJECT_SUMMARY.SUBJECT_TITLE", "SUBJECT_SUMMARY.TOTAL_UNITS", "SUBJECT_SUMMARY.DEPARTMENT_NAME", "ACADEMIC_TERMS.TERM_CODE"], "number of subjects offered by that department in '2009SP'": ["SUBJECT_SUMMARY.DEPARTMENT_NAME", "ACADEMIC_TERMS.TERM_CODE", "SUBJECT_SUMMARY.SUBJECT_TITLE"]}

## 领域知识

[]

## 表结构

### ACADEMIC_TERMS

- 列：["ACADEMIC_TERMS_KEY", "TERM_CODE", "TERM_DESCRIPTION", "TERM_SELECTOR", "TERM_START_DATE", "TERM_END_DATE", "ACADEMIC_YEAR", "ACADEMIC_YEAR_DESC", "IS_CURRENT_TERM", "IS_REGULAR_TERM", "TERM_STATUS_INDICATOR", "TERM_STATUS", "FINANCIAL_AID_YEAR", "DEGREE_YEAR", "LAST_DAY_OF_FINAL_EXAM", "PRE_REGISTRATION_START_DAY", "REGISTRATION_DAY", "FIRST_DAY_OF_CLASSES", "LAST_DAY_OF_CLASSES", "ADD_DATE", "DROP_DATE", "GRADUATE_AWARD_START_DATE", "GRADUATE_AWARD_END_DATE", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE"]
- 示例：[["2003JA", "2003JA", "January Term 2002-2003", "2003JA-January Term 2002-2003", "06-JAN-03", "02-FEB-03", 2003, "Academic Year 2002-2003", "N", "N", "P", "Previous", NaN, NaN, "31-JAN-03", "29-NOV-02", "06-JAN-03", "06-JAN-03", "31-JAN-03", NaN, NaN, NaN, NaN, "19-DEC-24"], ["2027JA", "2027JA", "January Term 2026-2027", "2027JA-January Term 2026-2027", "04-JAN-27", "29-JAN-27", 2027, "Academic Ye

### COURSE_CATALOG_SUBJECT_OFFERED

- 列：["ACADEMIC_YEAR", "TERM_CODE", "SUBJECT_ID", "SUBJECT_CODE", "SUBJECT_NUMBER", "SOURCE_SUBJECT_ID", "PRINT_SUBJECT_ID", "IS_PRINTED_IN_BULLETIN", "DEPARTMENT_CODE", "DEPARTMENT_NAME", "EFFECTIVE_TERM_CODE", "SUBJECT_SHORT_TITLE", "SUBJECT_TITLE", "IS_VARIABLE_UNITS", "LECTURE_UNITS", "LAB_UNITS", "PREPARATION_UNITS", "TOTAL_UNITS", "DESIGN_UNITS", "GRADE_TYPE", "GRADE_TYPE_DESC", "GRADE_RULE", "GRADE_RULE_DESC", "HGN_CODE", "HGN_DESC", "HGN_EXCEPT", "GIR_ATTRIBUTE", "GIR_ATTRIBUTE_DESC", "COMM_REQ_ATTRIBUTE", "COMM_REQ_ATTRIBUTE_DESC", "TUITION_ATTRIBUTE", "TUITION_ATTRIBUTE_DESC", "WRITE_REQ_ATTRIBUTE", "WRITE_REQ_ATTRIBUTE_DESC", "SUPERVISOR_ATTRIBUTE", "SUPERVISOR_ATTRIBUTE_DESC", "PREREQUISITES", "SUBJECT_DESCRIPTION", "JOINT_SUBJECTS", "SCHOOL_WIDE_ELECTIVES", "MEETS_WITH_SUBJECTS", "EQUIVALENT_SUBJECTS", "IS_OFFERED_THIS_YEAR", "IS_OFFERED_FALL_TERM", "IS_OFFERED_IAP", "IS_OFFERED_SPRING_TERM", "IS_OFFERED_SUMMER_TERM", "FALL_INSTRUCTORS", "SPRING_INSTRUCTORS", "STATUS_CHANGE", "LAST_ACTIVITY_DATE", "WAREHOUSE_LOAD_DATE", "MASTER_SUBJECT_ID", "HASS_ATTRIBUTE", "HASS_ATTRIBUTE_DESC", "TERM_DURATION", "GLOBAL_REGIONS", "GLOBAL_COUNTRIES", "ON_LINE_PAGE_NUMBER", "SECTION_ID", "IS_MASTER_SECTION", "IS_LECTURE_SECTION", "IS_LAB_SECTION", "IS_RECITATION_SECTION", "IS_DESIGN_SECTION", "RESPONSIBLE_FACULTY_NAME", "RESPONSIBLE_FACULTY_MIT_ID", "MEET_TIME", "MEET_PLACE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2"]
- 示例：[[2006, "2006FA", "18.781", "18", "781", "18.781", "18.781", "Y", "18", "Mathematics", "2006FA", "Theory of Numbers", "Theory of Numbers", "N", 3, 0, 9, 12, 0, "L", "Letter graded", "N", "Not repeatable for credit", "U", "Undergraduate", NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, "An elementary introduction to number theory with no algebraic prerequisites. Primes, congruences, qua

## 子问题

["List the top 10 department names and their corresponding academic years by the number of subjects offered, including only subjects that are not repeatable for credit and are offered in the fall term.", "For subjects in the academic term with term code '2009SP', show the subject title, department name, total units, and assign row numbers within a window of 2 preceding and 1 following rows ordered by subject title.", "Show the department names, academic years, the number of non-repeatable-for-credit subjects offered in the fall term, and the corresponding subject codes and subject titles for those subjects, for the top 10 departments by subject count.", "For the top 5 departments with the highest total subject units in the academic term with term code '2009SP', show each department's name, the total units for that department, the subject title with the highest units in that department, and the number of subjects offered by that department in that term."]
