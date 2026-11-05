# 查询任务（dw）

## 问题

For each administrative department and its corresponding academic department whose name is "Political Science" (Course 17), what is the maximum total units of any subject offered by that department in the academic year 2024, what is the name of the subject with that maximum total units, and what are the average, range, and variance of the number of enrolled students in subjects offered by that department (considering only subjects with more than 0 enrolled students and where the department is degree granting, but excluding the Mathematics department)? Additionally, for each administrative department and academic department pair, include a grand total row for all such pairs in the format of (null, null, null, null, average enrolled students, range of enrolled students, variance of enrolled students). List the administrative department, academic department, maximum total units, subject title with maximum total units, average enrolled students, range of enrolled students, and variance of enrolled students, in that order. Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_ADMIN_DEPARTMENT", "SIS_DEPARTMENT", "COURSE_CATALOG_SUBJECT_OFFERED", "TIP_SUBJECT_OFFERED", "SIS_SUBJECT_CODE"]

## 连接键

[["SIS_ADMIN_DEPARTMENT.SIS_ADMIN_DEPARTMENT_CODE", "SIS_DEPARTMENT.DEPARTMENT_CODE"], ["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_CODE", "SIS_DEPARTMENT.DEPARTMENT_CODE"], ["SIS_DEPARTMENT.DEPARTMENT_CODE", "TIP_SUBJECT_OFFERED.OFFER_DEPT_CODE"], ["SIS_DEPARTMENT.DEPARTMENT_CODE", "SIS_SUBJECT_CODE.DEPARTMENT_CODE"]]

## 列映射

{"administrative department": ["SIS_ADMIN_DEPARTMENT.SIS_ADMIN_DEPARTMENT_NAME"], "academic department": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "maximum total units": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS"], "subject title with maximum total units": ["COURSE_CATALOG_SUBJECT_OFFERED.SUBJECT_TITLE"], "average enrolled students": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "range of enrolled students": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "variance of enrolled students": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "Political Science": ["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_NAME", "COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_CODE"], "academic year 2024": ["COURSE_CATALOG_SUBJECT_OFFERED.ACADEMIC_YEAR"], "degree granting": ["SIS_DEPARTMENT.IS_DEGREE_GRANTING"], "Mathematics": ["SIS_DEPARTMENT.DEPARTMENT_NAME"]}

## 领域知识

["\"Political Science\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Political Science'\"", "\"math\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"Course 17\" is predicated by \"TABLE.DEPARTMENT_CODE = '17'\"", "\"Course 18\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"Mathematics\" is predicated by \"TABLE.DEPARTMENT_CODE = '18'\""]

## 表结构

### SIS_DEPARTMENT

- 列：["DEPARTMENT_CODE", "DEPARTMENT_NAME", "DEPARTMENT_FULL_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "DEPT_BUDGET_CODE", "IS_DEGREE_GRANTING", "DEPT_NAME_IN_COMMENCEMENT_BK", "SCHOOL_NAME_IN_COMMENCEMENT_BK", "DEPARTMENT_NAME_HISTORY", "DEPARTMENT_LAST_ACTIVITY_DATE", "DLC_KEY", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "VARCHAR2", "DATE"]
- 示例：[["HPM", "Health Policy & Management", "HPM-Health Policy & Management", "T", "Whitaker Coll of HST;  HST", 160000.0, "Y", NaN, "Whitaker College of Health Sciences and Technology", NaN, "17-FEB-94", "D_WHIT", "19-DEC-24"], ["NIE", "Non-Institute Exchange Student", "NIE-Non-Institute Exchange Student", "Z", "Non-MIT", NaN, "N", NaN, NaN, NaN, "12-JUL-95", "D_CROSS_REG", "19-DEC-24"], ["WHIT", "Whi

### COURSE_CATALOG_SUBJECT_OFFERED

- 列：["ACADEMIC_YEAR", "TERM_CODE", "SUBJECT_ID", "SUBJECT_CODE", "SUBJECT_NUMBER", "SOURCE_SUBJECT_ID", "PRINT_SUBJECT_ID", "IS_PRINTED_IN_BULLETIN", "DEPARTMENT_CODE", "DEPARTMENT_NAME", "EFFECTIVE_TERM_CODE", "SUBJECT_SHORT_TITLE", "SUBJECT_TITLE", "IS_VARIABLE_UNITS", "LECTURE_UNITS", "LAB_UNITS", "PREPARATION_UNITS", "TOTAL_UNITS", "DESIGN_UNITS", "GRADE_TYPE", "GRADE_TYPE_DESC", "GRADE_RULE", "GRADE_RULE_DESC", "HGN_CODE", "HGN_DESC", "HGN_EXCEPT", "GIR_ATTRIBUTE", "GIR_ATTRIBUTE_DESC", "COMM_REQ_ATTRIBUTE", "COMM_REQ_ATTRIBUTE_DESC", "TUITION_ATTRIBUTE", "TUITION_ATTRIBUTE_DESC", "WRITE_REQ_ATTRIBUTE", "WRITE_REQ_ATTRIBUTE_DESC", "SUPERVISOR_ATTRIBUTE", "SUPERVISOR_ATTRIBUTE_DESC", "PREREQUISITES", "SUBJECT_DESCRIPTION", "JOINT_SUBJECTS", "SCHOOL_WIDE_ELECTIVES", "MEETS_WITH_SUBJECTS", "EQUIVALENT_SUBJECTS", "IS_OFFERED_THIS_YEAR", "IS_OFFERED_FALL_TERM", "IS_OFFERED_IAP", "IS_OFFERED_SPRING_TERM", "IS_OFFERED_SUMMER_TERM", "FALL_INSTRUCTORS", "SPRING_INSTRUCTORS", "STATUS_CHANGE", "LAST_ACTIVITY_DATE", "WAREHOUSE_LOAD_DATE", "MASTER_SUBJECT_ID", "HASS_ATTRIBUTE", "HASS_ATTRIBUTE_DESC", "TERM_DURATION", "GLOBAL_REGIONS", "GLOBAL_COUNTRIES", "ON_LINE_PAGE_NUMBER", "SECTION_ID", "IS_MASTER_SECTION", "IS_LECTURE_SECTION", "IS_LAB_SECTION", "IS_RECITATION_SECTION", "IS_DESIGN_SECTION", "RESPONSIBLE_FACULTY_NAME", "RESPONSIBLE_FACULTY_MIT_ID", "MEET_TIME", "MEET_PLACE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2"]
- 示例：[[2006, "2006FA", "18.781", "18", "781", "18.781", "18.781", "Y", "18", "Mathematics", "2006FA", "Theory of Numbers", "Theory of Numbers", "N", 3, 0, 9, 12, 0, "L", "Letter graded", "N", "Not repeatable for credit", "U", "Undergraduate", NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, "An elementary introduction to number theory with no algebraic prerequisites. Primes, congruences, qua

### TIP_SUBJECT_OFFERED

- 列：["TIP_SUBJECT_OFFERED_KEY", "TERM_CODE", "IS_NO_COURSE_MATERIAL", "MASTER_COURSE_NUMBER", "MASTER_COURSE_NUMBER_SORT", "MASTER_COURSE_NUMBER_DESC", "MASTER_SUBJECT_ID", "MASTER_SUBJECT_ID_SORT", "COURSE_NUMBER", "COURSE_NUMBER_SORT", "COURSE_NUMBER_DESC", "SUBJECT_ID", "SUBJECT_ID_SORT", "SUBJECT_TITLE", "OFFER_DEPT_CODE", "OFFER_DEPT_NAME", "OFFER_SCHOOL_NAME", "RESPONSIBLE_FACULTY_NAME", "RESPONSIBLE_FACULTY_MIT_ID", "NUM_ENROLLED_STUDENTS", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "DATE"]
- 示例：[["0166830002017JA", "2017JA", NaN, "16", " 16", "Aeronautics and Astronautics", "16.683", "16.683", "16", " 16", "Aeronautics and Astronautics", "16.683", " 16.683", "Sem Aeronautics & Astronautics", "16", "Aeronautics and Astronautics", "Engineering", "Branch, Claude", 910358479.0, 0, "20-DEC-24"], ["21M3410002005FA", "2005FA", NaN, "21M", "21M", "Music and Theater Arts", "21M.341", "21M.341", "

## 子问题

["For each administrative department and its corresponding academic department, what is the maximum total units of any subject offered by that department in the academic year 2024, and what is the name of the subject with that maximum total units, only for departments whose name is \"Political Science\" (Course 17), and only include results where the maximum total units is greater than 9?", "For each department, give the department name and calculate the average, range, and variance of the number of enrolled students in subjects offered by that department, considering only subjects with more than 0 enrolled students and where the department is degree granting, but exclude the Mathematics department (Course 18).", "For each administrative department and its corresponding academic department whose name is \"Political Science\" (Course 17), what is the maximum total units of any subject offered by that department in the academic year 2024, what is the name of the subject with that maximum total units, and what are the average, range, and variance of the number of enrolled students in subjects offered by that department (considering only subjects with more than 0 enrolled students and where the department is degree granting, but excluding the Mathematics department), only including results where the maximum total units is greater than 9? List the administrative department, academic department, maximum total units, subject title with maximum total units, average enrolled students, range of enrolled students, and variance of enrolled students, in that order."]
