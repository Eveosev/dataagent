# 查询任务（dw）

## 问题

For each department and school, what are the average, variance, and standard deviation (using STDDEV only and never STDDEV_POP) of the total units for subjects offered by that department, considering only departments that grant degrees and subjects with more than 0 total units, and specifically for the Mathematics department (Course 18)? Additionally, for each school, include a grand total for all departments in the format of (null, school name, average, variance, stddev). Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_DEPARTMENT", "SUBJECT_OFFERED_SUMMARY"]

## 连接键

[["SIS_DEPARTMENT.DEPARTMENT_CODE", "SUBJECT_OFFERED_SUMMARY.OFFER_DEPT_CODE"]]

## 列映射

{"department": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "school": ["SIS_DEPARTMENT.SCHOOL_NAME"], "average of total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"], "variance of total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"], "standard deviation of total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"], "departments that grant degrees": ["SIS_DEPARTMENT.IS_DEGREE_GRANTING"], "subjects with more than 0 total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"], "Mathematics department (Course 18)": ["SIS_DEPARTMENT.DEPARTMENT_NAME"]}

## 领域知识

["\"math\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"Course 18\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\""]

## 子问题

["For each department, what are the average, variance, and standard deviation of the total units for subjects offered by that department, considering only departments that grant degrees, subjects with more than 0 total units, and specifically for the Mathematics department (Course 18)?"]
