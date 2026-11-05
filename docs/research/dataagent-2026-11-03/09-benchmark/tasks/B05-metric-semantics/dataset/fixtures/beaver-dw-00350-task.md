# 查询任务（dw）

## 问题

For each academic year, list the academic year, the academic year description, the average, standard deviation (using STDDEV only and never STDDEV_POP), and geometric mean of the total units for subjects offered in regular terms, and for each academic year also include the department that offered the most subjects in regular terms along with the count of subjects from that department. Order the results by academic year. Do not return any rounded answers.

## 库

dw

## 涉及表

["ACADEMIC_TERMS", "COURSE_CATALOG_SUBJECT_OFFERED"]

## 连接键

[["ACADEMIC_TERMS.TERM_CODE", "COURSE_CATALOG_SUBJECT_OFFERED.EFFECTIVE_TERM_CODE"]]

## 列映射

{"academic year": ["ACADEMIC_TERMS.ACADEMIC_YEAR"], "academic year description": ["ACADEMIC_TERMS.ACADEMIC_YEAR_DESC"], "average of the total units": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS"], "standard deviation of the total units": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS"], "geometric mean of the total units": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS"], "subjects offered in regular terms": ["ACADEMIC_TERMS.IS_REGULAR_TERM", "COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS"], "department that offered the most subjects": ["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_NAME"], "count of subjects from that department": ["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_NAME"]}

## 领域知识

[]

## 子问题

["For each academic year, give the academic year description and find the average and standard deviation of the total units for subjects offered in terms that are regular terms.", "For each academic year, what is the academic year description and the geometric mean of the total units for all subjects offered in terms that are regular terms and have total units greater than zero?", "For each academic year, give the academic year, the academic year description, the average of the total units, the standard deviation of the total units, and the geometric mean of the total units for subjects offered in terms that are regular terms, where the geometric mean is calculated only for subjects with total units greater than zero. Present the results ordered by academic year."]
