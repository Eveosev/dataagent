# 查询任务（dw）

## 问题

For each administrative department and each subject offered by that department in the term '2019FA' with more than 0 enrolled students, list the department name, the average and standard deviation (using STDDEV only and never STDDEV_POP) of the office phone numbers of students in that department (considering only students who have a non-null office phone number), the subject title, the offer department name, the department full name, the number of enrolled students, the average number of enrolled students in a window of 2 preceding and 2 following rows grouped by the school code, and classify the subject as 'HIGH_ENROLLMENT' if the number of enrolled students is at least 10% greater than the window average, 'LOW_ENROLLMENT' if at least 10% less, or 'AVERAGE' otherwise. Order by department name and subject title. Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_ADMIN_DEPARTMENT", "MIT_STUDENT_DIRECTORY", "TIP_SUBJECT_OFFERED", "SIS_DEPARTMENT"]

## 连接键

[["MIT_STUDENT_DIRECTORY.DEPARTMENT", "SIS_ADMIN_DEPARTMENT.SIS_ADMIN_DEPARTMENT_CODE"], ["SIS_DEPARTMENT.DEPARTMENT_CODE", "TIP_SUBJECT_OFFERED.OFFER_DEPT_CODE"]]

## 列映射

{"administrative department": ["SIS_ADMIN_DEPARTMENT.SIS_ADMIN_DEPARTMENT_NAME", "SIS_ADMIN_DEPARTMENT.SIS_ADMIN_DEPARTMENT_CODE"], "department name": ["SIS_ADMIN_DEPARTMENT.SIS_ADMIN_DEPARTMENT_NAME"], "office phone numbers of students": ["MIT_STUDENT_DIRECTORY.OFFICE_PHONE"], "students in that department": ["MIT_STUDENT_DIRECTORY.DEPARTMENT"], "average of the office phone numbers": ["MIT_STUDENT_DIRECTORY.OFFICE_PHONE"], "standard deviation of the office phone numbers": ["MIT_STUDENT_DIRECTORY.OFFICE_PHONE"], "subject offered": ["TIP_SUBJECT_OFFERED.SUBJECT_TITLE", "TIP_SUBJECT_OFFERED.OFFER_DEPT_CODE"], "subject title": ["TIP_SUBJECT_OFFERED.SUBJECT_TITLE"], "offer department name": ["TIP_SUBJECT_OFFERED.OFFER_DEPT_NAME"], "department full name": ["SIS_DEPARTMENT.DEPARTMENT_FULL_NAME"], "number of enrolled students": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "enrolled students": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"], "term '2019FA'": ["TIP_SUBJECT_OFFERED.TERM_CODE"], "school code": ["SIS_DEPARTMENT.SCHOOL_CODE"], "window average of enrolled students": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS", "SIS_DEPARTMENT.SCHOOL_CODE"], "classify the subject as 'HIGH_ENROLLMENT', 'LOW_ENROLLMENT', or 'AVERAGE'": ["TIP_SUBJECT_OFFERED.NUM_ENROLLED_STUDENTS"]}

## 领域知识

[]

## 表结构

### MIT_STUDENT_DIRECTORY

- 列：["FIRST_NAME", "MIDDLE_NAME", "LAST_NAME", "FULL_NAME", "OFFICE_LOCATION", "OFFICE_PHONE", "EMAIL_ADDRESS", "DEPARTMENT", "DEPARTMENT_NAME", "STUDENT_YEAR", "FULL_NAME_UPPERCASE", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE"]
- 示例：[["Peter", NaN, "Best", "Best, Peter", NaN, NaN, "peterb9@worker.com", "6", "Electrical Eng & Computer Sci", "G", "BEST, PETER", "19-DEC-24"], ["Harriett", "H", "Wilkinson", "Wilkinson, Harriett H.", "36-798", NaN, "harriettw@worker.com", "6", "Electrical Eng & Computer Sci", "G", "WILKINSON, HARRIETT H.", "19-DEC-24"], ["Eliana", NaN, "Bolton", "Bolton, Eliana", NaN, NaN, "eb@worker.com", "4", "A

### TIP_SUBJECT_OFFERED

- 列：["TIP_SUBJECT_OFFERED_KEY", "TERM_CODE", "IS_NO_COURSE_MATERIAL", "MASTER_COURSE_NUMBER", "MASTER_COURSE_NUMBER_SORT", "MASTER_COURSE_NUMBER_DESC", "MASTER_SUBJECT_ID", "MASTER_SUBJECT_ID_SORT", "COURSE_NUMBER", "COURSE_NUMBER_SORT", "COURSE_NUMBER_DESC", "SUBJECT_ID", "SUBJECT_ID_SORT", "SUBJECT_TITLE", "OFFER_DEPT_CODE", "OFFER_DEPT_NAME", "OFFER_SCHOOL_NAME", "RESPONSIBLE_FACULTY_NAME", "RESPONSIBLE_FACULTY_MIT_ID", "NUM_ENROLLED_STUDENTS", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "NUMBER", "DATE"]
- 示例：[["0166830002017JA", "2017JA", NaN, "16", " 16", "Aeronautics and Astronautics", "16.683", "16.683", "16", " 16", "Aeronautics and Astronautics", "16.683", " 16.683", "Sem Aeronautics & Astronautics", "16", "Aeronautics and Astronautics", "Engineering", "Branch, Claude", 910358479.0, 0, "20-DEC-24"], ["21M3410002005FA", "2005FA", NaN, "21M", "21M", "Music and Theater Arts", "21M.341", "21M.341", "

## 子问题

["For each administrative department, give the department name and find the average and standard deviation of the office phone numbers of students in that department, considering only students who have a non-null office phone number.", "For subjects offered in the term '2019FA' with more than 0 enrolled students, show the subject title, offer department name, department full name, number of enrolled students, and the average number of enrolled students in a window of 2 preceding and 2 following rows grouped by the school code, ordered by the subject title.", "For each administrative department and each subject offered by that department in the term '2019FA' with more than 0 enrolled students, list the department name, the average and standard deviation of the office phone numbers of students in that department (considering only students who have a non-null office phone number), the subject title, the offer department name, the department full name, the number of enrolled students, and the average number of enrolled students in a window of 2 preceding and 2 following rows grouped by the school code, ordered by department name and subject title."]
