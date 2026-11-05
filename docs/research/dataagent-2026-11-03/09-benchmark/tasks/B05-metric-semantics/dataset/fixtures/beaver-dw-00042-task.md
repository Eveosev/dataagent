# 查询任务（dw）

## 问题

For subjects in the academic term with the term code '2019FA' that are in the Mathematics department, show the subject ID, subject title, department name, total units, the rank of each subject within its department (ordered by subject ID), and the deviation of each subject's total units from the average total units of all Mathematics subjects in that term. Do not return any rounded answers.

## 库

dw

## 涉及表

["ACADEMIC_TERMS", "SUBJECT_SUMMARY"]

## 连接键

[["ACADEMIC_TERMS.TERM_CODE", "SUBJECT_SUMMARY.TERM_CODE"]]

## 列映射

{"subjects": ["SUBJECT_SUMMARY.SUBJECT_ID", "SUBJECT_SUMMARY.SUBJECT_TITLE"], "academic term": ["ACADEMIC_TERMS.TERM_CODE", "SUBJECT_SUMMARY.TERM_CODE"], "term code '2019FA'": ["ACADEMIC_TERMS.TERM_CODE", "SUBJECT_SUMMARY.TERM_CODE"], "Mathematics department": ["SUBJECT_SUMMARY.DEPARTMENT_NAME"], "subject ID": ["SUBJECT_SUMMARY.SUBJECT_ID"], "subject title": ["SUBJECT_SUMMARY.SUBJECT_TITLE"], "department name": ["SUBJECT_SUMMARY.DEPARTMENT_NAME"], "total units": ["SUBJECT_SUMMARY.TOTAL_UNITS"], "rank of each subject within its department": ["SUBJECT_SUMMARY.DEPARTMENT_NAME", "SUBJECT_SUMMARY.SUBJECT_ID"], "average total units": ["SUBJECT_SUMMARY.TOTAL_UNITS"], "deviation of each subject's total units from the average": ["SUBJECT_SUMMARY.TOTAL_UNITS"]}

## 领域知识

["\"math\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"Course 18\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\""]

## 子问题

["For subjects in the academic term with the term code '2019FA' that are in the Mathematics department, show the subject ID, subject title, department name, total units, and the rank of each subject within its department (ordered by subject ID)."]
