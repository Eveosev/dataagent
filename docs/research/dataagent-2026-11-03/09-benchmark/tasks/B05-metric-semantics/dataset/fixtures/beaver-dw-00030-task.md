# 查询任务（dw）

## 问题

For each HGN code in the Political Science department, what is the department name, the maximum number of lecture units among all subjects in the course catalog, and the subject title from the subject offered table, for subjects offered in the year 2012 with more than 2 lecture units, and only include those where the subject is also present in the SUBJECT_OFFERED table for the same year? Do not return any rounded answers.

## 库

dw

## 涉及表

["COURSE_CATALOG_SUBJECT_OFFERED", "SUBJECT_OFFERED"]

## 连接键

[["COURSE_CATALOG_SUBJECT_OFFERED.HGN_CODE", "SUBJECT_OFFERED.HGN_CODE"]]

## 列映射

{"HGN code": ["COURSE_CATALOG_SUBJECT_OFFERED.HGN_CODE", "SUBJECT_OFFERED.HGN_CODE"], "department name": ["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_NAME"], "maximum number of lecture units": ["COURSE_CATALOG_SUBJECT_OFFERED.LECTURE_UNITS"], "subject title": ["SUBJECT_OFFERED.SUBJECT_TITLE"], "Political Science": ["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_NAME"], "year 2012": ["COURSE_CATALOG_SUBJECT_OFFERED.ACADEMIC_YEAR", "SUBJECT_OFFERED.TERM_CODE"], "more than 2 lecture units": ["COURSE_CATALOG_SUBJECT_OFFERED.LECTURE_UNITS"], "subject is also present in the SUBJECT_OFFERED table for the same year": ["COURSE_CATALOG_SUBJECT_OFFERED.HGN_CODE", "SUBJECT_OFFERED.HGN_CODE", "SUBJECT_OFFERED.TERM_CODE"]}

## 领域知识

["\"Political Science\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Political Science'\"", "\"Course 17\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Political Science'\""]

## 子问题

["For each HGN code in the Political Science department, what is the department name, the maximum number of lecture units among all subjects in the course catalog, and the subject title from the subject offered table, for subjects offered in the year 2012 with more than 2 lecture units?"]
