# 查询任务（dw）

## 问题

From the top 10 departments with the highest total number of enrolled students in courses offered by the School of Engineering or School of Science, display each department's name, the total number of enrolled students, the school name, and the course with the highest enrollment in that department, along with the number of students enrolled in that course. Only include departments that grant degrees or the Department of Mathematics, and only consider departments where the total number of enrolled students is greater than 20. Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_COURSE_DESCRIPTION", "SIS_SUBJECT_CODE", "LIBRARY_SUBJECT_OFFERED"]

## 连接键

[["SIS_COURSE_DESCRIPTION.COURSE", "SIS_SUBJECT_CODE.COURSE_NUMBER"], ["LIBRARY_SUBJECT_OFFERED.COURSE_NUMBER", "SIS_SUBJECT_CODE.COURSE_NUMBER"]]

## 列映射

{"departments": ["SIS_COURSE_DESCRIPTION.DEPARTMENT_NAME"], "department's name": ["SIS_COURSE_DESCRIPTION.DEPARTMENT_NAME"], "total number of enrolled students": ["LIBRARY_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "school name": ["SIS_COURSE_DESCRIPTION.SCHOOL_NAME"], "course with the highest enrollment": ["LIBRARY_SUBJECT_OFFERED.COURSE_NUMBER"], "number of students enrolled in that course": ["LIBRARY_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "School of Engineering": ["SIS_COURSE_DESCRIPTION.SCHOOL_NAME"], "School of Science": ["SIS_COURSE_DESCRIPTION.SCHOOL_NAME"], "departments that grant degrees": ["SIS_COURSE_DESCRIPTION.IS_DEGREE_GRANTING"], "Department of Mathematics": ["SIS_COURSE_DESCRIPTION.DEPARTMENT_NAME"]}

## 领域知识

["\"degree-granting\" is predicated by \"TABLE.IS_DEGREE_GRANTING = 'Y'\"", "\"math\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"Course 18\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\""]

## 表结构

### SIS_SUBJECT_CODE

- 列：["COURSE_NUMBER", "SUBJECT_CODE", "SUBJECT_CODE_DESC", "DEPARTMENT_CODE", "DEPARTMENT_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE"]
- 示例：[["S0", "S0", NaN, NaN, NaN, NaN, NaN, "19-DEC-24"], ["OGE", "OGE", "Office of Graduate Education", "OGE", "Office of Graduate Education", "Y", "MIT, academic", "19-DEC-24"], ["MCH", "MCH", "Photography", "NIA", "Non-Institute-MFA/MCA", "Z", "Non-MIT", "19-DEC-24"]]

## 子问题

["For each department, give the department name and calculate the total number of enrolled students in courses offered by the department of Engineering or Science, where the total number of enrolled students is greater than 20, and restrict the results to departments that grant degrees and to the Department of Mathematics."]
