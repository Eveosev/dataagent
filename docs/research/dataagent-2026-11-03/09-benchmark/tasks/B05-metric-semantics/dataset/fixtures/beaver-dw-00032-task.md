# 查询任务（dw）

## 问题

For each academic year, what is the academic year description, and what are the minimum, maximum, and average number of TIP materials per subject offered in that year, considering only subjects that are offered in the fall term, have at least one TIP material, and are in the Mathematics department (Course 18)? Do not return any rounded answers.

## 库

dw

## 涉及表

["COURSE_CATALOG_SUBJECT_OFFERED", "ACADEMIC_TERMS_ALL", "TIP_DETAIL"]

## 连接键

[["ACADEMIC_TERMS_ALL.TERM_CODE", "COURSE_CATALOG_SUBJECT_OFFERED.TERM_CODE"], ["ACADEMIC_TERMS_ALL.TERM_CODE", "TIP_DETAIL.TERM_CODE"]]

## 列映射

{"academic year": ["ACADEMIC_TERMS_ALL.ACADEMIC_YEAR"], "academic year description": ["ACADEMIC_TERMS_ALL.ACADEMIC_YEAR_DESC"], "number of TIP materials per subject": ["TIP_DETAIL.TIP_MATERIAL_KEY"], "subjects offered in the fall term": ["COURSE_CATALOG_SUBJECT_OFFERED.IS_OFFERED_FALL_TERM"], "Mathematics department (Course 18)": ["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_NAME"]}

## 领域知识

["\"math\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"Course 18\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\""]

## 表结构

### ACADEMIC_TERMS_ALL

- 列：["ACADEMIC_TERMS_KEY", "TERM_CODE", "TERM_DESCRIPTION", "TERM_SELECTOR", "TERM_START_DATE", "TERM_END_DATE", "ACADEMIC_YEAR", "ACADEMIC_YEAR_DESC", "IS_CURRENT_TERM", "TERM_STATUS_INDICATOR", "FINANCIAL_AID_YEAR", "DEGREE_YEAR", "LAST_DAY_OF_FINAL_EXAM", "PRE_REGISTRATION_START_DAY", "REGISTRATION_DAY", "FIRST_DAY_OF_CLASSES", "LAST_DAY_OF_CLASSES", "GRADUATE_AWARD_START_DATE", "GRADUATE_AWARD_END_DATE", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE"]
- 示例：[["2022SU", "2022SU", "Summer Term 2022", "2022SU-Summer Term 2022", "06-JUN-22", "16-AUG-22", 2022, "Academic Year 2021-2022", "N", "P", "2023", "2023", "16-AUG-22", "02-MAY-22", "06-JUN-22", "06-JUN-22", "12-AUG-22", "01-JUN-22", "31-AUG-22", "19-DEC-24"], ["2020JA", "2020JA", "January Term 2019-2020", "2020JA-January Term 2019-2020", "06-JAN-20", "31-JAN-20", 2020, "Academic Year 2019-2020", "N

## 子问题

["For each academic year, what is the academic year description, and what are the range, variance, and standard deviation of the number of TIP materials per subject offered in that year, considering only subjects that are offered in the fall term, have at least one TIP material, and are in the Mathematics department (Course 18)?"]
