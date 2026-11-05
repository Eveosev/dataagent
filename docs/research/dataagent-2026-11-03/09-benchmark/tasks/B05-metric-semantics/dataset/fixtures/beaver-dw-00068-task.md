# 查询任务（dw）

## 问题

For each subject code where the department is degree granting and the department is Mathematics, show the subject code, subject code description, department name, school name, the average department budget code within each school, the maximum total units of any subject offered by that department in 2024 (excluding Physics), and the subject title for that subject, considering only subjects that are offered this year and have more than 9 total units, ordered by department name, subject code, and subject title. Do not return any rounded answers.

## 库

dw

## 涉及表

["SIS_DEPARTMENT", "SIS_SUBJECT_CODE", "COURSE_CATALOG_SUBJECT_OFFERED"]

## 连接键

[["SIS_DEPARTMENT.SCHOOL_CODE", "SIS_SUBJECT_CODE.SCHOOL_CODE"], ["COURSE_CATALOG_SUBJECT_OFFERED.DEPARTMENT_CODE", "SIS_DEPARTMENT.DEPARTMENT_CODE"]]

## 列映射

{"subject code": ["SIS_SUBJECT_CODE.SUBJECT_CODE"], "subject code description": ["SIS_SUBJECT_CODE.SUBJECT_CODE_DESC"], "department name": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "school name": ["SIS_SUBJECT_CODE.SCHOOL_NAME"], "average department budget code": ["SIS_DEPARTMENT.DEPT_BUDGET_CODE", "SIS_SUBJECT_CODE.SCHOOL_NAME"], "maximum total units": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS"], "subject title": ["COURSE_CATALOG_SUBJECT_OFFERED.SUBJECT_TITLE"], "degree granting": ["SIS_DEPARTMENT.IS_DEGREE_GRANTING"], "Mathematics": ["SIS_DEPARTMENT.DEPARTMENT_NAME"], "2024": ["COURSE_CATALOG_SUBJECT_OFFERED.ACADEMIC_YEAR"], "offered this year": ["COURSE_CATALOG_SUBJECT_OFFERED.IS_OFFERED_THIS_YEAR"], "more than 9 total units": ["COURSE_CATALOG_SUBJECT_OFFERED.TOTAL_UNITS"], "Physics (excluded)": ["SIS_DEPARTMENT.DEPARTMENT_NAME", "SIS_DEPARTMENT.DEPARTMENT_CODE"]}

## 领域知识

["\"math\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"Physics\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Physics'\"", "\"Course 18\" is predicated by \"TABLE.DEPARTMENT_NAME = 'Mathematics'\"", "\"Physics\" is predicated by \"TABLE.DEPARTMENT_CODE = '8'\""]

## 表结构

### SIS_SUBJECT_CODE

- 列：["COURSE_NUMBER", "SUBJECT_CODE", "SUBJECT_CODE_DESC", "DEPARTMENT_CODE", "DEPARTMENT_NAME", "SCHOOL_CODE", "SCHOOL_NAME", "WAREHOUSE_LOAD_DATE"]
- 类型：["VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "VARCHAR2", "DATE"]
- 示例：[["S0", "S0", NaN, NaN, NaN, NaN, NaN, "19-DEC-24"], ["OGE", "OGE", "Office of Graduate Education", "OGE", "Office of Graduate Education", "Y", "MIT, academic", "19-DEC-24"], ["MCH", "MCH", "Photography", "NIA", "Non-Institute-MFA/MCA", "Z", "Non-MIT", "19-DEC-24"]]

## 子问题

["For each subject code where the department is degree granting and the department is Mathematics, show the subject code, subject code description, department name, school name, and the average department budget code within each school, ordered by department name.", "For each department that is degree-granting, excluding the Physics department, what is the department name, the maximum total units of any subject offered by that department in 2024, and the subject title for that subject, considering only subjects that are offered this year and have more than 9 total units?"]
