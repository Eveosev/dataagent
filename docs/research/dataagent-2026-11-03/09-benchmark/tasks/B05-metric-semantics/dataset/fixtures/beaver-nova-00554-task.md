# 查询任务（nova）

## 问题

For each instance VM state and migration status, considering only migrations that are not hidden and only **active** migrations (i.e., migration status not in ('accepted', 'confirmed', 'reverted', 'error', 'failed', 'completed')), return the number of instances involved and the minimum total memory recorded for the migration. Do not return any rounded answers.

## 库

nova

## 涉及表

["INSTANCES", "MIGRATIONS"]

## 连接键

[["INSTANCES.UUID", "MIGRATIONS.INSTANCE_UUID"]]

## 列映射

{"instance VM state": ["INSTANCES.VM_STATE"], "migration status": ["MIGRATIONS.STATUS"], "migrations that are not hidden": ["MIGRATIONS.HIDDEN"], "number of instances involved": ["INSTANCES.ID"], "minimum total memory recorded for the migration": ["MIGRATIONS.MEMORY_TOTAL"]}

## 领域知识

["\"Active migrations\" is predicated by \"migrations.status NOT IN ('accepted', 'confirmed', 'reverted', 'error', 'failed', 'completed')\""]

## 子问题

[]
