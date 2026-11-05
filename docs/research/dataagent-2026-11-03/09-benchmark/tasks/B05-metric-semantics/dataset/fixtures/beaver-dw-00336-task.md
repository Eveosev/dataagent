# 查询任务（dw）

## 问题

For each department in the School of Engineering where the total number of students enrolled in courses offered by that department is greater than 50, what is the department name, the total number of enrolled students, the average of the total units for its courses that have a non-null subject title and total units greater than 0, the variance of the total units for those courses, and the number of unique subject titles offered by the department? Please list the department name, total enrollment, average units, units variance, and subject count in that order. Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_DEPARTMENT", "TIP_SUBJECT_OFFERED", "STUDENT_DEPARTMENT", "CIS_COURSE_CATALOG"]

## 连接键

[["SIS_DEPARTMENT.DEPARTMENT_CODE", "TIP_SUBJECT_OFFERED.OFFER_DEPT_CODE"], ["STUDENT_DEPARTMENT.DEPARTMENT_CODE", "TIP_SUBJECT_OFFERED.OFFER_DEPT_CODE"], ["CIS_COURSE_CATALOG.DEPARTMENT_CODE", "SIS_DEPARTMENT.DEPARTMENT_CODE"]]

## 列映射

{"department": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "School of Engineering": ["SIS_DEPARTMENT.SCHOOL_NAME"], "total number of students enrolled": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "courses offered by that department": ["TIP_SUBJECT_OFFERED.OFFER_DEPT_CODE", "SIS_DEPARTMENT.DEPARTMENT_CODE"], "total units": ["CIS_COURSE_CATALOG.TOTAL_UNITS"], "subject title": ["CIS_COURSE_CATALOG.SUBJECT_TITLE"], "number of unique subject titles": ["CIS_COURSE_CATALOG.SUBJECT_TITLE"], "department name": ["SIS_DEPARTMENT.DEPARTMENT_NAME"]}

## 领域知识

[]

## 表结构

### TIP_SUBJECT_OFFERED

- 列：["TIP_SUBJECT_OFFERED_KEY", "TERM_CODE", "IS_NO_COURSE_MATERIAL", "MASTER_COURSE_NUMBER", "MASTER_COURSE_NUMBER_SORT", "MASTER_COURSE_NUMBER_DESC", "MASTER_SUBJECT_ID", "MASTER_SUBJECT_ID_SORT", "COURSE_NUMBER", "COURSE_NUMBER_SORT", "COURSE_NUMBER_DESC", "SUBJECT_ID", "SUBJECT_ID_SORT", "SUBJECT_TITLE", "OFFER_DEPT_CODE", "OFFER_DEPT_NAME", "OFFER_SCHOOL_NAME", "RESPONSIBLE_FACULTY_NAME", "RESPONSIBLE_FACULTY_MIT_ID", "NUM_ENROLLED_STUDENTS", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "DATE"]
- 示例：[["0166830002017JA", "2017JA", NaN, "16", " 16", "Aeronautics and Astronautics", "16.683", "16.683", "16", " 16", "Aeronautics and Astronautics", "16.683", " 16.683", "Sem Aeronautics & Astronautics", "16", "Aeronautics and Astronautics", "Engineering", "Branch, Claude", 910358479.0, 0, "20-DEC-24"], ["21M3410002005FA", "2005FA", NaN, "21M", "21M", "Music and Theater Arts", "21M.341", "21M.341", "

### STUDENT_DEPARTMENT

- 列：["DEPARTMENT_CODE", "DEPARTMENT_NAME", "DEPARTMENT_FULL_NAME", "SCHOOL_CODE", "SCHOOL_NAME"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2"]
- 示例：[["21G", "Global Languages", "21G-Global Languages", "H", "Hum, Arts & Social Sciences"], ["22", "Nuclear Engineering", "22-Nuclear Engineering", "E", "Engineering"], ["21W", "Writing & Humanistic Studies", "21W-Writing & Humanistic Studies", "H", "Hum, Arts & Social Sciences"]]

## 子问题

["For each department, give the department name and calculate the total number of students enrolled in courses offered by that department in the School of Engineering, where the total number of enrolled students is greater than 50.", "For each department, provide the department name and calculate the average and variance of the total units for its courses that have a non-null subject title and total units greater than 0.", "For each department in the School of Engineering where the total number of students enrolled in courses offered by that department is greater than 50, what is the department name, the total number of enrolled students, the average of the total units for its courses that have a non-null subject title and total units greater than 0, and the variance of the total units for those courses? Please list the department name, total enrollment, average units, and units variance in that order."]
