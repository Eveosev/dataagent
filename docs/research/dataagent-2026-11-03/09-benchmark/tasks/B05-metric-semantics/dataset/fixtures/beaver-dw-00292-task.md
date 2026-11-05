# 查询任务（dw）

## 问题

For each academic year and subject category where the subject has a maximum enrollment greater than 10, what is the academic year, academic year description, the variance of the number of tip detail records for subjects offered in that year (considering only subjects that are offered in the fall term and have at least one associated tip detail record), the number of unique departments represented among those subjects, the subject category key, the number of unique subjects, the minimum academic term start date, and the total number of TIP materials per subject category and academic year? Present the results ordered by the variance of tip detail record counts in descending order, then by total TIP materials in descending order. Do not return any rounded answers.

## 库

dw

## 涉及表

["COURSE_CATALOG_SUBJECT_OFFERED", "ACADEMIC_TERMS_ALL", "TIP_DETAIL", "IAP_SUBJECT_DETAIL", "ACADEMIC_TERMS"]

## 连接键

[["ACADEMIC_TERMS_ALL.TERM_CODE", "COURSE_CATALOG_SUBJECT_OFFERED.TERM_CODE"], ["ACADEMIC_TERMS_ALL.TERM_CODE", "TIP_DETAIL.TERM_CODE"], ["ACADEMIC_TERMS.TERM_CODE", "IAP_SUBJECT_DETAIL.TERM_CODE"], ["ACADEMIC_TERMS.TERM_CODE", "TIP_DETAIL.TERM_CODE"]]

## 列映射

{"academic year": ["ACADEMIC_TERMS_ALL.ACADEMIC_YEAR", "ACADEMIC_TERMS.ACADEMIC_YEAR"], "academic year description": ["ACADEMIC_TERMS_ALL.ACADEMIC_YEAR_DESC"], "variance of the number of tip detail records": ["TIP_DETAIL.RECORD_COUNT"], "subjects offered in that year": ["COURSE_CATALOG_SUBJECT_OFFERED.TERM_CODE", "ACADEMIC_TERMS_ALL.TERM_CODE"], "subjects that are offered in the fall term": ["COURSE_CATALOG_SUBJECT_OFFERED.IS_OFFERED_FALL_TERM"], "tip detail record": ["TIP_DETAIL.RECORD_COUNT"], "departments": ["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_CODE"], "subject category key": ["IAP_SUBJECT_DETAIL.IAP_SUBJECT_CATEGORY_KEY"], "unique subjects": ["IAP_SUBJECT_DETAIL.IAP_SUBJECT_SESSION_KEY"], "minimum academic term start date": ["ACADEMIC_TERMS.TERM_START_DATE"], "TIP materials": ["TIP_DETAIL.TIP_MATERIAL_KEY"], "maximum enrollment greater than 10": ["IAP_SUBJECT_DETAIL.MAX_ENROLLMENT"]}

## 领域知识

[]

## 表结构

### ACADEMIC_TERMS_ALL

- 列：["ACADEMIC_TERMS_KEY", "TERM_CODE", "TERM_DESCRIPTION", "TERM_SELECTOR", "TERM_START_DATE", "TERM_END_DATE", "ACADEMIC_YEAR", "ACADEMIC_YEAR_DESC", "IS_CURRENT_TERM", "TERM_STATUS_INDICATOR", "FINANCIAL_AID_YEAR", "DEGREE_YEAR", "LAST_DAY_OF_FINAL_EXAM", "PRE_REGISTRATION_START_DAY", "REGISTRATION_DAY", "FIRST_DAY_OF_CLASSES", "LAST_DAY_OF_CLASSES", "GRADUATE_AWARD_START_DATE", "GRADUATE_AWARD_END_DATE", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE", "DATE"]
- 示例：[["2022SU", "2022SU", "Summer Term 2022", "2022SU-Summer Term 2022", "06-JUN-22", "16-AUG-22", 2022, "Academic Year 2021-2022", "N", "P", "2023", "2023", "16-AUG-22", "02-MAY-22", "06-JUN-22", "06-JUN-22", "12-AUG-22", "01-JUN-22", "31-AUG-22", "19-DEC-24"], ["2020JA", "2020JA", "January Term 2019-2020", "2020JA-January Term 2019-2020", "06-JAN-20", "31-JAN-20", 2020, "Academic Year 2019-2020", "N

### TIP_DETAIL

- 列：["TIP_SUBJECT_OFFERED_KEY", "TIP_MATERIAL_KEY", "TIP_MATERIAL_STATUS_KEY", "TERM_CODE", "SUBJECT_ID", "ISBN", "RECORD_COUNT", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "DATE"]
- 示例：[["0043700002010FA", "0262731223 Critical vehicles : writings, projects, interviews / KrzysztWodiczko, Krzysztof.Cambridge, Mass19992010FA", "RC", "2010FA", "4.370", "0262731223 ", 1, "20-DEC-24"], ["21G4020002017SP", "9781285675312EBK NEUE HORIZONTE82017SP", "EO", "2017SP", "21G.402", "9781285675312", 1, "20-DEC-24"], ["0106260002014SP", "N/ACourse has no materials2014SP", "NM", "2014SP", "10.626

### IAP_SUBJECT_DETAIL

- 列：["IAP_SUBJECT_CATEGORY_KEY", "IAP_SUBJECT_SPONSOR_KEY", "IAP_SUBJECT_SESSION_KEY", "IAP_SUBJECT_PERSON_KEY", "ACTIVITY_TITLE", "ACTIVITY_DESCRIPTION", "TERM_CODE", "ENROLLMENT_TYPE", "MAX_ENROLLMENT", "ATTENDANCE", "PREREQUISITES", "FEE", "FEE_REASON", "PREREG_DEADLINE", "CREATE_DATE", "LAST_ACTIVITY_DATE", "IS_MULTIPLE_SESSION", "IS_CANCELLED", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "VARCHAR2", "VARCHAR2", "NUMBER", "VARCHAR2", "DATE", "DATE", "DATE", "VARCHAR2", "VARCHAR2", "DATE"]
- 示例：[["B9953FF477E312EFE0440003BAB016E8", "B979A5B90857644BE0440003BAB016E8", "9289afec76e20021017702b62c5a01e9", "9289afec76e20021017702b62c5a01e9", "The Power Series: Exploration Through Case Studies", "<p>From the COVID-19 pandemic to the racial justice reckoning, 2020 brought a number of challenges that disproportionately impa", "2021JA", "Advance sign-up required", NaN, "Participants welcome at i

## 子问题

["For each academic year, what is the academic year description and the variance of the number of tip detail records for subjects offered in that year, considering only subjects that are offered in the fall term and have at least one associated tip detail record?", "For each subject category and academic year where the subject has a maximum enrollment greater than 10, give the number of unique subjects and the minimum academic term start date.", "For each academic year, what is the academic year description, the variance of the number of tip detail records for subjects offered in that year (considering only subjects that are offered in the fall term and have at least one associated tip detail record), and the number of unique departments represented among those subjects?", "For each subject category and academic year where the subject has a maximum enrollment greater than 10, show the number of unique subjects, the minimum academic term start date, and the total number of TIP materials per subject category and academic year."]
