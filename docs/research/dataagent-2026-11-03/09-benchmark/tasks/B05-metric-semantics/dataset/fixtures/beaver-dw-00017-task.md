# 查询任务（dw）

## 问题

For each Mathematics department subject offered in the term '2019FA' that has course materials, list the subject title, number of enrolled students, responsible faculty name, the department name, and the school name. Also, include a dense rank over the department name, ordered by department name. Do not repeat the department name if it is the same as the previous row. Sort the table by department name and subject title. Do not return any rounded answers.

## 库

dw

## 涉及表

["TIP_SUBJECT_OFFERED", "SIS_DEPARTMENT", "SIS_COURSE_DESCRIPTION"]

## 连接键

[["SIS_DEPARTMENT.DEPARTMENT_CODE", "TIP_SUBJECT_OFFERED.OFFER_DEPT_CODE"], ["SIS_COURSE_DESCRIPTION.DEPARTMENT", "SIS_DEPARTMENT.DEPARTMENT_CODE"]]

## 列映射

{"Mathematics department": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "subject offered": ["TIP_SUBJECT_OFFERED.SUBJECT_TITLE"], "term '2019FA'": ["TIP_SUBJECT_OFFERED.TERM_CODE"], "course materials": ["TIP_SUBJECT_OFFERED.IS_NO_COURSE_MATERIAL"], "number of enrolled students": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "responsible faculty name": ["TIP_SUBJECT_OFFERED.RESPONSIBLE_FACULTY_NAME"], "department name": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "school name": ["SIS_DEPARTMENT.SCHOOL_NAME"]}

## 领域知识

["\"math\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"courses with materials\" is predicated by \"TIP_SUBJECT_OFFERED.IS_NO_COURSE_MATERIAL = 'N'\"", "\"Course 18\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\""]

## 表结构

### SIS_DEPARTMENT

- 列：["DEPARTMENT_CODE", "DEPARTMENT_NAME", "DEPARTMENT_FULL_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "DEPT_BUDGET_CODE", "IS_DEGREE_GRANTING", "DEPT_NAME_IN_COMMENCEMENT_BK", "SCHOOL_NAME_IN_COMMENCEMENT_BK", "DEPARTMENT_NAME_HISTORY", "DEPARTMENT_LAST_ACTIVITY_DATE", "DLC_KEY", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE", "VARCHAR2", "DATE"]
- 示例：[["HPM", "Health Policy & Management", "HPM-Health Policy & Management", "T", "Whitaker Coll of HST;  HST", 160000.0, "Y", NaN, "Whitaker College of Health Sciences and Technology", NaN, "17-FEB-94", "D_WHIT", "19-DEC-24"], ["NIE", "Non-Institute Exchange Student", "NIE-Non-Institute Exchange Student", "Z", "Non-MIT", NaN, "N", NaN, NaN, NaN, "12-JUL-95", "D_CROSS_REG", "19-DEC-24"], ["WHIT", "Whi

## 子问题

["List the subject title, number of enrolled students, and the responsible faculty name for each subject offered by the Mathematics department (Course 18) in the term '2019FA', where the subject has course materials, along with a dense rank over the department name, ordered by department name."]
