# 查询任务（dw）

## 问题

List the department code, department name, department full name, the number of subjects offered, the total number of enrolled students in those subjects, and the corresponding subject code and subject title for each department that is degree-granting and offered at least one subject in the School of Engineering in 2021. Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_DEPARTMENT", "SUBJECT_OFFERED_SUMMARY"]

## 连接键

[["SIS_DEPARTMENT.DEPARTMENT_CODE", "SUBJECT_OFFERED_SUMMARY.OFFER_DEPT_CODE"]]

## 列映射

{"department code": ["SIS_DEPARTMENT.DEPARTMENT_CODE"], "department name": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "department full name": ["SIS_DEPARTMENT.DEPARTMENT_FULL_NAME"], "number of subjects offered": ["SUBJECT_OFFERED_SUMMARY.SUBJECT_OFFERED_SUMMARY_KEY"], "total number of enrolled students": ["SUBJECT_OFFERED_SUMMARY.NUM_ENROLLED_STUDENTS"], "subject code": ["SUBJECT_OFFERED_SUMMARY.COURSE_NUMBER"], "subject title": ["SUBJECT_OFFERED_SUMMARY.SUBJECT_TITLE"], "degree-granting": ["SIS_DEPARTMENT.IS_DEGREE_GRANTING"], "School of Engineering": ["SUBJECT_OFFERED_SUMMARY.OFFER_SCHOOL_NAME"], "2021": ["SUBJECT_OFFERED_SUMMARY.TERM_CODE"]}

## 领域知识

[]

## 子问题

["For each department that is degree-granting and offered at least one subject in the School of Engineering in 2021, provide the department code, department name, department full name, the number of subjects offered, and the total number of enrolled students in those subjects."]
