# 查询任务（dw）

## 问题

For each subject, what is the highest variance of the record count for TIP materials associated with that subject across all terms, considering only records where the library material status is 'U' and the TIP material status is 'RQ'? Do not return any rounded answers.

## 库

dw

## 涉及表

["LIBRARY_RESERVE_MATRL_DETAIL", "TIP_DETAIL"]

## 连接键

[["LIBRARY_RESERVE_MATRL_DETAIL.SUBJECT_ID", "TIP_DETAIL.SUBJECT_ID"]]

## 列映射

{"subject": ["LIBRARY_RESERVE_MATRL_DETAIL.SUBJECT_ID", "TIP_DETAIL.SUBJECT_ID"], "variance of the record count": ["TIP_DETAIL.RECORD_COUNT"], "TIP materials": ["TIP_DETAIL.TIP_MATERIAL_STATUS_KEY"], "terms": ["TIP_DETAIL.TERM_CODE"], "library material status is 'U'": ["LIBRARY_RESERVE_MATRL_DETAIL.LIBRARY_MATERIAL_STATUS_KEY"], "TIP material status is 'RQ'": ["TIP_DETAIL.TIP_MATERIAL_STATUS_KEY"]}

## 领域知识

[]

## 子问题

["For each subject, what is the variance of the record count for TIP materials associated with that subject, considering only records where the library material status is 'U' and the TIP material status is 'RQ'?"]
