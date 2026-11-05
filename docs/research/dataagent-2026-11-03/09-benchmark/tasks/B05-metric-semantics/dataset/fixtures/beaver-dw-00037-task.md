# 查询任务（dw）

## 问题

Show the minimum total units, the sum of lecture units, and the number of unique subjects for letter graded Mathematics department (Course 18) subjects offered in the Spring Term 2021, along with the department name and term description. Do not return any rounded answers.

## 库

dw

## 涉及表

["ACADEMIC_TERMS_ALL", "COURSE_CATALOG_SUBJECT_OFFERED"]

## 连接键

[["ACADEMIC_TERMS_ALL.TERM_CODE", "COURSE_CATALOG_SUBJECT_OFFERED.TERM_CODE"]]

## 列映射

{"minimum total units": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS"], "sum of lecture units": ["COURSE_CATALOG_SUBJECT_OFFERED.LECTURE_UNITS"], "number of unique subjects": ["COURSE_CATALOG_SUBJECT_OFFERED.SUBJECT_ID"], "department name": ["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_NAME"], "term description": ["ACADEMIC_TERMS_ALL.TERM_DESCRIPTION"], "letter graded": ["COURSE_CATALOG_SUBJECT_OFFERED.GRADE_TYPE"], "Mathematics department (Course 18)": ["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_NAME"], "Spring Term 2021": ["ACADEMIC_TERMS_ALL.TERM_CODE", "COURSE_CATALOG_SUBJECT_OFFERED.TERM_CODE"]}

## 领域知识

["\"math\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"Course 18\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\""]

## 子问题

["What is the minimum total units and the sum of lecture units for subjects offered in the Spring Term 2021 that are letter graded and are in the Mathematics department (Course 18)?"]
