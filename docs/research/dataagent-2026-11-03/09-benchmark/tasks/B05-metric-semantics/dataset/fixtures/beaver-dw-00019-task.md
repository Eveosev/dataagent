# 查询任务（dw）

## 问题

List the minimum department code and the total number of unique department names for degree-granting courses in the School of Engineering, excluding courses from the Physics department, along with the corresponding subject code descriptions. Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_SUBJECT_CODE", "SIS_COURSE_DESCRIPTION"]

## 连接键

[["SIS_COURSE_DESCRIPTION.COURSE", "SIS_SUBJECT_CODE.SUBJECT_CODE"], ["SIS_COURSE_DESCRIPTION.COURSE", "SIS_SUBJECT_CODE.COURSE_NUMBER"]]

## 列映射

{"minimum department code": ["SIS_SUBJECT_CODE.DEPARTMENT_CODE"], "total number of unique department names": ["SIS_SUBJECT_CODE.DEPARTMENT_NAME"], "degree-granting courses": ["SIS_COURSE_DESCRIPTION.IS_DEGREE_GRANTING"], "School of Engineering": ["SIS_COURSE_DESCRIPTION.SCHOOL_NAME"], "Physics department": ["SIS_SUBJECT_CODE.DEPARTMENT_NAME"], "subject code descriptions": ["SIS_SUBJECT_CODE.SUBJECT_CODE_DESC"]}

## 领域知识

["\"Physics\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Physics'\"", "\"Physics\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Physics'\""]

## 子问题

["What is the minimum department code and the total number of unique department names for degree-granting courses in the School of Engineering, excluding courses from the Physics department?"]
