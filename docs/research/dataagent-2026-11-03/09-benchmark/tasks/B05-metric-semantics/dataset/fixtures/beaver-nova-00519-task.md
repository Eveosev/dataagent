# 查询任务（nova）

## 问题

For host 'blaze8-12' in availability zone 'flare3', among the top 10 instance display names with the most completed migrations, show each display name’s completed migration count, total vCPUs, total memory (MB), whether any instance under that display name has an active (non-completed) migration, and for the matching instances list the instance UUID, VM state, memory (MB), vCPU count, instance extra record ID, the row number within each VM state ordered by UUID, the benchmark average vCPUs, and the vCPU category (HIGH_VCPU/LOW_VCPU/AVERAGE_VCPU). Do not return any rounded answers. Categorize each instance as 'HIGH_VCPU' (at least 50% above average), 'LOW_VCPU' (at least 50% below average), or 'AVERAGE_VCPU'.

## 库

nova

## 涉及表

["INSTANCES", "MIGRATIONS", "INSTANCE_EXTRA"]

## 连接键

[["INSTANCES.UUID", "MIGRATIONS.INSTANCE_UUID"], ["INSTANCES.UUID", "INSTANCE_EXTRA.INSTANCE_UUID"]]

## 列映射

{"instance display names": ["instances.display_name"], "migrations": ["migrations.id"], "migrations per instance": ["migrations.instance_uuid", "instances.uuid"], "migration status": ["migrations.status"], "availability zone \"flare3\"": ["INSTANCES.AVAILABILITY_ZONE"], "instance UUID": ["INSTANCES.UUID"], "display name": ["INSTANCES.DISPLAY_NAME"], "VM state": ["INSTANCES.VM_STATE"], "memory in MB": ["INSTANCES.MEMORY_MB"], "vCPU count": ["INSTANCES.VCPUS"], "instance extra record ID": ["INSTANCE_EXTRA.ID"], "row numbers within each VM state ordered by instance UUID": ["INSTANCES.VM_STATE", "INSTANCES.UUID"]}

## 领域知识

["Host \"blaze8-12\" is predicated by \"instances.host = 'blaze8-12'\""]

## 表结构

### MIGRATIONS

- 列：["CREATED_AT", "UPDATED_AT", "DELETED_AT", "ID", "SOURCE_COMPUTE", "DEST_COMPUTE", "DEST_HOST", "STATUS", "INSTANCE_UUID", "OLD_INSTANCE_TYPE_ID", "NEW_INSTANCE_TYPE_ID", "SOURCE_NODE", "DEST_NODE", "DELETED", "MIGRATION_TYPE", "HIDDEN", "MEMORY_TOTAL", "MEMORY_PROCESSED", "MEMORY_REMAINING", "DISK_TOTAL", "DISK_PROCESSED", "DISK_REMAINING"]
- 类型：["DATETIME", "DATETIME", "DATETIME", "INT", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(36)", "INT", "INT", "VARCHAR(255)", "VARCHAR(255)", "INT", "ENUM('MIGRATION','RESIZE','LIVE-MIGRATION','EVACUATION')", "TINYINT(1)", "BIGINT", "BIGINT", "BIGINT", "BIGINT", "BIGINT", "BIGINT"]
- 示例：[["2015-04-17T14:35:45", "2015-04-17T14:43:20", null, 147, "ether-60", "pivot-12", "10.121.94.149/8", "confirmed", "b8e529b0-87c9-4bb3-bdcb-9b83ceceea87", 74, 74, "ether-60.yahoo.ca.com", "pivot-12.yahoo.ca.com", 0, null, 0, null, null, null, null, null, null], ["2015-07-09T19:30:11", "2015-07-09T19:30:45", null, 175, "astro1-40", "glint-94", "10.228.204.94/8", "confirmed", "5494abf2-e134-4311-9fb

## 子问题

["List the top 10 instance display names with the highest number of migrations, counting migrations per instance, considering only migrations whose status is 'completed' and only instances hosted on 'blaze8-12'.", "For instances in availability zone \"flare3\" that are running on host \"blaze8-12\", list the instance UUID, display name, VM state, memory in MB, vCPU count, the instance extra record ID, and assign row numbers within each VM state ordered by instance UUID.", "From the top 10 instance display names with the highest number of completed migrations on host 'blaze8-12', show each display name, the completed migration count, the total vCPUs, the total memory (MB), and whether any of those instances have a non-completed migration (i.e., an active migration).", "For instances in availability zone \"flare3\" that are running on host \"blaze8-12\", list the instance UUID, display name, VM state, memory in MB, vCPU count, the instance extra record ID, and the row number within each VM state ordered by instance UUID; also compute the average vCPU count across these instances as a benchmark and categorize each instance as 'HIGH_VCPU' (at least 50% above average), 'LOW_VCPU' (at least 50% below average), or 'AVERAGE_VCPU'."]
