# 查询任务（dw）

## 问题

For each subject offered in the library in the Mathematics department during regular terms, show the subject title, number of enrolled students, offering department name, term description, academic year, subject short title, the maximum total units for each row and the next two rows in order of subject ID, the number of unique subjects, and the minimum total units for those subjects where the course material status is 'RQ', grouped by offering department and school. Additionally, for each offering department and school, include a grand total row for all subjects in the format of (nulls for subject-specific columns, department, school, nulls for subject-specific columns, subject count, min total units). Do not return any rounded answers.

## 库

dw

## 涉及表

["LIBRARY_SUBJECT_OFFERED", "ACADEMIC_TERMS", "COURSE_CATALOG_SUBJECT_OFFERED", "TIP_SUBJECT_OFFERED", "TIP_DETAIL", "SUBJECT_OFFERED_SUMMARY"]

## 连接键

[["ACADEMIC_TERMS.TERM_CODE", "LIBRARY_SUBJECT_OFFERED.TERM_CODE"], ["ACADEMIC_TERMS.TERM_CODE", "COURSE_CATALOG_SUBJECT_OFFERED.TERM_CODE"], ["TIP_DETAIL.SUBJECT_ID", "TIP_SUBJECT_OFFERED.SUBJECT_ID"], ["SUBJECT_OFFERED_SUMMARY.SUBJECT_ID", "TIP_DETAIL.SUBJECT_ID"]]

## 列映射

{"subject offered in the library": ["LIBRARY_SUBJECT_OFFERED.SUBJECT_TITLE", "LIBRARY_SUBJECT_OFFERED.SUBJECT_ID"], "Mathematics department": ["LIBRARY_SUBJECT_OFFERED.OFFER_DEPT_NAME"], "regular terms": ["ACADEMIC_TERMS.IS_REGULAR_TERM"], "subject title": ["LIBRARY_SUBJECT_OFFERED.SUBJECT_TITLE"], "number of enrolled students": ["LIBRARY_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "offering department name": ["LIBRARY_SUBJECT_OFFERED.OFFER_DEPT_NAME"], "term description": ["ACADEMIC_TERMS.TERM_DESCRIPTION"], "academic year": ["ACADEMIC_TERMS.ACADEMIC_YEAR"], "subject short title": ["COURSE_CATALOG_SUBJECT_OFFERED.SUBJECT_SHORT_TITLE"], "maximum total units": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS"], "subject ID": ["LIBRARY_SUBJECT_OFFERED.SUBJECT_ID"], "offering school": ["LIBRARY_SUBJECT_OFFERED.OFFER_SCHOOL_NAME"], "number of unique subjects": ["TIP_SUBJECT_OFFERED.SUBJECT_ID"], "minimum total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"], "course material status is 'RQ'": ["TIP_DETAIL.TIP_MATERIAL_STATUS_KEY"]}

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

### TIP_SUBJECT_OFFERED

- 列：["TIP_SUBJECT_OFFERED_KEY", "TERM_CODE", "IS_NO_COURSE_MATERIAL", "MASTER_COURSE_NUMBER", "MASTER_COURSE_NUMBER_SORT", "MASTER_COURSE_NUMBER_DESC", "MASTER_SUBJECT_ID", "MASTER_SUBJECT_ID_SORT", "COURSE_NUMBER", "COURSE_NUMBER_SORT", "COURSE_NUMBER_DESC", "SUBJECT_ID", "SUBJECT_ID_SORT", "SUBJECT_TITLE", "OFFER_DEPT_CODE", "OFFER_DEPT_NAME", "OFFER_SCHOOL_NAME", "RESPONSIBLE_FACULTY_NAME", "RESPONSIBLE_FACULTY_MIT_ID", "NUM_ENROLLED_STUDENTS", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "DATE"]
- 示例：[["0166830002017JA", "2017JA", NaN, "16", " 16", "Aeronautics and Astronautics", "16.683", "16.683", "16", " 16", "Aeronautics and Astronautics", "16.683", " 16.683", "Sem Aeronautics & Astronautics", "16", "Aeronautics and Astronautics", "Engineering", "Branch, Claude", 910358479.0, 0, "20-DEC-24"], ["21M3410002005FA", "2005FA", NaN, "21M", "21M", "Music and Theater Arts", "21M.341", "21M.341", "

### TIP_DETAIL

- 列：["TIP_SUBJECT_OFFERED_KEY", "TIP_MATERIAL_KEY", "TIP_MATERIAL_STATUS_KEY", "TERM_CODE", "SUBJECT_ID", "ISBN", "RECORD_COUNT", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "DATE"]
- 示例：[["0043700002010FA", "0262731223 Critical vehicles : writings, projects, interviews / KrzysztWodiczko, Krzysztof.Cambridge, Mass19992010FA", "RC", "2010FA", "4.370", "0262731223 ", 1, "20-DEC-24"], ["21G4020002017SP", "9781285675312EBK NEUE HORIZONTE82017SP", "EO", "2017SP", "21G.402", "9781285675312", 1, "20-DEC-24"], ["0106260002014SP", "N/ACourse has no materials2014SP", "NM", "2014SP", "10.626

## 子问题

["For each subject offered in the library, show the subject title, number of enrolled students, offering department name, term description, academic year, subject short title, and the maximum total units for each row and the next two rows in order of subject ID, considering only subjects offered in the 'Mathematics' department during regular terms.", "For each offering department and school where the course material status is 'RQ', provide the number of unique subjects and the minimum total units for those subjects.", "For each subject offered in the library in the Mathematics department during regular terms, show the subject title, number of enrolled students, offering department name, term description, academic year, subject short title, the maximum total units for each row and the next two rows in order of subject ID, the number of unique subjects, and the minimum total units for those subjects where the course material status is 'RQ', grouped by offering department and school."]
