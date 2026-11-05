# 查询任务（dw）

## 问题

For each school and department, list the school name, department name, average total units, range of total units, and variance of total units for degree-granting subjects offered in the 2022 academic year, excluding the Mathematics department (Course 18), and include a grand total for all departments in each school (with department name as null). Also, for each department in the School of Engineering (excluding Management) that grants degrees and has a total student enrollment in its offered courses greater than 50, list the department name, total enrollment, the most popular course by enrollment, and its enrollment count. For each result, indicate the reason for inclusion as either 'UnitsStats' or 'EnrollmentStats'. The columns should be: school name, department name, average total units, total units range, total units variance, total enrollment, most popular course, course enrollment, and reason. Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_SUBJECT_CODE", "SIS_COURSE_DESCRIPTION", "COURSE_CATALOG_SUBJECT_OFFERED", "SIS_DEPARTMENT", "TIP_SUBJECT_OFFERED", "STUDENT_DEPARTMENT"]

## 连接键

[["SIS_COURSE_DESCRIPTION.COURSE", "SIS_SUBJECT_CODE.COURSE_NUMBER"], ["COURSE_CATALOG_SUBJECT_OFFERED.SUBJECT_CODE", "SIS_COURSE_DESCRIPTION.COURSE"], ["SIS_DEPARTMENT.DEPARTMENT_CODE", "TIP_SUBJECT_OFFERED.OFFER_DEPT_CODE"], ["STUDENT_DEPARTMENT.DEPARTMENT_CODE", "TIP_SUBJECT_OFFERED.OFFER_DEPT_CODE"]]

## 列映射

{"school name": ["SIS_COURSE_DESCRIPTION.SCHOOL_NAME", "SIS_DEPARTMENT.SCHOOL_NAME"], "department name": ["SIS_COURSE_DESCRIPTION.DEPARTMENT_NAME", "SIS_DEPARTMENT.DEPARTMENT_NAME"], "average total units": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS"], "total units range": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS"], "total units variance": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS"], "degree-granting subjects": ["SIS_COURSE_DESCRIPTION.IS_DEGREE_GRANTING", "SIS_DEPARTMENT.IS_DEGREE_GRANTING"], "2022 academic year": ["COURSE_CATALOG_SUBJECT_OFFERED.ACADEMIC_YEAR"], "Mathematics department (Course 18)": ["SIS_COURSE_DESCRIPTION.DEPARTMENT_NAME", "SIS_COURSE_DESCRIPTION.DEPARTMENT"], "School of Engineering": ["SIS_DEPARTMENT.SCHOOL_NAME"], "Management": ["SIS_DEPARTMENT.DEPARTMENT_CODE"], "total student enrollment": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "most popular course": ["TIP_SUBJECT_OFFERED.SUBJECT_TITLE"], "course enrollment": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "reason": []}

## 领域知识

["\"math\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"degree-granting\" is predicated by \"TABLE.IS_DEGREE_GRANTING = 'Y'\"", "\"Course 18\" is predicated by \"TABLE.DEPARTMENT = '18'\"", "\"Course 15\" is predicated by \"UPPER(TABLE.SIS_ADMIN_DEPARTMENT_NAME) = 'MANAGEMENT'\"", "\"Management\" is predicated by \"TABLE.DEPARTMENT_CODE = '15'\""]

## 表结构

### SIS_COURSE_DESCRIPTION

- 列：["SIS_COURSE_DESCRIPTION_KEY", "COURSE", "COURSE_DESCRIPTION", "COURSE_DESCRIPTION_LONG", "DEPARTMENT", "DEPARTMENT_NAME", "DEPT_NAME_IN_COMMENCEMENT_BK", "SCHOOL_NAME", "SCHOOL_NAME_IN_COMMENCEMENT_BK", "FROM_TERM", "FROM_TERM_DESCRIPTION", "THRU_TERM", "THRU_TERM_DESCRIPTION", "COURSE_OPTION", "COURSE_LEVEL", "CIP_PROGRAM_CODE", "IS_DEGREE_GRANTING", "DEFAULT_ULTIMATE_DEGREE", "GRADAUTE_LEVEL", "GRADUATE_LEVEL", "LAST_ACTIVITY_DATE", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "CHAR", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE"]
- 示例：[["5:CMI:U", "5 CMI", "Chemistry - Cambridge-MIT", "Chemistry", "5", "Chemistry", "Department of Chemistry", "Science", "School of Science", "2003FA", "Fall Term 2002-2003", "2004SU", "Summer Term 2004", "CMI", "U", 400501, "N", "NDG", NaN, NaN, "25-APR-05", "19-DEC-24"], ["6:AB:G", "6 AB", "Articial Intel & Dec Making", "Artificial Intelligence and Decision Making", "6", "Electrical Eng & Compute

### COURSE_CATALOG_SUBJECT_OFFERED

- 列：["ACADEMIC_YEAR", "TERM_CODE", "SUBJECT_ID", "SUBJECT_CODE", "SUBJECT_NUMBER", "SOURCE_SUBJECT_ID", "PRINT_SUBJECT_ID", "IS_PRINTED_IN_BULLETIN", "DEPARTMENT_CODE", "DEPARTMENT_NAME", "EFFECTIVE_TERM_CODE", "SUBJECT_SHORT_TITLE", "SUBJECT_TITLE", "IS_VARIABLE_UNITS", "LECTURE_UNITS", "LAB_UNITS", "PREPARATION_UNITS", "TOTAL_UNITS", "DESIGN_UNITS", "GRADE_TYPE", "GRADE_TYPE_DESC", "GRADE_RULE", "GRADE_RULE_DESC", "HGN_CODE", "HGN_DESC", "HGN_EXCEPT", "GIR_ATTRIBUTE", "GIR_ATTRIBUTE_DESC", "COMM_REQ_ATTRIBUTE", "COMM_REQ_ATTRIBUTE_DESC", "TUITION_ATTRIBUTE", "TUITION_ATTRIBUTE_DESC", "WRITE_REQ_ATTRIBUTE", "WRITE_REQ_ATTRIBUTE_DESC", "SUPERVISOR_ATTRIBUTE", "SUPERVISOR_ATTRIBUTE_DESC", "PREREQUISITES", "SUBJECT_DESCRIPTION", "JOINT_SUBJECTS", "SCHOOL_WIDE_ELECTIVES", "MEETS_WITH_SUBJECTS", "EQUIVALENT_SUBJECTS", "IS_OFFERED_THIS_YEAR", "IS_OFFERED_FALL_TERM", "IS_OFFERED_IAP", "IS_OFFERED_SPRING_TERM", "IS_OFFERED_SUMMER_TERM", "FALL_INSTRUCTORS", "SPRING_INSTRUCTORS", "STATUS_CHANGE", "LAST_ACTIVITY_DATE", "WAREHOUSE_LOAD_DATE", "MASTER_SUBJECT_ID", "HASS_ATTRIBUTE", "HASS_ATTRIBUTE_DESC", "TERM_DURATION", "GLOBAL_REGIONS", "GLOBAL_COUNTRIES", "ON_LINE_PAGE_NUMBER", "SECTION_ID", "IS_MASTER_SECTION", "IS_LECTURE_SECTION", "IS_LAB_SECTION", "IS_RECITATION_SECTION", "IS_DESIGN_SECTION", "RESPONSIBLE_FACULTY_NAME", "RESPONSIBLE_FACULTY_MIT_ID", "MEET_TIME", "MEET_PLACE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2"]
- 示例：[[2006, "2006FA", "18.781", "18", "781", "18.781", "18.781", "Y", "18", "Mathematics", "2006FA", "Theory of Numbers", "Theory of Numbers", "N", 3, 0, 9, 12, 0, "L", "Letter graded", "N", "Not repeatable for credit", "U", "Undergraduate", NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, "An elementary introduction to number theory with no algebraic prerequisites. Primes, congruences, qua

### SIS_DEPARTMENT

- 列：["DEPARTMENT_CODE", "DEPARTMENT_NAME", "DEPARTMENT_FULL_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "DEPT_BUDGET_CODE", "IS_DEGREE_GRANTING", "DEPT_NAME_IN_COMMENCEMENT_BK", "SCHOOL_NAME_IN_COMMENCEMENT_BK", "DEPARTMENT_NAME_HISTORY", "DEPARTMENT_LAST_ACTIVITY_DATE", "DLC_KEY", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "VARCHAR2", "DATE"]
- 示例：[["HPM", "Health Policy & Management", "HPM-Health Policy & Management", "T", "Whitaker Coll of HST;  HST", 160000.0, "Y", NaN, "Whitaker College of Health Sciences and Technology", NaN, "17-FEB-94", "D_WHIT", "19-DEC-24"], ["NIE", "Non-Institute Exchange Student", "NIE-Non-Institute Exchange Student", "Z", "Non-MIT", NaN, "N", NaN, NaN, NaN, "12-JUL-95", "D_CROSS_REG", "19-DEC-24"], ["WHIT", "Whi

### TIP_SUBJECT_OFFERED

- 列：["TIP_SUBJECT_OFFERED_KEY", "TERM_CODE", "IS_NO_COURSE_MATERIAL", "MASTER_COURSE_NUMBER", "MASTER_COURSE_NUMBER_SORT", "MASTER_COURSE_NUMBER_DESC", "MASTER_SUBJECT_ID", "MASTER_SUBJECT_ID_SORT", "COURSE_NUMBER", "COURSE_NUMBER_SORT", "COURSE_NUMBER_DESC", "SUBJECT_ID", "SUBJECT_ID_SORT", "SUBJECT_TITLE", "OFFER_DEPT_CODE", "OFFER_DEPT_NAME", "OFFER_SCHOOL_NAME", "RESPONSIBLE_FACULTY_NAME", "RESPONSIBLE_FACULTY_MIT_ID", "NUM_ENROLLED_STUDENTS", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "DATE"]
- 示例：[["0166830002017JA", "2017JA", NaN, "16", " 16", "Aeronautics and Astronautics", "16.683", "16.683", "16", " 16", "Aeronautics and Astronautics", "16.683", " 16.683", "Sem Aeronautics & Astronautics", "16", "Aeronautics and Astronautics", "Engineering", "Branch, Claude", 910358479.0, 0, "20-DEC-24"], ["21M3410002005FA", "2005FA", NaN, "21M", "21M", "Music and Theater Arts", "21M.341", "21M.341", "

## 子问题

["For each department, give the department name and calculate the average, range, and variance of the total units for subjects offered in the 2022 academic year that are degree granting, but only include departments that are not 'Mathematics' (Course 18).", "For each department, give the department name and calculate the total number of students enrolled in courses offered by that department in the School of Engineering, where the total number of enrolled students is greater than 50, and restrict the results to departments that grant degrees and exclude the Department of Management (Course 15).", "For each school, list the school name, the department name, and calculate the average, range, and variance of the total units for subjects offered in the 2022 academic year that are degree granting, but only include departments that are not 'Mathematics' (Course 18). For each school, also include a grand total for all departments in that school in the format of (school name, null, aggregated values).", "Among departments in the School of Engineering that grant degrees (excluding the Department of Management), which departments have a total student enrollment in their offered courses greater than 50, and for each such department, what is the most popular course (by enrollment) they offer and its enrollment count?"]
