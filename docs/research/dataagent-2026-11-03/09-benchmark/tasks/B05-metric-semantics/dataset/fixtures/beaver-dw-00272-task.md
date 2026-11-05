# 查询任务（dw）

## 问题

For each department that grants degrees, what are the department name, the average of the total units, the variance of the total units, the standard deviation (using STDDEV only and never STDDEV_POP) of the total units, and the geometric mean of the total units for subjects offered by that department, considering only subjects with more than 0 total units? Present the results ordered by the variance of the total units in descending order. Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_DEPARTMENT", "SUBJECT_OFFERED_SUMMARY"]

## 连接键

[["SIS_DEPARTMENT.DEPARTMENT_CODE", "SUBJECT_OFFERED_SUMMARY.OFFER_DEPT_CODE"]]

## 列映射

{"department name": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "department that grants degrees": ["SIS_DEPARTMENT.IS_DEGREE_GRANTING"], "average of the total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"], "variance of the total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"], "standard deviation of the total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"], "geometric mean of the total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"], "subjects offered by that department": ["SUBJECT_OFFERED_SUMMARY.OFFER_DEPT_CODE"], "subjects with more than 0 total units": ["SUBJECT_OFFERED_SUMMARY.TOTAL_UNITS"]}

## 领域知识

[]

## 子问题

["For each department, what are the average, variance, and standard deviation of the total units for subjects offered by that department, considering only departments that grant degrees and subjects with more than 0 total units?", "For each department, what is the department name and the geometric mean of the total units for subjects offered by that department where the total units are greater than zero?"]
