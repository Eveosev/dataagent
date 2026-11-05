# 查询任务（dw）

## 问题

For each academic year, what is the standard deviation (using STDDEV only and never STDDEV_POP) of the maximum enrollment for IAP activities offered by the Mathematics department (Course 18), considering only years with more than five activities, and what is the corresponding academic year description? Do not return any rounded answers.

## 库

dw

## 涉及表

["IAP_SUBJECT_DETAIL", "ACADEMIC_TERMS_ALL", "COURSE_CATALOG_SUBJECT_OFFERED"]

## 连接键

[["IAP_SUBJECT_DETAIL.TERM_CODE", "ACADEMIC_TERMS_ALL.TERM_CODE"], ["ACADEMIC_TERMS_ALL.TERM_CODE", "COURSE_CATALOG_SUBJECT_OFFERED.TERM_CODE"]]

## 列映射

{"academic year": ["ACADEMIC_TERMS_ALL.ACADEMIC_YEAR"], "standard deviation of the maximum enrollment": ["IAP_SUBJECT_DETAIL.MAX_ENROLLMENT"], "IAP activities": ["IAP_SUBJECT_DETAIL.MAX_ENROLLMENT"], "Mathematics department (Course 18)": ["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_NAME"], "academic year description": ["ACADEMIC_TERMS_ALL.ACADEMIC_YEAR_DESC"], "years with more than five activities": ["IAP_SUBJECT_DETAIL.MAX_ENROLLMENT"]}

## 领域知识

["\"math\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"Course 18\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\""]

## 表结构

### ACADEMIC_TERMS_ALL

- 列：["ACADEMIC_TERMS_KEY", "TERM_CODE", "TERM_DESCRIPTION", "TERM_SELECTOR", "TERM_START_DATE", "TERM_END_DATE", "ACADEMIC_YEAR", "ACADEMIC_YEAR_DESC", "IS_CURRENT_TERM", "TERM_STATUS_INDICATOR", "FINANCIAL_AID_YEAR", "DEGREE_YEAR", "LAST_DAY_OF_FINAL_EXAM", "PRE_REGISTRATION_START_DAY", "REGISTRATION_DAY", "FIRST_DAY_OF_CLASSES", "LAST_DAY_OF_CLASSES", "GRADUATE_AWARD_START_DATE", "GRADUATE_AWARD_END_DATE", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE"]
- 示例：[["2022SU", "2022SU", "Summer Term 2022", "2022SU-Summer Term 2022", "06-JUN-22", "16-AUG-22", 2022, "Academic Year 2021-2022", "N", "P", "2023", "2023", "16-AUG-22", "02-MAY-22", "06-JUN-22", "06-JUN-22", "12-AUG-22", "01-JUN-22", "31-AUG-22", "19-DEC-24"], ["2020JA", "2020JA", "January Term 2019-2020", "2020JA-January Term 2019-2020", "06-JAN-20", "31-JAN-20", 2020, "Academic Year 2019-2020", "N

## 子问题

[]
