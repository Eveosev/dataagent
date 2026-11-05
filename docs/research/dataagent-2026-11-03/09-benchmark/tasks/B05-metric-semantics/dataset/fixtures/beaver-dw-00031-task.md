# 查询任务（dw）

## 问题

For each department, what is the department name and the highest variance of the number of enrolled students in courses offered by that department across all terms, considering only degree-granting courses and excluding the Chemistry department? Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_COURSE_DESCRIPTION", "SIS_SUBJECT_CODE", "LIBRARY_SUBJECT_OFFERED"]

## 连接键

[["SIS_COURSE_DESCRIPTION.COURSE", "SIS_SUBJECT_CODE.COURSE_NUMBER"], ["LIBRARY_SUBJECT_OFFERED.COURSE_NUMBER", "SIS_SUBJECT_CODE.COURSE_NUMBER"]]

## 列映射

{"department": ["SIS_COURSE_DESCRIPTION.DEPARTMENT_NAME"], "department name": ["SIS_COURSE_DESCRIPTION.DEPARTMENT_NAME"], "number of enrolled students": ["LIBRARY_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "courses offered by that department": ["SIS_COURSE_DESCRIPTION.DEPARTMENT_NAME", "LIBRARY_SUBJECT_OFFERED.COURSE_NUMBER"], "terms": ["LIBRARY_SUBJECT_OFFERED.TERM_CODE"], "degree-granting courses": ["SIS_COURSE_DESCRIPTION.IS_DEGREE_GRANTING"], "Chemistry department": ["SIS_COURSE_DESCRIPTION.DEPARTMENT_NAME"]}

## 领域知识

["\"degree-granting courses\" is predicated by \"TABLE.IS_DEGREE_GRANTING = 'Y'\"", "\"Chemistry\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Chemistry'\""]

## 表结构

### SIS_SUBJECT_CODE

- 列：["COURSE_NUMBER", "SUBJECT_CODE", "SUBJECT_CODE_DESC", "DEPARTMENT_CODE", "DEPARTMENT_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE"]
- 示例：[["S0", "S0", NaN, NaN, NaN, NaN, NaN, "19-DEC-24"], ["OGE", "OGE", "Office of Graduate Education", "OGE", "Office of Graduate Education", "Y", "MIT, academic", "19-DEC-24"], ["MCH", "MCH", "Photography", "NIA", "Non-Institute-MFA/MCA", "Z", "Non-MIT", "19-DEC-24"]]

## 子问题

["For each department, what is the department name and the variance of the number of enrolled students in courses offered by that department during the term '2014FA', considering only degree-granting courses and excluding the Chemistry department?"]
