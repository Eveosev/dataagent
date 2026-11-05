# 查询任务（dw）

## 问题

For each IAP subject activity with a maximum enrollment greater than 10, show the activity title, enrollment type, term description, subject ID, and the sum of maximum enrollment within each academic year. Additionally, indicate whether the activity's maximum enrollment is at least 20% greater than the average maximum enrollment for that academic year ('HIGH_ENROLLMENT'), at least 20% less ('LOW_ENROLLMENT'), or otherwise 'AVERAGE'. Order the results by activity title. Do not return any rounded answers.

## 库

dw

## 涉及表

["IAP_SUBJECT_DETAIL", "ACADEMIC_TERMS", "TIP_DETAIL"]

## 连接键

[["ACADEMIC_TERMS.TERM_CODE", "IAP_SUBJECT_DETAIL.TERM_CODE"], ["ACADEMIC_TERMS.TERM_CODE", "TIP_DETAIL.TERM_CODE"]]

## 列映射

{"IAP subject activity": ["IAP_SUBJECT_DETAIL.ACTIVITY_TITLE"], "maximum enrollment": ["IAP_SUBJECT_DETAIL.MAX_ENROLLMENT"], "enrollment type": ["IAP_SUBJECT_DETAIL.ENROLLMENT_TYPE"], "term description": ["ACADEMIC_TERMS.TERM_DESCRIPTION"], "subject ID": ["TIP_DETAIL.SUBJECT_ID"], "academic year": ["ACADEMIC_TERMS.ACADEMIC_YEAR"], "sum of maximum enrollment within each academic year": ["IAP_SUBJECT_DETAIL.MAX_ENROLLMENT", "ACADEMIC_TERMS.ACADEMIC_YEAR"], "average maximum enrollment for that academic year": ["IAP_SUBJECT_DETAIL.MAX_ENROLLMENT", "ACADEMIC_TERMS.ACADEMIC_YEAR"], "activity title": ["IAP_SUBJECT_DETAIL.ACTIVITY_TITLE"]}

## 领域知识

[]

## 表结构

### ACADEMIC_TERMS

- 列：["ACADEMIC_TERMS_KEY", "TERM_CODE", "TERM_DESCRIPTION", "TERM_SELECTOR", "TERM_START_DATE", "TERM_END_DATE", "ACADEMIC_YEAR", "ACADEMIC_YEAR_DESC", "IS_CURRENT_TERM", "IS_REGULAR_TERM", "TERM_STATUS_INDICATOR", "TERM_STATUS", "FINANCIAL_AID_YEAR", "DEGREE_YEAR", "LAST_DAY_OF_FINAL_EXAM", "PRE_REGISTRATION_START_DAY", "REGISTRATION_DAY", "FIRST_DAY_OF_CLASSES", "LAST_DAY_OF_CLASSES", "ADD_DATE", "DROP_DATE", "GRADUATE_AWARD_START_DATE", "GRADUATE_AWARD_END_DATE", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE"]
- 示例：[["2003JA", "2003JA", "January Term 2002-2003", "2003JA-January Term 2002-2003", "06-JAN-03", "02-FEB-03", 2003, "Academic Year 2002-2003", "N", "N", "P", "Previous", NaN, NaN, "31-JAN-03", "29-NOV-02", "06-JAN-03", "06-JAN-03", "31-JAN-03", NaN, NaN, NaN, NaN, "19-DEC-24"], ["2027JA", "2027JA", "January Term 2026-2027", "2027JA-January Term 2026-2027", "04-JAN-27", "29-JAN-27", 2027, "Academic Ye

## 子问题

["For each IAP subject activity with a maximum enrollment greater than 10, show the activity title, enrollment type, term description, subject ID, and the sum of maximum enrollment within each academic year, ordered by activity title."]
