# 查询任务（dw）

## 问题

For each Mathematics department (Course 18) that has a minimum number of enrolled students between 1 and 10 or a department budget code of at least 90000, and a department budget code between 90000 and 200000, list the department code, department name, the minimum number of enrolled students, the average department budget code, the most common course number offered by that department (with the count of offerings for that course number), and for each subject offered in 2022 that is printed in the bulletin and whose total units exceed the average total units for Mathematics subjects offered in 2022, provide the subject title, total units, and the row number within a window of 2 preceding and 1 following rows ordered by subject title. Do not return any rounded answers.

## 库

dw

## 涉及表

["TIP_SUBJECT_OFFERED", "SIS_DEPARTMENT", "SIS_SUBJECT_CODE", "COURSE_CATALOG_SUBJECT_OFFERED", "CIS_COURSE_CATALOG"]

## 连接键

[["SIS_DEPARTMENT.DEPARTMENT_CODE", "TIP_SUBJECT_OFFERED.OFFER_DEPT_CODE"], ["SIS_DEPARTMENT.DEPARTMENT_CODE", "SIS_SUBJECT_CODE.DEPARTMENT_CODE"], ["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_CODE", "SIS_DEPARTMENT.DEPARTMENT_CODE"], ["CIS_COURSE_CATALOG.DEPARTMENT_CODE", "SIS_DEPARTMENT.DEPARTMENT_CODE"]]

## 列映射

{"Mathematics department": ["SIS_DEPARTMENT.DEPARTMENT_NAME", "SIS_DEPARTMENT.DEPARTMENT_CODE"], "Course 18": ["SIS_DEPARTMENT.DEPARTMENT_CODE", "COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_CODE"], "minimum number of enrolled students": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "department budget code": ["SIS_DEPARTMENT.DEPT_BUDGET_CODE"], "department code": ["SIS_DEPARTMENT.DEPARTMENT_CODE"], "department name": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "average department budget code": ["SIS_DEPARTMENT.DEPT_BUDGET_CODE"], "most common course number": ["TIP_SUBJECT_OFFERED.COURSE_NUMBER"], "count of offerings for that course number": ["TIP_SUBJECT_OFFERED.COURSE_NUMBER"], "subject offered in 2022": ["COURSE_CATALOG_SUBJECT_OFFERED.ACADEMIC_YEAR"], "printed in the bulletin": ["COURSE_CATALOG_SUBJECT_OFFERED.IS_PRINTED_IN_BULLETIN"], "subject title": ["COURSE_CATALOG_SUBJECT_OFFERED.SUBJECT_TITLE"], "total units": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS"], "average total units for Mathematics subjects offered in 2022": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS", "COURSE_CATALOG_SUBJECT_OFFERED.ACADEMIC_YEAR", "COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_CODE"], "row number within a window of 2 preceding and 1 following rows ordered by subject title": ["COURSE_CATALOG_SUBJECT_OFFERED.SUBJECT_TITLE"]}

## 领域知识

["\"math\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"Course 18\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"Course 18\" is predicated by \"TABLE.DEPARTMENT_CODE = '18'\""]

## 表结构

### SIS_DEPARTMENT

- 列：["DEPARTMENT_CODE", "DEPARTMENT_NAME", "DEPARTMENT_FULL_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "DEPT_BUDGET_CODE", "IS_DEGREE_GRANTING", "DEPT_NAME_IN_COMMENCEMENT_BK", "SCHOOL_NAME_IN_COMMENCEMENT_BK", "DEPARTMENT_NAME_HISTORY", "DEPARTMENT_LAST_ACTIVITY_DATE", "DLC_KEY", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "VARCHAR2", "DATE"]
- 示例：[["HPM", "Health Policy & Management", "HPM-Health Policy & Management", "T", "Whitaker Coll of HST;  HST", 160000.0, "Y", NaN, "Whitaker College of Health Sciences and Technology", NaN, "17-FEB-94", "D_WHIT", "19-DEC-24"], ["NIE", "Non-Institute Exchange Student", "NIE-Non-Institute Exchange Student", "Z", "Non-MIT", NaN, "N", NaN, NaN, NaN, "12-JUL-95", "D_CROSS_REG", "19-DEC-24"], ["WHIT", "Whi

### SIS_SUBJECT_CODE

- 列：["COURSE_NUMBER", "SUBJECT_CODE", "SUBJECT_CODE_DESC", "DEPARTMENT_CODE", "DEPARTMENT_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE"]
- 示例：[["S0", "S0", NaN, NaN, NaN, NaN, NaN, "19-DEC-24"], ["OGE", "OGE", "Office of Graduate Education", "OGE", "Office of Graduate Education", "Y", "MIT, academic", "19-DEC-24"], ["MCH", "MCH", "Photography", "NIA", "Non-Institute-MFA/MCA", "Z", "Non-MIT", "19-DEC-24"]]

### COURSE_CATALOG_SUBJECT_OFFERED

- 列：["ACADEMIC_YEAR", "TERM_CODE", "SUBJECT_ID", "SUBJECT_CODE", "SUBJECT_NUMBER", "SOURCE_SUBJECT_ID", "PRINT_SUBJECT_ID", "IS_PRINTED_IN_BULLETIN", "DEPARTMENT_CODE", "DEPARTMENT_NAME", "EFFECTIVE_TERM_CODE", "SUBJECT_SHORT_TITLE", "SUBJECT_TITLE", "IS_VARIABLE_UNITS", "LECTURE_UNITS", "LAB_UNITS", "PREPARATION_UNITS", "TOTAL_UNITS", "DESIGN_UNITS", "GRADE_TYPE", "GRADE_TYPE_DESC", "GRADE_RULE", "GRADE_RULE_DESC", "HGN_CODE", "HGN_DESC", "HGN_EXCEPT", "GIR_ATTRIBUTE", "GIR_ATTRIBUTE_DESC", "COMM_REQ_ATTRIBUTE", "COMM_REQ_ATTRIBUTE_DESC", "TUITION_ATTRIBUTE", "TUITION_ATTRIBUTE_DESC", "WRITE_REQ_ATTRIBUTE", "WRITE_REQ_ATTRIBUTE_DESC", "SUPERVISOR_ATTRIBUTE", "SUPERVISOR_ATTRIBUTE_DESC", "PREREQUISITES", "SUBJECT_DESCRIPTION", "JOINT_SUBJECTS", "SCHOOL_WIDE_ELECTIVES", "MEETS_WITH_SUBJECTS", "EQUIVALENT_SUBJECTS", "IS_OFFERED_THIS_YEAR", "IS_OFFERED_FALL_TERM", "IS_OFFERED_IAP", "IS_OFFERED_SPRING_TERM", "IS_OFFERED_SUMMER_TERM", "FALL_INSTRUCTORS", "SPRING_INSTRUCTORS", "STATUS_CHANGE", "LAST_ACTIVITY_DATE", "WAREHOUSE_LOAD_DATE", "MASTER_SUBJECT_ID", "HASS_ATTRIBUTE", "HASS_ATTRIBUTE_DESC", "TERM_DURATION", "GLOBAL_REGIONS", "GLOBAL_COUNTRIES", "ON_LINE_PAGE_NUMBER", "SECTION_ID", "IS_MASTER_SECTION", "IS_LECTURE_SECTION", "IS_LAB_SECTION", "IS_RECITATION_SECTION", "IS_DESIGN_SECTION", "RESPONSIBLE_FACULTY_NAME", "RESPONSIBLE_FACULTY_MIT_ID", "MEET_TIME", "MEET_PLACE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2"]
- 示例：[[2006, "2006FA", "18.781", "18", "781", "18.781", "18.781", "Y", "18", "Mathematics", "2006FA", "Theory of Numbers", "Theory of Numbers", "N", 3, 0, 9, 12, 0, "L", "Letter graded", "N", "Not repeatable for credit", "U", "Undergraduate", NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, "An elementary introduction to number theory with no algebraic prerequisites. Primes, congruences, qua

## 子问题

["For each department give the department code, the department name, the minimum number of enrolled students and the average department budget code, where the number of enrolled students is between 1 and 10 or the department budget code is at least 90000, and the department budget code is between 90000 and 200000, for departments that are Mathematics (Course 18)?", "For subjects offered in the academic year 2022 that are printed in the bulletin and belong to the Mathematics department (Course 18), show the subject title, department name, total units, and assign row numbers within a window of 2 preceding and 1 following rows ordered by subject title.", "For each department, list the department code, department name, the minimum number of enrolled students, the average department budget code, and the most common course number offered by that department (along with the count of offerings for that course number), where the number of enrolled students is between 1 and 10 or the department budget code is at least 90000, and the department budget code is between 90000 and 200000, for departments that are Mathematics (Course 18).", "For subjects offered in the academic year 2022 that are printed in the bulletin and belong to the Mathematics department (Course 18), show the subject title, department name, total units, and assign row numbers within a window of 2 preceding and 1 following rows ordered by subject title. Additionally, only include those subjects whose total units exceed the average total units for Mathematics subjects offered in 2022 and printed in the bulletin."]
