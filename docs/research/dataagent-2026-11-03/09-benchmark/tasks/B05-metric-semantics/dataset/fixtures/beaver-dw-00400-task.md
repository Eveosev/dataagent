# 查询任务（dw）

## 问题

For each course material detail in the Chemistry department, provide the material status key, term code, subject ID, ISBN, material key, the course number description, the subject title, the offering department name, and the maximum number of enrolled students for each row considering the current row and the next 2 rows ordered by material key, and only include results where the offering department name is 'Chemistry'. Do not return any rounded answers.

## 库

dw

## 涉及表

["TIP_DETAIL", "TIP_SUBJECT_OFFERED"]

## 连接键

[["TIP_DETAIL.TIP_SUBJECT_OFFERED_KEY", "TIP_SUBJECT_OFFERED.TIP_SUBJECT_OFFERED_KEY"]]

## 列映射

{"course material detail": ["TIP_DETAIL.TIP_MATERIAL_STATUS_KEY", "TIP_DETAIL.TERM_CODE", "TIP_DETAIL.SUBJECT_ID", "TIP_DETAIL.ISBN", "TIP_DETAIL.TIP_MATERIAL_KEY"], "material status key": ["TIP_DETAIL.TIP_MATERIAL_STATUS_KEY"], "term code": ["TIP_DETAIL.TERM_CODE"], "subject ID": ["TIP_DETAIL.SUBJECT_ID"], "ISBN": ["TIP_DETAIL.ISBN"], "material key": ["TIP_DETAIL.TIP_MATERIAL_KEY"], "course number description": ["TIP_SUBJECT_OFFERED.COURSE_NUMBER_DESC"], "subject title": ["TIP_SUBJECT_OFFERED.SUBJECT_TITLE"], "offering department name": ["TIP_SUBJECT_OFFERED.OFFER_DEPT_NAME"], "maximum number of enrolled students": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "Chemistry department": ["TIP_SUBJECT_OFFERED.OFFER_DEPT_NAME"]}

## 领域知识

["\"Chemistry\" is predicated by \"TABLE.OFFER_DEPT_NAME = 'Chemistry'\"", "\"Course 5\" is predicated by \"TABLE.OFFER_DEPT_NAME = 'Chemistry'\""]

## 子问题

[]
