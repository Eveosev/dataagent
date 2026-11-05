# 查询任务（dw）

## 问题

For each administrative department whose name is 'Mechanical Engineering' (Course 2), show the administrative department name, the coefficient of variation (using STDDEV only and never STDDEV_POP) of the total units for subjects offered by that department in the academic year 2024, the department name, and the coefficient of variation (using STDDEV only and never STDDEV_POP) of the total units for subjects offered by that department in regular academic terms (excluding 'Mathematics'), where the administrative department and department names match. Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_ADMIN_DEPARTMENT", "SIS_DEPARTMENT", "COURSE_CATALOG_SUBJECT_OFFERED", "ACADEMIC_TERMS"]

## 连接键

[["SIS_ADMIN_DEPARTMENT.SIS_ADMIN_DEPARTMENT_CODE", "SIS_DEPARTMENT.DEPARTMENT_CODE"], ["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_CODE", "SIS_DEPARTMENT.DEPARTMENT_CODE"], ["ACADEMIC_TERMS.TERM_CODE", "COURSE_CATALOG_SUBJECT_OFFERED.TERM_CODE"], ["ACADEMIC_TERMS.TERM_CODE", "COURSE_CATALOG_SUBJECT_OFFERED.EFFECTIVE_TERM_CODE"]]

## 列映射

{"administrative department name": ["SIS_ADMIN_DEPARTMENT.SIS_ADMIN_DEPARTMENT_NAME"], "coefficient of variation of the total units for subjects offered by that department in the academic year 2024": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS", "COURSE_CATALOG_SUBJECT_OFFERED.ACADEMIC_YEAR", "SIS_ADMIN_DEPARTMENT.SIS_ADMIN_DEPARTMENT_NAME"], "department name": ["SIS_DEPARTMENT.DEPARTMENT_NAME", "COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_NAME"], "coefficient of variation of the total units for subjects offered by that department in regular academic terms (excluding 'Mathematics')": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS", "COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_NAME", "ACADEMIC_TERMS.IS_REGULAR_TERM"], "administrative department and department names match": ["SIS_ADMIN_DEPARTMENT.SIS_ADMIN_DEPARTMENT_NAME", "SIS_DEPARTMENT.DEPARTMENT_NAME"], "Mechanical Engineering": ["SIS_ADMIN_DEPARTMENT.SIS_ADMIN_DEPARTMENT_NAME"]}

## 领域知识

["\"Mechanical Engineering\" is predicated by \"UPPER(TABLE.SIS_ADMIN_DEPARTMENT_NAME) = 'MECHANICAL ENGINEERING'\"", "\"math\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"Course 2\" is predicated by \"UPPER(TABLE.SIS_ADMIN_DEPARTMENT_NAME) = 'MECHANICAL ENGINEERING'\"", "\"Course 18\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\""]

## 表结构

### SIS_DEPARTMENT

- 列：["DEPARTMENT_CODE", "DEPARTMENT_NAME", "DEPARTMENT_FULL_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "DEPT_BUDGET_CODE", "IS_DEGREE_GRANTING", "DEPT_NAME_IN_COMMENCEMENT_BK", "SCHOOL_NAME_IN_COMMENCEMENT_BK", "DEPARTMENT_NAME_HISTORY", "DEPARTMENT_LAST_ACTIVITY_DATE", "DLC_KEY", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "VARCHAR2", "DATE"]
- 示例：[["HPM", "Health Policy & Management", "HPM-Health Policy & Management", "T", "Whitaker Coll of HST;  HST", 160000.0, "Y", NaN, "Whitaker College of Health Sciences and Technology", NaN, "17-FEB-94", "D_WHIT", "19-DEC-24"], ["NIE", "Non-Institute Exchange Student", "NIE-Non-Institute Exchange Student", "Z", "Non-MIT", NaN, "N", NaN, NaN, NaN, "12-JUL-95", "D_CROSS_REG", "19-DEC-24"], ["WHIT", "Whi

### COURSE_CATALOG_SUBJECT_OFFERED

- 列：["ACADEMIC_YEAR", "TERM_CODE", "SUBJECT_ID", "SUBJECT_CODE", "SUBJECT_NUMBER", "SOURCE_SUBJECT_ID", "PRINT_SUBJECT_ID", "IS_PRINTED_IN_BULLETIN", "DEPARTMENT_CODE", "DEPARTMENT_NAME", "EFFECTIVE_TERM_CODE", "SUBJECT_SHORT_TITLE", "SUBJECT_TITLE", "IS_VARIABLE_UNITS", "LECTURE_UNITS", "LAB_UNITS", "PREPARATION_UNITS", "TOTAL_UNITS", "DESIGN_UNITS", "GRADE_TYPE", "GRADE_TYPE_DESC", "GRADE_RULE", "GRADE_RULE_DESC", "HGN_CODE", "HGN_DESC", "HGN_EXCEPT", "GIR_ATTRIBUTE", "GIR_ATTRIBUTE_DESC", "COMM_REQ_ATTRIBUTE", "COMM_REQ_ATTRIBUTE_DESC", "TUITION_ATTRIBUTE", "TUITION_ATTRIBUTE_DESC", "WRITE_REQ_ATTRIBUTE", "WRITE_REQ_ATTRIBUTE_DESC", "SUPERVISOR_ATTRIBUTE", "SUPERVISOR_ATTRIBUTE_DESC", "PREREQUISITES", "SUBJECT_DESCRIPTION", "JOINT_SUBJECTS", "SCHOOL_WIDE_ELECTIVES", "MEETS_WITH_SUBJECTS", "EQUIVALENT_SUBJECTS", "IS_OFFERED_THIS_YEAR", "IS_OFFERED_FALL_TERM", "IS_OFFERED_IAP", "IS_OFFERED_SPRING_TERM", "IS_OFFERED_SUMMER_TERM", "FALL_INSTRUCTORS", "SPRING_INSTRUCTORS", "STATUS_CHANGE", "LAST_ACTIVITY_DATE", "WAREHOUSE_LOAD_DATE", "MASTER_SUBJECT_ID", "HASS_ATTRIBUTE", "HASS_ATTRIBUTE_DESC", "TERM_DURATION", "GLOBAL_REGIONS", "GLOBAL_COUNTRIES", "ON_LINE_PAGE_NUMBER", "SECTION_ID", "IS_MASTER_SECTION", "IS_LECTURE_SECTION", "IS_LAB_SECTION", "IS_RECITATION_SECTION", "IS_DESIGN_SECTION", "RESPONSIBLE_FACULTY_NAME", "RESPONSIBLE_FACULTY_MIT_ID", "MEET_TIME", "MEET_PLACE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2"]
- 示例：[[2006, "2006FA", "18.781", "18", "781", "18.781", "18.781", "Y", "18", "Mathematics", "2006FA", "Theory of Numbers", "Theory of Numbers", "N", 3, 0, 9, 12, 0, "L", "Letter graded", "N", "Not repeatable for credit", "U", "Undergraduate", NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, "An elementary introduction to number theory with no algebraic prerequisites. Primes, congruences, qua

## 子问题

["For each administrative department, give the administrative department name and the coefficient of variation of the total units for subjects offered by that department in the academic year 2024, but only include departments whose name is 'Mechanical Engineering' (Course 2).", "For each department, give the department name and the coefficient of variation of the total units for subjects offered in regular academic terms, but only include departments that are not 'Mathematics' (Course 18)."]
