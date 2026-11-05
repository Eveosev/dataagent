# 查询任务（dw）

## 问题

For each department that grants degrees (excluding the Biology department), provide the department name, the average and variance of the total units for subjects offered by that department in the 2022 academic year, and, if the department is Mathematics, also include the school name, the average, variance, and standard deviation (using STDDEV only and never STDDEV_POP) of the total units of courses offered by the Mathematics department in that school, considering only courses with more than 0 total units. Present the results ordered by the variance of total units for subjects in 2022 in descending order. Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_DEPARTMENT", "COURSE_CATALOG_SUBJECT_OFFERED", "CIS_COURSE_CATALOG"]

## 连接键

[["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_CODE", "SIS_DEPARTMENT.DEPARTMENT_CODE"], ["CIS_COURSE_CATALOG.DEPARTMENT_CODE", "SIS_DEPARTMENT.DEPARTMENT_CODE"]]

## 列映射

{"department": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "department name": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "departments that grant degrees": ["SIS_DEPARTMENT.IS_DEGREE_GRANTING"], "Biology department": ["SIS_DEPARTMENT.DEPARTMENT_CODE"], "subjects offered by that department in the 2022 academic year": ["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_CODE", "COURSE_CATALOG_SUBJECT_OFFERED.ACADEMIC_YEAR"], "average of the total units for subjects": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS"], "variance of the total units for subjects": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS"], "Mathematics department": ["SIS_DEPARTMENT.DEPARTMENT_NAME", "SIS_DEPARTMENT.DEPARTMENT_CODE"], "school name": ["SIS_DEPARTMENT.SCHOOL_NAME"], "average of the total units of courses": ["CIS_COURSE_CATALOG.TOTAL_UNITS"], "variance of the total units of courses": ["CIS_COURSE_CATALOG.TOTAL_UNITS"], "standard deviation of the total units of courses": ["CIS_COURSE_CATALOG.TOTAL_UNITS"], "courses with more than 0 total units": ["CIS_COURSE_CATALOG.TOTAL_UNITS"]}

## 领域知识

["\"degree-granting\" is predicated by \"TABLE.IS_DEGREE_GRANTING = 'Y'\"", "\"math\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"Biology\" is predicated by \"TABLE.DEPARTMENT_CODE = '7'\"", "\"Course 18\" is predicated by \"TABLE.DEPARTMENT_CODE = '18'\""]

## 表结构

### COURSE_CATALOG_SUBJECT_OFFERED

- 列：["ACADEMIC_YEAR", "TERM_CODE", "SUBJECT_ID", "SUBJECT_CODE", "SUBJECT_NUMBER", "SOURCE_SUBJECT_ID", "PRINT_SUBJECT_ID", "IS_PRINTED_IN_BULLETIN", "DEPARTMENT_CODE", "DEPARTMENT_NAME", "EFFECTIVE_TERM_CODE", "SUBJECT_SHORT_TITLE", "SUBJECT_TITLE", "IS_VARIABLE_UNITS", "LECTURE_UNITS", "LAB_UNITS", "PREPARATION_UNITS", "TOTAL_UNITS", "DESIGN_UNITS", "GRADE_TYPE", "GRADE_TYPE_DESC", "GRADE_RULE", "GRADE_RULE_DESC", "HGN_CODE", "HGN_DESC", "HGN_EXCEPT", "GIR_ATTRIBUTE", "GIR_ATTRIBUTE_DESC", "COMM_REQ_ATTRIBUTE", "COMM_REQ_ATTRIBUTE_DESC", "TUITION_ATTRIBUTE", "TUITION_ATTRIBUTE_DESC", "WRITE_REQ_ATTRIBUTE", "WRITE_REQ_ATTRIBUTE_DESC", "SUPERVISOR_ATTRIBUTE", "SUPERVISOR_ATTRIBUTE_DESC", "PREREQUISITES", "SUBJECT_DESCRIPTION", "JOINT_SUBJECTS", "SCHOOL_WIDE_ELECTIVES", "MEETS_WITH_SUBJECTS", "EQUIVALENT_SUBJECTS", "IS_OFFERED_THIS_YEAR", "IS_OFFERED_FALL_TERM", "IS_OFFERED_IAP", "IS_OFFERED_SPRING_TERM", "IS_OFFERED_SUMMER_TERM", "FALL_INSTRUCTORS", "SPRING_INSTRUCTORS", "STATUS_CHANGE", "LAST_ACTIVITY_DATE", "WAREHOUSE_LOAD_DATE", "MASTER_SUBJECT_ID", "HASS_ATTRIBUTE", "HASS_ATTRIBUTE_DESC", "TERM_DURATION", "GLOBAL_REGIONS", "GLOBAL_COUNTRIES", "ON_LINE_PAGE_NUMBER", "SECTION_ID", "IS_MASTER_SECTION", "IS_LECTURE_SECTION", "IS_LAB_SECTION", "IS_RECITATION_SECTION", "IS_DESIGN_SECTION", "RESPONSIBLE_FACULTY_NAME", "RESPONSIBLE_FACULTY_MIT_ID", "MEET_TIME", "MEET_PLACE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2"]
- 示例：[[2006, "2006FA", "18.781", "18", "781", "18.781", "18.781", "Y", "18", "Mathematics", "2006FA", "Theory of Numbers", "Theory of Numbers", "N", 3, 0, 9, 12, 0, "L", "Letter graded", "N", "Not repeatable for credit", "U", "Undergraduate", NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, "An elementary introduction to number theory with no algebraic prerequisites. Primes, congruences, qua

## 子问题

["For each department, provide the department name and calculate the average and variance of the total units for subjects offered by that department in the 2022 academic year, but only include departments that grant degrees and exclude the Biology department (Course 7).", "For each school, what are the average, variance, and standard deviation of the total units of courses offered by each department in that school, considering only departments that grant degrees, courses with more than 0 total units, and only for the Mathematics department (Course 18)?"]
