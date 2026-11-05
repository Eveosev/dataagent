# 查询任务（dw）

## 问题

For degree-granting courses in the School of Engineering, show the course description, department name, subject title, and the subject's grade type description, but only include those courses where the total units for the subject exceed the average total units for that department. Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_COURSE_DESCRIPTION", "COURSE_CATALOG_SUBJECT_OFFERED"]

## 连接键

[["COURSE_CATALOG_SUBJECT_OFFERED.SUBJECT_CODE", "SIS_COURSE_DESCRIPTION.COURSE"]]

## 列映射

{"degree-granting courses": ["SIS_COURSE_DESCRIPTION.IS_DEGREE_GRANTING"], "School of Engineering": ["SIS_COURSE_DESCRIPTION.SCHOOL_NAME"], "course description": ["SIS_COURSE_DESCRIPTION.COURSE_DESCRIPTION"], "department name": ["SIS_COURSE_DESCRIPTION.DEPARTMENT_NAME", "COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_NAME"], "subject title": ["COURSE_CATALOG_SUBJECT_OFFERED.SUBJECT_TITLE"], "subject's grade type description": ["COURSE_CATALOG_SUBJECT_OFFERED.GRADE_TYPE_DESC"], "total units for the subject": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS"]}

## 领域知识

[]

## 子问题

["For courses in the School of Engineering that are degree granting, show the course description, department name, subject title, and assign row numbers within a window of 2 preceding and 1 following rows ordered by subject title."]
