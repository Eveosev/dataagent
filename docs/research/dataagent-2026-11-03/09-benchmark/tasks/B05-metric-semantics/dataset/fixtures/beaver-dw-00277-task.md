# 查询任务（dw）

## 问题

For subjects offered by departments in the School of Engineering with a total of at least 6 units, where the running sum of total units within each grade type exceeds 12 units, show the subject code, subject title, department name, and the running sum of total units within each grade type. For each such subject, for each building and floor where the subject is scheduled (based on the room's meet place), show the building key, the floor key, and the total coefficient of variation (using STDDEV only and never STDDEV_POP) of the area of rooms located on that floor (including grand totals for all floors per building). Order the results by subject code, building key, and floor key. Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_DEPARTMENT", "COURSE_CATALOG_SUBJECT_OFFERED", "FCLT_FLOOR", "FCLT_ROOMS"]

## 连接键

[["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_CODE", "SIS_DEPARTMENT.DEPARTMENT_CODE"], ["FCLT_FLOOR.FCLT_FLOOR_KEY", "FCLT_ROOMS.FCLT_FLOOR_KEY"]]

## 列映射

{"subjects": ["COURSE_CATALOG_SUBJECT_OFFERED.SUBJECT_CODE", "COURSE_CATALOG_SUBJECT_OFFERED.SUBJECT_TITLE"], "subject code": ["COURSE_CATALOG_SUBJECT_OFFERED.SUBJECT_CODE"], "subject title": ["COURSE_CATALOG_SUBJECT_OFFERED.SUBJECT_TITLE"], "department name": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "School of Engineering": ["SIS_DEPARTMENT.SCHOOL_NAME"], "total units": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS"], "grade type": ["COURSE_CATALOG_SUBJECT_OFFERED.GRADE_TYPE"], "running sum of total units": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS", "COURSE_CATALOG_SUBJECT_OFFERED.GRADE_TYPE", "COURSE_CATALOG_SUBJECT_OFFERED.SUBJECT_CODE"], "building key": ["FCLT_FLOOR.FCLT_BUILDING_KEY"], "floor key": ["FCLT_FLOOR.FCLT_FLOOR_KEY"], "room's meet place": ["COURSE_CATALOG_SUBJECT_OFFERED.MEET_PLACE", "FCLT_ROOMS.FCLT_ROOM_KEY"], "area of rooms": ["FCLT_ROOMS.AREA"], "coefficient of variation": ["FCLT_ROOMS.AREA"], "total coefficient of variation": ["FCLT_ROOMS.AREA"]}

## 领域知识

[]

## 表结构

### COURSE_CATALOG_SUBJECT_OFFERED

- 列：["ACADEMIC_YEAR", "TERM_CODE", "SUBJECT_ID", "SUBJECT_CODE", "SUBJECT_NUMBER", "SOURCE_SUBJECT_ID", "PRINT_SUBJECT_ID", "IS_PRINTED_IN_BULLETIN", "DEPARTMENT_CODE", "DEPARTMENT_NAME", "EFFECTIVE_TERM_CODE", "SUBJECT_SHORT_TITLE", "SUBJECT_TITLE", "IS_VARIABLE_UNITS", "LECTURE_UNITS", "LAB_UNITS", "PREPARATION_UNITS", "TOTAL_UNITS", "DESIGN_UNITS", "GRADE_TYPE", "GRADE_TYPE_DESC", "GRADE_RULE", "GRADE_RULE_DESC", "HGN_CODE", "HGN_DESC", "HGN_EXCEPT", "GIR_ATTRIBUTE", "GIR_ATTRIBUTE_DESC", "COMM_REQ_ATTRIBUTE", "COMM_REQ_ATTRIBUTE_DESC", "TUITION_ATTRIBUTE", "TUITION_ATTRIBUTE_DESC", "WRITE_REQ_ATTRIBUTE", "WRITE_REQ_ATTRIBUTE_DESC", "SUPERVISOR_ATTRIBUTE", "SUPERVISOR_ATTRIBUTE_DESC", "PREREQUISITES", "SUBJECT_DESCRIPTION", "JOINT_SUBJECTS", "SCHOOL_WIDE_ELECTIVES", "MEETS_WITH_SUBJECTS", "EQUIVALENT_SUBJECTS", "IS_OFFERED_THIS_YEAR", "IS_OFFERED_FALL_TERM", "IS_OFFERED_IAP", "IS_OFFERED_SPRING_TERM", "IS_OFFERED_SUMMER_TERM", "FALL_INSTRUCTORS", "SPRING_INSTRUCTORS", "STATUS_CHANGE", "LAST_ACTIVITY_DATE", "WAREHOUSE_LOAD_DATE", "MASTER_SUBJECT_ID", "HASS_ATTRIBUTE", "HASS_ATTRIBUTE_DESC", "TERM_DURATION", "GLOBAL_REGIONS", "GLOBAL_COUNTRIES", "ON_LINE_PAGE_NUMBER", "SECTION_ID", "IS_MASTER_SECTION", "IS_LECTURE_SECTION", "IS_LAB_SECTION", "IS_RECITATION_SECTION", "IS_DESIGN_SECTION", "RESPONSIBLE_FACULTY_NAME", "RESPONSIBLE_FACULTY_MIT_ID", "MEET_TIME", "MEET_PLACE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2"]
- 示例：[[2006, "2006FA", "18.781", "18", "781", "18.781", "18.781", "Y", "18", "Mathematics", "2006FA", "Theory of Numbers", "Theory of Numbers", "N", 3, 0, 9, 12, 0, "L", "Letter graded", "N", "Not repeatable for credit", "U", "Undergraduate", NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, "An elementary introduction to number theory with no algebraic prerequisites. Primes, congruences, qua

### FCLT_FLOOR

- 列：["FCLT_FLOOR_KEY", "FCLT_BUILDING_KEY", "FLOOR", "EXT_GROSS_AREA", "ASSIGNABLE_AREA", "NON_ASSIGNABLE_AREA", "FLOOR_SORT_SEQUENCE", "LEVEL_ID", "BUILDING_WINGS_ID", "ACCESS_LEVEL", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "NUMBER", "NUMBER", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE"]
- 示例：[["37-6", "37", "6", 14876.9, 9382.8, 2996.35, 6, 6.0, NaN, 2, "19-DEC-24"], ["NW61-3", "NW61", "3", 7958.63, 5197.8, 1451.06, 3, 3.0, NaN, 2, "19-DEC-24"], ["W84-16", "W84", "16", 5850.4, 4416.82, 800.19, 16, 16.0, NaN, 2, "19-DEC-24"]]

## 子问题

["For subjects offered by departments in the School of Engineering with a total of at least 6 units, show the subject code, subject title, department name, and the running sum of total units within each grade type, ordered by subject code.", "For each floor, give the floor key and the coefficient of variation of the area of rooms located on that floor, considering only floors where the average room area is greater than zero.", "For subjects offered by departments in the School of Engineering with a total of at least 6 units, show the subject code, subject title, department name, and the running sum of total units within each grade type, but only include those subjects where the running sum exceeds 12 units within their grade type. Order the results by subject code.", "For each building, list its key, the floor key, and the coefficient of variation of the area of rooms located on that floor, considering only floors where the average room area is greater than zero. For each building, include a grand total for all floors in the format of (building key, null, total coefficient of variation)."]
