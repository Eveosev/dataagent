# 查询任务（dw）

## 问题

For each academic year, which subjects offered in the fall term have an above-average number of enrolled students compared to the average enrollment for that year, and what is the minimum academic year and the sum of total units for subjects that are offered in the fall term, considering only library reserve material details with material status 'U'? Please provide the academic year, subject id, subject title, number of enrolled students, minimum academic year, and total units sum in this order. Do not return any rounded answers.

## 库

dw

## 涉及表

["COURSE_CATALOG_SUBJECT_OFFERED", "ACADEMIC_TERMS_ALL", "TIP_SUBJECT_OFFERED", "LIBRARY_RESERVE_MATRL_DETAIL", "ACADEMIC_TERMS"]

## 连接键

[["ACADEMIC_TERMS_ALL.TERM_CODE", "COURSE_CATALOG_SUBJECT_OFFERED.TERM_CODE"], ["ACADEMIC_TERMS_ALL.TERM_CODE", "TIP_SUBJECT_OFFERED.TERM_CODE"], ["ACADEMIC_TERMS.TERM_CODE", "LIBRARY_RESERVE_MATRL_DETAIL.TERM_CODE"], ["ACADEMIC_TERMS.TERM_CODE", "COURSE_CATALOG_SUBJECT_OFFERED.TERM_CODE"]]

## 列映射

{"academic year": ["ACADEMIC_TERMS_ALL.ACADEMIC_YEAR", "ACADEMIC_TERMS.ACADEMIC_YEAR"], "subjects offered in the fall term": ["COURSE_CATALOG_SUBJECT_OFFERED.IS_OFFERED_FALL_TERM", "TIP_SUBJECT_OFFERED.SUBJECT_ID", "TIP_SUBJECT_OFFERED.SUBJECT_TITLE"], "number of enrolled students": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "average enrollment for that year": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS", "ACADEMIC_TERMS_ALL.ACADEMIC_YEAR"], "minimum academic year": ["ACADEMIC_TERMS.ACADEMIC_YEAR"], "sum of total units": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS"], "library reserve material details": ["LIBRARY_RESERVE_MATRL_DETAIL.LIBRARY_MATERIAL_STATUS_KEY"], "material status 'U'": ["LIBRARY_RESERVE_MATRL_DETAIL.LIBRARY_MATERIAL_STATUS_KEY"]}

## 领域知识

[]

## 表结构

### ACADEMIC_TERMS_ALL

- 列：["ACADEMIC_TERMS_KEY", "TERM_CODE", "TERM_DESCRIPTION", "TERM_SELECTOR", "TERM_START_DATE", "TERM_END_DATE", "ACADEMIC_YEAR", "ACADEMIC_YEAR_DESC", "IS_CURRENT_TERM", "TERM_STATUS_INDICATOR", "FINANCIAL_AID_YEAR", "DEGREE_YEAR", "LAST_DAY_OF_FINAL_EXAM", "PRE_REGISTRATION_START_DAY", "REGISTRATION_DAY", "FIRST_DAY_OF_CLASSES", "LAST_DAY_OF_CLASSES", "GRADUATE_AWARD_START_DATE", "GRADUATE_AWARD_END_DATE", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE"]
- 示例：[["2022SU", "2022SU", "Summer Term 2022", "2022SU-Summer Term 2022", "06-JUN-22", "16-AUG-22", 2022, "Academic Year 2021-2022", "N", "P", "2023", "2023", "16-AUG-22", "02-MAY-22", "06-JUN-22", "06-JUN-22", "12-AUG-22", "01-JUN-22", "31-AUG-22", "19-DEC-24"], ["2020JA", "2020JA", "January Term 2019-2020", "2020JA-January Term 2019-2020", "06-JAN-20", "31-JAN-20", 2020, "Academic Year 2019-2020", "N

### TIP_SUBJECT_OFFERED

- 列：["TIP_SUBJECT_OFFERED_KEY", "TERM_CODE", "IS_NO_COURSE_MATERIAL", "MASTER_COURSE_NUMBER", "MASTER_COURSE_NUMBER_SORT", "MASTER_COURSE_NUMBER_DESC", "MASTER_SUBJECT_ID", "MASTER_SUBJECT_ID_SORT", "COURSE_NUMBER", "COURSE_NUMBER_SORT", "COURSE_NUMBER_DESC", "SUBJECT_ID", "SUBJECT_ID_SORT", "SUBJECT_TITLE", "OFFER_DEPT_CODE", "OFFER_DEPT_NAME", "OFFER_SCHOOL_NAME", "RESPONSIBLE_FACULTY_NAME", "RESPONSIBLE_FACULTY_MIT_ID", "NUM_ENROLLED_STUDENTS", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "DATE"]
- 示例：[["0166830002017JA", "2017JA", NaN, "16", " 16", "Aeronautics and Astronautics", "16.683", "16.683", "16", " 16", "Aeronautics and Astronautics", "16.683", " 16.683", "Sem Aeronautics & Astronautics", "16", "Aeronautics and Astronautics", "Engineering", "Branch, Claude", 910358479.0, 0, "20-DEC-24"], ["21M3410002005FA", "2005FA", NaN, "21M", "21M", "Music and Theater Arts", "21M.341", "21M.341", "

### LIBRARY_RESERVE_MATRL_DETAIL

- 列：["LIBRARY_COURSE_INSTRUCTOR_KEY", "LIBRARY_RESERVE_CATALOG_KEY", "LIBRARY_SUBJECT_OFFERED_KEY", "LIBRARY_MATERIAL_STATUS_KEY", "TERM_CODE", "SUBJECT_ID", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE"]
- 示例：[["SP.713-SMALL2009JA:SP.713", 50265, "SP.7132009JA", "N", "2009JA", "SP.713", "02-FEB-09"], ["21H.421-CASE2008SP:21H.421", 45133, "21H.4212008SP", "U", "2008SP", "21H.421", "09-MAY-08"], ["21M.240-RODGERS2009SP:21M.240", 52604, "21M.2402009SP", "U", "2009SP", "21M.240", "08-MAY-09"]]

## 子问题

["For each academic year, what is the average and variance of the number of enrolled students in each subject offered, considering only subjects that are offered in the fall term and have more than 0 enrolled students? Please provide the academic year and these statistics.", "What is the minimum academic year and the sum of total units for subjects that are offered in the fall term, considering only library reserve material details with material status 'U'?", "For each academic year, what is the average and variance of the number of enrolled students in each subject offered, considering only subjects that are offered in the fall term and have more than 0 enrolled students, and what is the minimum academic year and the sum of total units for subjects that are offered in the fall term, considering only library reserve material details with material status 'U'? Please provide the academic year, average enrollment, enrollment variance, minimum academic year, and total units sum in this order."]
