# 查询任务（dw）

## 问题

For each student in the Electrical Engineering and Computer Science department whose MIT ID is between 921145998 and 999756146 or whose department number is at least 4, and whose department number is between 4 and 6, and whose department number is 6, what are their minimum MIT ID, average department number, and email address? Do not return any rounded answers.

## 库

dw

## 涉及表

["SE_PERSON", "MIT_STUDENT_DIRECTORY"]

## 连接键

[["MIT_STUDENT_DIRECTORY.FULL_NAME", "SE_PERSON.FULL_NAME"]]

## 列映射

{"student": ["SE_PERSON.FULL_NAME", "MIT_STUDENT_DIRECTORY.FULL_NAME"], "Electrical Engineering and Computer Science department": ["SE_PERSON.ORGANIZATION"], "MIT ID": ["SE_PERSON.MIT_ID"], "department number": ["MIT_STUDENT_DIRECTORY.DEPARTMENT"], "minimum MIT ID": ["SE_PERSON.MIT_ID"], "average department number": ["MIT_STUDENT_DIRECTORY.DEPARTMENT"], "email address": ["MIT_STUDENT_DIRECTORY.EMAIL_ADDRESS"]}

## 领域知识

["\"Electrical Engineering and Computer Science department\" is predicated by \"TABLE.ORGANIZATION = 'Electrical Engineering-Computer Science'\"", "\"Electrical Engineering and Computer Science\" is predicated by \"TABLE.DEPARTMENT = '6'\""]

## 子问题

["What are the minimum MIT ID and average department number for each student, where MIT IDs are between 921145998 and 999756146 or department numbers are at least 4, and department numbers are between 4 and 6, and the student is in the Electrical Engineering and Computer Science department?"]
