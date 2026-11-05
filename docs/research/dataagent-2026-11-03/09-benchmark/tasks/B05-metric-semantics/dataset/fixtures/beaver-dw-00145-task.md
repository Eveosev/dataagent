# 查询任务（dw）

## 问题

Show the department names, the corresponding SIS subject code, subject code descriptions, graduate level, the total number of courses per department, and for each department, the average and standard deviation (using STDDEV only and never STDDEV_POP) of total units for subjects offered in regular terms, as well as the average and standard deviation (using STDDEV only and never STDDEV_POP) of the maximum enrollment for IAP activities that required advance sign-up, and the ratio of the average total units to the average maximum enrollment, rounded to two decimal places. Present the results ordered by this ratio in descending order.

## 库

dw

## 涉及表

["ACADEMIC_TERMS", "SUBJECT_SUMMARY", "IAP_SUBJECT_DETAIL", "COURSE_CATALOG_SUBJECT_OFFERED"]

## 连接键

[["ACADEMIC_TERMS.TERM_CODE", "SUBJECT_SUMMARY.TERM_CODE"], ["ACADEMIC_TERMS.TERM_CODE", "IAP_SUBJECT_DETAIL.TERM_CODE"], ["ACADEMIC_TERMS.TERM_CODE", "COURSE_CATALOG_SUBJECT_OFFERED.TERM_CODE"]]

## 列映射

{"department names": ["SIS_DEPARTMENT.DEPARTMENT_NAME", "SUBJECT_SUMMARY.DEPARTMENT_NAME", "COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_NAME"], "SIS subject code": ["SIS_SUBJECT_CODE.SUBJECT_CODE"], "subject code descriptions": ["SIS_SUBJECT_CODE.SUBJECT_CODE_DESC"], "graduate level": ["SIS_COURSE_DESCRIPTION.GRADUATE_LEVEL"], "total number of courses per department": ["SIS_COURSE_DESCRIPTION.COURSE"], "total units for subjects offered in regular terms": ["SUBJECT_SUMMARY.TOTAL_UNITS", "ACADEMIC_TERMS.IS_REGULAR_TERM"], "maximum enrollment for IAP activities that required advance sign-up": ["IAP_SUBJECT_DETAIL.MAX_ENROLLMENT", "IAP_SUBJECT_DETAIL.ENROLLMENT_TYPE"], "average total units": ["SUBJECT_SUMMARY.TOTAL_UNITS"], "standard deviation of total units": ["SUBJECT_SUMMARY.TOTAL_UNITS"], "average maximum enrollment": ["IAP_SUBJECT_DETAIL.MAX_ENROLLMENT"], "standard deviation of maximum enrollment": ["IAP_SUBJECT_DETAIL.MAX_ENROLLMENT"], "ratio of the average total units to the average maximum enrollment": ["SUBJECT_SUMMARY.TOTAL_UNITS", "IAP_SUBJECT_DETAIL.MAX_ENROLLMENT"]}

## 领域知识

["\"math\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"Course 18\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\""]

## 表结构

### SUBJECT_SUMMARY

- 列：["SUBJECT_SUMMARY_KEY", "TERM_CODE", "SUBJECT_ID", "SUBJECT_ID_SORT", "SUBJECT_TITLE", "SUBJECT_OR_CLUSTER", "MASTER_SUBJECT_ID", "MASTER_SUBJECT_ID_SORT", "ULT_MASTER_SUBJECT_ID", "CLUSTER_TYPE", "CLUSTER_TYPE_DESC", "CLUSTER_LIST", "DEPARTMENT_CODE", "DEPARTMENT_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "TOTAL_UNITS", "LECTURE_UNITS", "LAB_UNITS", "PREP_UNITS", "DESIGN_UNITS", "SUBJECT_ENROLLMENT_NUMBER", "CLUSTER_ENROLLMENT_NUMBER", "SUBJECT_GROUP_ID", "SUBJECT_ENROLLMENT_FIRST_WEEK", "CLUSTER_ENROLLMENT_FIRST_WEEK", "SUBJECT_ENROLLMENT_FIFTH_WEEK", "CLUSTER_ENROLLMENT_FIFTH_WEEK", "SUBJECT_ENROLLMENT_CREDIT", "SUBJECT_ENROLLMENT_LISTEN", "CLUSTER_ENROLLMENT_CREDIT", "CLUSTER_ENROLLMENT_LISTEN", "SUBJECT_ENROLLMENT_1ST_CREDIT", "SUBJECT_ENROLLMENT_1ST_LISTEN", "CLUSTER_ENROLLMENT_1ST_CREDIT", "CLUSTER_ENROLLMENT_1ST_LISTEN", "SUBJECT_ENROLLMENT_5TH_CREDIT", "SUBJECT_ENROLLMENT_5TH_LISTEN", "CLUSTER_ENROLLMENT_5TH_CREDIT", "CLUSTER_ENROLLMENT_5TH_LISTEN", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "VARCHAR2", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "NUMBER", "DATE"]
- 示例：[["2.UR2019FA", "2019FA", "2.UR", "  2.UR", "Undergraduate Research", "2.UR", "2.UR", "  2.UR", "2.UR", NaN, NaN, NaN, "2", "Mechanical Engineering", "E", "Engineering", 1.0, 0.0, 1.0, 0.0, 0.0, 7, NaN, "679673EE2BF43692E0533D2F0912F028", 7, 7, 7, 7, 7, 0, 7, 0, 7, 0, 7, 0, 7, 0, 7, 0, "20-DEC-24"], ["HAA.89682009SP", "2009SP", "HAA.8968", "HAA.8968", "Yiddish Cb:Advanced II", "HAA.0000, HAA.0021,

### IAP_SUBJECT_DETAIL

- 列：["IAP_SUBJECT_CATEGORY_KEY", "IAP_SUBJECT_SPONSOR_KEY", "IAP_SUBJECT_SESSION_KEY", "IAP_SUBJECT_PERSON_KEY", "ACTIVITY_TITLE", "ACTIVITY_DESCRIPTION", "TERM_CODE", "ENROLLMENT_TYPE", "MAX_ENROLLMENT", "ATTENDANCE", "PREREQUISITES", "FEE", "FEE_REASON", "PREREG_DEADLINE", "CREATE_DATE", "LAST_ACTIVITY_DATE", "IS_MULTIPLE_SESSION", "IS_CANCELLED", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "VARCHAR2", "VARCHAR2", "NUMBER", "VARCHAR2", "DATE", "DATE", "DATE", "VARCHAR2", "VARCHAR2", "DATE"]
- 示例：[["B9953FF477E312EFE0440003BAB016E8", "B979A5B90857644BE0440003BAB016E8", "9289afec76e20021017702b62c5a01e9", "9289afec76e20021017702b62c5a01e9", "The Power Series: Exploration Through Case Studies", "<p>From the COVID-19 pandemic to the racial justice reckoning, 2020 brought a number of challenges that disproportionately impa", "2021JA", "Advance sign-up required", NaN, "Participants welcome at i

## 子问题

["For each academic year, give the academic year description and find the average and standard deviation of the total units for subjects offered in regular terms by the Mathematics department (Course 18).", "For each academic year, provide the academic year and calculate the average and standard deviation of the maximum enrollment for IAP activities that required advance sign-up, using only activities that have a non-null maximum enrollment and are offered by the Department of Mathematics (Course 18).", "For each academic year, list the academic year, the academic year description, the average and standard deviation of the total units for subjects offered in regular terms by the Mathematics department (Course 18), the average and standard deviation of the maximum enrollment for IAP activities that required advance sign-up and are offered by the Mathematics department, and calculate the ratio of the average total units to the average maximum enrollment for that year, rounded to two decimal places. Present the results ordered by this ratio in descending order."]
