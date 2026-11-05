# 查询任务（dw）

## 问题

For each term and department, what is the term, department, and the variance of the reserve catalog keys for courses in that department and term where the material status is 'U'? Include subtotals for each term (the corresponding term field is 'SUBTOTAL') and a grand total across all terms (the corresponding term field is 'TOTAL'). Do not repeat the term if it is the same as the previous row. Sort the table by term and department. Do not return any rounded answers.

## 库

dw

## 涉及表

["LIBRARY_COURSE_INSTRUCTOR", "LIBRARY_RESERVE_MATRL_DETAIL"]

## 连接键

[["LIBRARY_COURSE_INSTRUCTOR.LIBRARY_COURSE_INSTRUCTOR_KEY", "LIBRARY_RESERVE_MATRL_DETAIL.LIBRARY_COURSE_INSTRUCTOR_KEY"]]

## 列映射

{"term": ["LIBRARY_RESERVE_MATRL_DETAIL.TERM_CODE"], "department": ["LIBRARY_COURSE_INSTRUCTOR.DEPARTMENT"], "variance of the reserve catalog keys": ["LIBRARY_RESERVE_MATRL_DETAIL.LIBRARY_RESERVE_CATALOG_KEY"], "material status is 'U'": ["LIBRARY_RESERVE_MATRL_DETAIL.LIBRARY_MATERIAL_STATUS_KEY"]}

## 领域知识

[]

## 子问题

["For each department, what is the name of the department and the variance of the reserve catalog keys for courses in that department where the material status is 'U'?"]
