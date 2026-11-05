# 查询任务（dw）

## 问题

For each department, what is the department code, department full name, school name, average, variance, and standard deviation (using STDDEV only and never STDDEV_POP) of the number of enrolled students in subjects offered by that department, considering only departments that grant degrees and excluding the Chemistry and Biology departments, and for each subject offered in the Mathematics department (Course 18) with more than 0 enrolled students, what is the department code, school name, department name, subject title, number of enrolled students, and the dense rank over the department code ordered by department code? Additionally, for each school, what is the total number of enrolled students in all subjects offered by departments in that school (considering only degree-granting departments and excluding Chemistry and Biology), and include a grand total for all schools. List all these columns in the result. Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_DEPARTMENT", "TIP_SUBJECT_OFFERED", "STUDENT_DEPARTMENT"]

## 连接键

[["SIS_DEPARTMENT.DEPARTMENT_CODE", "TIP_SUBJECT_OFFERED.OFFER_DEPT_CODE"], ["STUDENT_DEPARTMENT.DEPARTMENT_CODE", "TIP_SUBJECT_OFFERED.OFFER_DEPT_CODE"]]

## 列映射

{"department code": ["SIS_DEPARTMENT.DEPARTMENT_CODE"], "department full name": ["SIS_DEPARTMENT.DEPARTMENT_FULL_NAME"], "school name": ["SIS_DEPARTMENT.SCHOOL_NAME", "STUDENT_DEPARTMENT.SCHOOL_NAME"], "average of the number of enrolled students": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "variance of the number of enrolled students": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "standard deviation of the number of enrolled students": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "departments that grant degrees": ["SIS_DEPARTMENT.IS_DEGREE_GRANTING"], "excluding the Chemistry and Biology departments": ["SIS_DEPARTMENT.DEPARTMENT_CODE"], "Mathematics department (Course 18)": ["SIS_DEPARTMENT.DEPARTMENT_NAME", "SIS_DEPARTMENT.DEPARTMENT_CODE"], "subject title": ["TIP_SUBJECT_OFFERED.SUBJECT_TITLE"], "number of enrolled students": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "dense rank over the department code": ["SIS_DEPARTMENT.DEPARTMENT_CODE"], "subjects offered": ["TIP_SUBJECT_OFFERED.OFFER_DEPT_CODE"], "total number of enrolled students in all subjects offered by departments in that school": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS", "SIS_DEPARTMENT.SCHOOL_NAME"], "grand total for all schools": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"]}

## 领域知识

["\"degree-granting\" is predicated by \"TABLE.IS_DEGREE_GRANTING = 'Y'\"", "\"exclude organizations '101' and '103'\" is predicated by \"TABLE.ORGANIZATION_ID NOT IN ('101', '103')\"", "\"math\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"Chemistry\" is predicated by \"TABLE.DEPARTMENT_CODE = '5'\"", "\"Biology\" is predicated by \"TABLE.DEPARTMENT_CODE = '7'\"", "\"Course 18\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"Mathematics\" is predicated by \"TABLE.DEPARTMENT_CODE = '18'\""]

## 表结构

### TIP_SUBJECT_OFFERED

- 列：["TIP_SUBJECT_OFFERED_KEY", "TERM_CODE", "IS_NO_COURSE_MATERIAL", "MASTER_COURSE_NUMBER", "MASTER_COURSE_NUMBER_SORT", "MASTER_COURSE_NUMBER_DESC", "MASTER_SUBJECT_ID", "MASTER_SUBJECT_ID_SORT", "COURSE_NUMBER", "COURSE_NUMBER_SORT", "COURSE_NUMBER_DESC", "SUBJECT_ID", "SUBJECT_ID_SORT", "SUBJECT_TITLE", "OFFER_DEPT_CODE", "OFFER_DEPT_NAME", "OFFER_SCHOOL_NAME", "RESPONSIBLE_FACULTY_NAME", "RESPONSIBLE_FACULTY_MIT_ID", "NUM_ENROLLED_STUDENTS", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "DATE"]
- 示例：[["0166830002017JA", "2017JA", NaN, "16", " 16", "Aeronautics and Astronautics", "16.683", "16.683", "16", " 16", "Aeronautics and Astronautics", "16.683", " 16.683", "Sem Aeronautics & Astronautics", "16", "Aeronautics and Astronautics", "Engineering", "Branch, Claude", 910358479.0, 0, "20-DEC-24"], ["21M3410002005FA", "2005FA", NaN, "21M", "21M", "Music and Theater Arts", "21M.341", "21M.341", "

## 子问题

["For each department, what is the average, variance, and standard deviation of the number of enrolled students in subjects offered by that department, along with the department's full name and the school name, considering only departments that grant degrees and excluding the Chemistry and Biology departments?", "List the department name, subject title, number of enrolled students, and school name for each subject offered, along with dense ranks over the department code ordered by department code, for subjects with more than 0 enrolled students in departments that grant degrees, specifically for the Mathematics department (Course 18).", "For each department, what is the department code, department full name, school name, average, variance, and standard deviation of the number of enrolled students in subjects offered by that department, considering only departments that grant degrees and excluding the Chemistry and Biology departments, and for each subject offered in the Mathematics department (Course 18) with more than 0 enrolled students, what is the department code, school name, department name, subject title, number of enrolled students, and the dense rank over the department code ordered by department code? List all these columns in the result."]
