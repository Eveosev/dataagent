# 查询任务（dw）

## 问题

For subjects offered in the term with code '2025FA' that are in departments whose total number of units for all courses is more than one standard deviation (using STDDEV only and never STDDEV_POP) above the mean total units across all departments, show the subject ID, subject title, offering department name, number of enrolled students, term description, academic year, term start date, term end date, term parameter, the difference between the number of enrolled students for each subject and the minimum number of enrolled students in its offering department, the department name, and the total number of units for all courses in that department, in that order. Do not return any rounded answers.

## 库

dw

## 涉及表

["TIP_SUBJECT_OFFERED", "ACADEMIC_TERMS_ALL", "ACADEMIC_TERM_PARAMETER", "SIS_DEPARTMENT", "CIS_COURSE_CATALOG"]

## 连接键

[["ACADEMIC_TERMS_ALL.TERM_CODE", "TIP_SUBJECT_OFFERED.TERM_CODE"], ["ACADEMIC_TERMS_ALL.TERM_CODE", "ACADEMIC_TERM_PARAMETER.TERM_CODE"], ["CIS_COURSE_CATALOG.DEPARTMENT_CODE", "SIS_DEPARTMENT.DEPARTMENT_CODE"]]

## 列映射

{"subjects": ["TIP_SUBJECT_OFFERED.SUBJECT_ID", "TIP_SUBJECT_OFFERED.SUBJECT_TITLE"], "subject ID": ["TIP_SUBJECT_OFFERED.SUBJECT_ID"], "subject title": ["TIP_SUBJECT_OFFERED.SUBJECT_TITLE"], "offering department name": ["TIP_SUBJECT_OFFERED.OFFER_DEPT_NAME"], "offering department code": ["TIP_SUBJECT_OFFERED.OFFER_DEPT_CODE"], "number of enrolled students": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "term code '2025FA'": ["TIP_SUBJECT_OFFERED.TERM_CODE"], "term description": ["ACADEMIC_TERMS_ALL.TERM_DESCRIPTION"], "academic year": ["ACADEMIC_TERMS_ALL.ACADEMIC_YEAR"], "term start date": ["ACADEMIC_TERMS_ALL.TERM_START_DATE"], "term end date": ["ACADEMIC_TERMS_ALL.TERM_END_DATE"], "term parameter": ["ACADEMIC_TERM_PARAMETER.TERM_PARAMETER"], "difference between the number of enrolled students for each subject and the minimum number of enrolled students in its offering department": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "minimum number of enrolled students in its offering department": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "department name": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "total number of units for all courses in that department": ["CIS_COURSE_CATALOG.TOTAL_UNITS"], "departments whose total number of units for all courses is more than one standard deviation above the mean total units across all departments": ["SIS_DEPARTMENT.DEPARTMENT_CODE", "CIS_COURSE_CATALOG.TOTAL_UNITS"]}

## 领域知识

[]

## 表结构

### ACADEMIC_TERMS_ALL

- 列：["ACADEMIC_TERMS_KEY", "TERM_CODE", "TERM_DESCRIPTION", "TERM_SELECTOR", "TERM_START_DATE", "TERM_END_DATE", "ACADEMIC_YEAR", "ACADEMIC_YEAR_DESC", "IS_CURRENT_TERM", "TERM_STATUS_INDICATOR", "FINANCIAL_AID_YEAR", "DEGREE_YEAR", "LAST_DAY_OF_FINAL_EXAM", "PRE_REGISTRATION_START_DAY", "REGISTRATION_DAY", "FIRST_DAY_OF_CLASSES", "LAST_DAY_OF_CLASSES", "GRADUATE_AWARD_START_DATE", "GRADUATE_AWARD_END_DATE", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE"]
- 示例：[["2022SU", "2022SU", "Summer Term 2022", "2022SU-Summer Term 2022", "06-JUN-22", "16-AUG-22", 2022, "Academic Year 2021-2022", "N", "P", "2023", "2023", "16-AUG-22", "02-MAY-22", "06-JUN-22", "06-JUN-22", "12-AUG-22", "01-JUN-22", "31-AUG-22", "19-DEC-24"], ["2020JA", "2020JA", "January Term 2019-2020", "2020JA-January Term 2019-2020", "06-JAN-20", "31-JAN-20", 2020, "Academic Year 2019-2020", "N

### ACADEMIC_TERM_PARAMETER

- 列：["TERM_PARAMETER", "TERM_INDICATOR", "TERM_CODE", "TERM_DESCRIPTION", "TERM_START_DATE", "TERM_END_DATE", "TERM_LAST_DAY_BEFORE_NEXT_TERM", "IS_CURRENT_TERM"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "DATE", "VARCHAR2"]
- 示例：[["SIS_UPCOMING_TERM", "F", "2025JA", "January Term 2024-2025", "06-JAN-25", "31-JAN-25", "31-JAN-25", "N"], ["SIS_CURRENT_TERM", "C", "2025FA", "Fall Term 2024-2025", "03-SEP-24", "20-DEC-24", "05-JAN-25", "Y"], ["SIS_PREVIOUS_TERM", "P", "2024SU", "Summer Term 2024", "10-JUN-24", "20-AUG-24", "02-SEP-24", "N"]]

### SIS_DEPARTMENT

- 列：["DEPARTMENT_CODE", "DEPARTMENT_NAME", "DEPARTMENT_FULL_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "DEPT_BUDGET_CODE", "IS_DEGREE_GRANTING", "DEPT_NAME_IN_COMMENCEMENT_BK", "SCHOOL_NAME_IN_COMMENCEMENT_BK", "DEPARTMENT_NAME_HISTORY", "DEPARTMENT_LAST_ACTIVITY_DATE", "DLC_KEY", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "VARCHAR2", "DATE"]
- 示例：[["HPM", "Health Policy & Management", "HPM-Health Policy & Management", "T", "Whitaker Coll of HST;  HST", 160000.0, "Y", NaN, "Whitaker College of Health Sciences and Technology", NaN, "17-FEB-94", "D_WHIT", "19-DEC-24"], ["NIE", "Non-Institute Exchange Student", "NIE-Non-Institute Exchange Student", "Z", "Non-MIT", NaN, "N", NaN, NaN, NaN, "12-JUL-95", "D_CROSS_REG", "19-DEC-24"], ["WHIT", "Whi

## 子问题

["For subjects offered in the term with code '2025FA', show the subject ID, subject title, offering department name, number of enrolled students, term description, academic year, term start date, term end date, term parameter, and the minimum number of enrolled students over each offering department, ordered by offering department.", "For each department, what is the department code and the total number of units for all courses in that department, considering only departments whose total units are more than one standard deviation above the mean total units across all departments?", "For subjects offered in the term with code '2025FA', show the subject ID, subject title, offering department name, number of enrolled students, term description, academic year, term start date, term end date, term parameter, and the difference between the number of enrolled students for each subject and the minimum number of enrolled students in its offering department.", "For each department, what is the department code, department name, and the total number of units for all courses in that department, considering only departments whose total units are more than one standard deviation above the mean total units across all departments?"]
