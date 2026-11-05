# 查询任务（dw）

## 问题

For each administrative department in the School of Engineering corresponding to the Mechanical Engineering department, list the administrative department name, department code, minimum CIP program code, total number of degree-granting departments for courses, and the total number of such courses per administrative department. Additionally, for each such department, provide the department name, the coefficient of variation (using STDDEV only and never STDDEV_POP) of the total units of subjects offered by that department in the 2024 academic year, the average coefficient of variation (using STDDEV only and never STDDEV_POP) across all degree-granting departments (excluding Biology), and indicate whether the department's coefficient of variation (using STDDEV only and never STDDEV_POP) is 'ABOVE_AVERAGE', 'BELOW_AVERAGE', or 'AVERAGE' compared to the overall average. Present the results in the order of administrative department name and department code. Do not return any rounded answers.

## 库

dw

## 涉及表

["MIT_STUDENT_DIRECTORY", "SIS_DEPARTMENT", "COURSE_CATALOG_SUBJECT_OFFERED", "SIS_COURSE_DESCRIPTION", "SIS_ADMIN_DEPARTMENT"]

## 连接键

[["MIT_STUDENT_DIRECTORY.DEPARTMENT", "SIS_DEPARTMENT.DEPARTMENT_CODE"], ["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_CODE", "SIS_DEPARTMENT.DEPARTMENT_CODE"], ["SIS_COURSE_DESCRIPTION.DEPARTMENT", "SIS_DEPARTMENT.DEPARTMENT_CODE"], ["SIS_ADMIN_DEPARTMENT.SIS_ADMIN_DEPARTMENT_CODE", "SIS_DEPARTMENT.DEPARTMENT_CODE"]]

## 列映射

{"administrative department name": ["SIS_ADMIN_DEPARTMENT.SIS_ADMIN_DEPARTMENT_NAME"], "department code": ["SIS_DEPARTMENT.DEPARTMENT_CODE"], "minimum CIP program code": ["SIS_COURSE_DESCRIPTION.CIP_PROGRAM_CODE"], "total number of degree-granting departments for courses": ["SIS_DEPARTMENT.DEPARTMENT_CODE"], "total number of such courses per administrative department": ["SIS_COURSE_DESCRIPTION.COURSE"], "department name": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "coefficient of variation of the total units of subjects offered by that department in the 2024 academic year": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS", "SIS_DEPARTMENT.DEPARTMENT_CODE", "COURSE_CATALOG_SUBJECT_OFFERED.ACADEMIC_YEAR"], "average coefficient of variation across all degree-granting departments (excluding Biology)": ["SIS_DEPARTMENT.DEPARTMENT_CODE", "COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS"], "variation category": []}

## 领域知识

["\"degree-granting\" is predicated by \"TABLE.IS_DEGREE_GRANTING = 'Y'\"", "\"Mechanical Engineering\" is predicated by \"UPPER(TABLE.SIS_ADMIN_DEPARTMENT_NAME) = 'MECHANICAL ENGINEERING'\"", "\"Biology\" is predicated by \"TABLE.DEPARTMENT_CODE = '7'\"", "\"Mechanical Engineering\" is predicated by \"TABLE.DEPARTMENT = '2'\""]

## 表结构

### SIS_DEPARTMENT

- 列：["DEPARTMENT_CODE", "DEPARTMENT_NAME", "DEPARTMENT_FULL_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "DEPT_BUDGET_CODE", "IS_DEGREE_GRANTING", "DEPT_NAME_IN_COMMENCEMENT_BK", "SCHOOL_NAME_IN_COMMENCEMENT_BK", "DEPARTMENT_NAME_HISTORY", "DEPARTMENT_LAST_ACTIVITY_DATE", "DLC_KEY", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "VARCHAR2", "DATE"]
- 示例：[["HPM", "Health Policy & Management", "HPM-Health Policy & Management", "T", "Whitaker Coll of HST;  HST", 160000.0, "Y", NaN, "Whitaker College of Health Sciences and Technology", NaN, "17-FEB-94", "D_WHIT", "19-DEC-24"], ["NIE", "Non-Institute Exchange Student", "NIE-Non-Institute Exchange Student", "Z", "Non-MIT", NaN, "N", NaN, NaN, NaN, "12-JUL-95", "D_CROSS_REG", "19-DEC-24"], ["WHIT", "Whi

### COURSE_CATALOG_SUBJECT_OFFERED

- 列：["ACADEMIC_YEAR", "TERM_CODE", "SUBJECT_ID", "SUBJECT_CODE", "SUBJECT_NUMBER", "SOURCE_SUBJECT_ID", "PRINT_SUBJECT_ID", "IS_PRINTED_IN_BULLETIN", "DEPARTMENT_CODE", "DEPARTMENT_NAME", "EFFECTIVE_TERM_CODE", "SUBJECT_SHORT_TITLE", "SUBJECT_TITLE", "IS_VARIABLE_UNITS", "LECTURE_UNITS", "LAB_UNITS", "PREPARATION_UNITS", "TOTAL_UNITS", "DESIGN_UNITS", "GRADE_TYPE", "GRADE_TYPE_DESC", "GRADE_RULE", "GRADE_RULE_DESC", "HGN_CODE", "HGN_DESC", "HGN_EXCEPT", "GIR_ATTRIBUTE", "GIR_ATTRIBUTE_DESC", "COMM_REQ_ATTRIBUTE", "COMM_REQ_ATTRIBUTE_DESC", "TUITION_ATTRIBUTE", "TUITION_ATTRIBUTE_DESC", "WRITE_REQ_ATTRIBUTE", "WRITE_REQ_ATTRIBUTE_DESC", "SUPERVISOR_ATTRIBUTE", "SUPERVISOR_ATTRIBUTE_DESC", "PREREQUISITES", "SUBJECT_DESCRIPTION", "JOINT_SUBJECTS", "SCHOOL_WIDE_ELECTIVES", "MEETS_WITH_SUBJECTS", "EQUIVALENT_SUBJECTS", "IS_OFFERED_THIS_YEAR", "IS_OFFERED_FALL_TERM", "IS_OFFERED_IAP", "IS_OFFERED_SPRING_TERM", "IS_OFFERED_SUMMER_TERM", "FALL_INSTRUCTORS", "SPRING_INSTRUCTORS", "STATUS_CHANGE", "LAST_ACTIVITY_DATE", "WAREHOUSE_LOAD_DATE", "MASTER_SUBJECT_ID", "HASS_ATTRIBUTE", "HASS_ATTRIBUTE_DESC", "TERM_DURATION", "GLOBAL_REGIONS", "GLOBAL_COUNTRIES", "ON_LINE_PAGE_NUMBER", "SECTION_ID", "IS_MASTER_SECTION", "IS_LECTURE_SECTION", "IS_LAB_SECTION", "IS_RECITATION_SECTION", "IS_DESIGN_SECTION", "RESPONSIBLE_FACULTY_NAME", "RESPONSIBLE_FACULTY_MIT_ID", "MEET_TIME", "MEET_PLACE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2"]
- 示例：[[2006, "2006FA", "18.781", "18", "781", "18.781", "18.781", "Y", "18", "Mathematics", "2006FA", "Theory of Numbers", "Theory of Numbers", "N", 3, 0, 9, 12, 0, "L", "Letter graded", "N", "Not repeatable for credit", "U", "Undergraduate", NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, "An elementary introduction to number theory with no algebraic prerequisites. Primes, congruences, qua

### SIS_COURSE_DESCRIPTION

- 列：["SIS_COURSE_DESCRIPTION_KEY", "COURSE", "COURSE_DESCRIPTION", "COURSE_DESCRIPTION_LONG", "DEPARTMENT", "DEPARTMENT_NAME", "DEPT_NAME_IN_COMMENCEMENT_BK", "SCHOOL_NAME", "SCHOOL_NAME_IN_COMMENCEMENT_BK", "FROM_TERM", "FROM_TERM_DESCRIPTION", "THRU_TERM", "THRU_TERM_DESCRIPTION", "COURSE_OPTION", "COURSE_LEVEL", "CIP_PROGRAM_CODE", "IS_DEGREE_GRANTING", "DEFAULT_ULTIMATE_DEGREE", "GRADAUTE_LEVEL", "GRADUATE_LEVEL", "LAST_ACTIVITY_DATE", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "CHAR", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE"]
- 示例：[["5:CMI:U", "5 CMI", "Chemistry - Cambridge-MIT", "Chemistry", "5", "Chemistry", "Department of Chemistry", "Science", "School of Science", "2003FA", "Fall Term 2002-2003", "2004SU", "Summer Term 2004", "CMI", "U", 400501, "N", "NDG", NaN, NaN, "25-APR-05", "19-DEC-24"], ["6:AB:G", "6 AB", "Articial Intel & Dec Making", "Artificial Intelligence and Decision Making", "6", "Electrical Eng & Compute

## 子问题

["For each department, give the department name and the coefficient of variation of the total units of subjects offered by that department in the 2024 academic year, but only include departments that are degree-granting and exclude the Biology department (Course 7).", "What is the minimum CIP program code and the total number of departments for courses in the School of Engineering, considering only degree-granting departments, including the corresponding administrative department names, and specifically for the Mechanical Engineering department?", "For each degree-granting department (excluding the Biology department, Course 7), what is the coefficient of variation of the total units of subjects offered by that department in the 2024 academic year, and how does this compare to the average coefficient of variation across all degree-granting departments (excluding Biology)? Also, indicate whether the department's coefficient of variation is 'ABOVE_AVERAGE', 'BELOW_AVERAGE', or 'AVERAGE' compared to the overall average.", "List the administrative department names, the corresponding department codes, the minimum CIP program code, and the total number of degree-granting departments for courses in the School of Engineering, specifically for the Mechanical Engineering department, and show the total number of such courses per administrative department."]
