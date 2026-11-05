# 查询任务（dw）

## 问题

For each department in the current academic term that has offered more than 5 unique subjects in terms from the academic year 2014 or later, what is the average, variance, and standard deviation (using STDDEV only and never STDDEV_POP) of the total units for subjects offered, which school within that department has the highest average total units, the average total units for that school, the count of unique subject titles, and the total number of enrolled students in those subjects? Show the department name, average total units, variance of total units, standard deviation (using STDDEV only and never STDDEV_POP) of total units, school name with the highest average, its average total units, subject count, and total enrolled students, in that order, sorted by total enrolled students descending. Do not return any rounded answers.

## 库

dw

## 涉及表

["ACADEMIC_TERM_PARAMETER", "ACADEMIC_TERMS_ALL", "SUBJECT_SUMMARY", "LIBRARY_SUBJECT_OFFERED", "ACADEMIC_TERMS"]

## 连接键

[["ACADEMIC_TERMS_ALL.TERM_CODE", "ACADEMIC_TERM_PARAMETER.TERM_CODE"], ["ACADEMIC_TERMS_ALL.TERM_CODE", "SUBJECT_SUMMARY.TERM_CODE"], ["ACADEMIC_TERMS.TERM_CODE", "LIBRARY_SUBJECT_OFFERED.TERM_CODE"], ["ACADEMIC_TERMS.TERM_CODE", "SUBJECT_SUMMARY.TERM_CODE"]]

## 列映射

{"department": ["SUBJECT_SUMMARY.DEPARTMENT_NAME", "LIBRARY_SUBJECT_OFFERED.OFFER_DEPT_NAME"], "current academic term": ["ACADEMIC_TERM_PARAMETER.IS_CURRENT_TERM"], "offered more than 5 unique subjects": ["LIBRARY_SUBJECT_OFFERED.OFFER_DEPT_NAME", "SUBJECT_SUMMARY.SUBJECT_TITLE"], "academic year 2014 or later": ["ACADEMIC_TERMS.ACADEMIC_YEAR"], "average total units": ["SUBJECT_SUMMARY.TOTAL_UNITS"], "variance of total units": ["SUBJECT_SUMMARY.TOTAL_UNITS"], "standard deviation of total units": ["SUBJECT_SUMMARY.TOTAL_UNITS"], "school within that department": ["SUBJECT_SUMMARY.SCHOOL_NAME"], "school with the highest average total units": ["SUBJECT_SUMMARY.SCHOOL_NAME", "SUBJECT_SUMMARY.TOTAL_UNITS"], "subject count": ["SUBJECT_SUMMARY.SUBJECT_TITLE"], "total number of enrolled students": ["LIBRARY_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"]}

## 领域知识

[]

## 表结构

### ACADEMIC_TERMS_ALL

- 列：["ACADEMIC_TERMS_KEY", "TERM_CODE", "TERM_DESCRIPTION", "TERM_SELECTOR", "TERM_START_DATE", "TERM_END_DATE", "ACADEMIC_YEAR", "ACADEMIC_YEAR_DESC", "IS_CURRENT_TERM", "TERM_STATUS_INDICATOR", "FINANCIAL_AID_YEAR", "DEGREE_YEAR", "LAST_DAY_OF_FINAL_EXAM", "PRE_REGISTRATION_START_DAY", "REGISTRATION_DAY", "FIRST_DAY_OF_CLASSES", "LAST_DAY_OF_CLASSES", "GRADUATE_AWARD_START_DATE", "GRADUATE_AWARD_END_DATE", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE"]
- 示例：[["2022SU", "2022SU", "Summer Term 2022", "2022SU-Summer Term 2022", "06-JUN-22", "16-AUG-22", 2022, "Academic Year 2021-2022", "N", "P", "2023", "2023", "16-AUG-22", "02-MAY-22", "06-JUN-22", "06-JUN-22", "12-AUG-22", "01-JUN-22", "31-AUG-22", "19-DEC-24"], ["2020JA", "2020JA", "January Term 2019-2020", "2020JA-January Term 2019-2020", "06-JAN-20", "31-JAN-20", 2020, "Academic Year 2019-2020", "N

### SUBJECT_SUMMARY

- 列：["SUBJECT_SUMMARY_KEY", "TERM_CODE", "SUBJECT_ID", "SUBJECT_ID_SORT", "SUBJECT_TITLE", "SUBJECT_OR_CLUSTER", "MASTER_SUBJECT_ID", "MASTER_SUBJECT_ID_SORT", "ULT_MASTER_SUBJECT_ID", "CLUSTER_TYPE", "CLUSTER_TYPE_DESC", "CLUSTER_LIST", "DEPARTMENT_CODE", "DEPARTMENT_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "TOTAL_UNITS", "LECTURE_UNITS", "LAB_UNITS", "PREP_UNITS", "DESIGN_UNITS", "SUBJECT_ENROLLMENT_NUMBER", "CLUSTER_ENROLLMENT_NUMBER", "SUBJECT_GROUP_ID", "SUBJECT_ENROLLMENT_FIRST_WEEK", "CLUSTER_ENROLLMENT_FIRST_WEEK", "SUBJECT_ENROLLMENT_FIFTH_WEEK", "CLUSTER_ENROLLMENT_FIFTH_WEEK", "SUBJECT_ENROLLMENT_CREDIT", "SUBJECT_ENROLLMENT_LISTEN", "CLUSTER_ENROLLMENT_CREDIT", "CLUSTER_ENROLLMENT_LISTEN", "SUBJECT_ENROLLMENT_1ST_CREDIT", "SUBJECT_ENROLLMENT_1ST_LISTEN", "CLUSTER_ENROLLMENT_1ST_CREDIT", "CLUSTER_ENROLLMENT_1ST_LISTEN", "SUBJECT_ENROLLMENT_5TH_CREDIT", "SUBJECT_ENROLLMENT_5TH_LISTEN", "CLUSTER_ENROLLMENT_5TH_CREDIT", "CLUSTER_ENROLLMENT_5TH_LISTEN", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "VARCHAR2", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "DATE"]
- 示例：[["2.UR2019FA", "2019FA", "2.UR", "  2.UR", "Undergraduate Research", "2.UR", "2.UR", "  2.UR", "2.UR", NaN, NaN, NaN, "2", "Mechanical Engineering", "E", "Engineering", 1.0, 0.0, 1.0, 0.0, 0.0, 7, NaN, "679673EE2BF43692E0533D2F0912F028", 7, 7, 7, 7, 7, 0, 7, 0, 7, 0, 7, 0, 7, 0, 7, 0, "20-DEC-24"], ["HAA.89682009SP", "2009SP", "HAA.8968", "HAA.8968", "Yiddish Cb:Advanced II", "HAA.0000, HAA.0021,

### LIBRARY_SUBJECT_OFFERED

- 列：["LIBRARY_SUBJECT_OFFERED_KEY", "TERM_CODE", "MASTER_COURSE_NUMBER", "MASTER_COURSE_NUMBER_SORT", "MASTER_COURSE_NUMBER_DESC", "MASTER_SUBJECT_ID", "MASTER_SUBJECT_ID_SORT", "COURSE_NUMBER", "COURSE_NUMBER_SORT", "COURSE_NUMBER_DESC", "SUBJECT_ID", "SUBJECT_ID_SORT", "SUBJECT_TITLE", "OFFER_DEPT_CODE", "OFFER_DEPT_NAME", "OFFER_SCHOOL_NAME", "RESPONSIBLE_FACULTY_NAME", "RESPONSIBLE_FACULTY_MIT_ID", "NUM_ENROLLED_STUDENTS", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "DATE"]
- 示例：[["18.02A2012SP", "2012SP", "18", " 18", "Mathematics", "18.02A", "18.02A", "18", " 18", "Mathematics", "18.02A", " 18.02A", "Calculus", "18", "Mathematics", "Science", "Donnelly, Maya", 928034212.0, 8, "19-DEC-24"], ["14.742014FA", "2014FA", "14", " 14", "Economics", "14.74", "14.74", "14", " 14", "Economics", "14.74", " 14.74", "Foundations: Dev Policy", "14", "Economics", "Hum, Arts & Social Sc

## 子问题

["For each school, what is the average, variance, and standard deviation of the total units for subjects offered in the current academic term? Show the school name along with these statistics.", "List the top 10 departments by the number of unique subjects they offered, including the department name and the count of unique subject titles, for terms in the academic year 2014 or later.", "For each department in the current academic term, what is the average, variance, and standard deviation of the total units for subjects offered, and which school within that department has the highest average total units? Show the department name, the overall statistics, the school name with the highest average, and its average total units.", "For departments that offered more than 5 unique subjects in terms from the academic year 2014 or later, list the department name, the count of unique subject titles, and the total number of enrolled students in those subjects."]
