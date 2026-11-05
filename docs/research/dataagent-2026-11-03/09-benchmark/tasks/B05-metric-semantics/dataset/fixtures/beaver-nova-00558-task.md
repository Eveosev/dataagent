# 查询任务（nova）

## 问题

For instances in availability zone "flare3", for each system metadata key show the metadata key, the total number of distinct instances in flare3 that have that key, the average (across those instances) of the instance’s average memory remaining (in bytes) over completed migrations, the maximum memory-remaining standard deviation (using STDDEV only and never STDDEV_POP) (in bytes) observed among those instances, and the deviation of that key’s average-of-instance-average memory remaining from the overall average-of-instance-average memory remaining across all flare3 metadata keys. Do not return any rounded answers.

## 库

nova

## 涉及表

["INSTANCES", "MIGRATIONS", "INSTANCE_EXTRA", "INSTANCE_SYSTEM_METADATA"]

## 连接键

[["INSTANCES.UUID", "MIGRATIONS.INSTANCE_UUID"], ["INSTANCES.UUID", "INSTANCE_EXTRA.INSTANCE_UUID"], ["INSTANCES.UUID", "INSTANCE_SYSTEM_METADATA.INSTANCE_UUID"]]

## 列映射

{"instance display name": ["INSTANCES.DISPLAY_NAME"], "memory remaining (in bytes)": ["MIGRATIONS.MEMORY_REMAINING"], "completed migrations": ["MIGRATIONS.STATUS"], "availability zone \"flare3\"": ["INSTANCES.AVAILABILITY_ZONE"], "instance UUID": ["INSTANCES.UUID"], "display name": ["INSTANCES.DISPLAY_NAME"], "memory (MB)": ["INSTANCES.MEMORY_MB"], "vCPUs": ["INSTANCES.VCPUS"], "instance extra flavor JSON": ["INSTANCE_EXTRA.FLAVOR"], "system metadata key": ["INSTANCE_SYSTEM_METADATA.KEY"], "system metadata value": ["INSTANCE_SYSTEM_METADATA.VALUE"], "row numbers within each metadata key group": ["INSTANCE_SYSTEM_METADATA.KEY", "INSTANCES.UUID"]}

## 领域知识

[]

## 表结构

### MIGRATIONS

- 列：["CREATED_AT", "UPDATED_AT", "DELETED_AT", "ID", "SOURCE_COMPUTE", "DEST_COMPUTE", "DEST_HOST", "STATUS", "INSTANCE_UUID", "OLD_INSTANCE_TYPE_ID", "NEW_INSTANCE_TYPE_ID", "SOURCE_NODE", "DEST_NODE", "DELETED", "MIGRATION_TYPE", "HIDDEN", "MEMORY_TOTAL", "MEMORY_PROCESSED", "MEMORY_REMAINING", "DISK_TOTAL", "DISK_PROCESSED", "DISK_REMAINING"]
- 类型：["DATETIME", "DATETIME", "DATETIME", "INT", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(36)", "INT", "INT", "VARCHAR(255)", "VARCHAR(255)", "INT", "ENUM('MIGRATION','RESIZE','LIVE-MIGRATION','EVACUATION')", "TINYINT(1)", "BIGINT", "BIGINT", "BIGINT", "BIGINT", "BIGINT", "BIGINT"]
- 示例：[["2015-04-17T14:35:45", "2015-04-17T14:43:20", null, 147, "ether-60", "pivot-12", "10.121.94.149/8", "confirmed", "b8e529b0-87c9-4bb3-bdcb-9b83ceceea87", 74, 74, "ether-60.yahoo.ca.com", "pivot-12.yahoo.ca.com", 0, null, 0, null, null, null, null, null, null], ["2015-07-09T19:30:11", "2015-07-09T19:30:45", null, 175, "astro1-40", "glint-94", "10.228.204.94/8", "confirmed", "5494abf2-e134-4311-9fb

### INSTANCE_EXTRA

- 列：["CREATED_AT", "UPDATED_AT", "DELETED_AT", "DELETED", "ID", "INSTANCE_UUID", "NUMA_TOPOLOGY", "PCI_REQUESTS", "FLAVOR", "VCPU_MODEL", "MIGRATION_CONTEXT"]
- 类型：["DATETIME", "DATETIME", "DATETIME", "INT", "INT", "VARCHAR(36)", "TEXT", "TEXT", "TEXT", "TEXT", "TEXT"]
- 示例：[["2015-02-04T21:07:18", "2022-12-19T19:23:53", null, 0, 1505, "2b1448cc-926f-4660-a35f-fba2bd7ce54a", null, "[]", "{\"new\": null, \"old\": null, \"cur\": {\"nova_object.version\": \"1.1\", \"nova_object.changes\": [\"root_gb\", \"name\", \"ephemeral_gb\", \"memory_mb\", \"vcpus\", \"extra_specs\", \"swap\", \"rxtx_factor\", \"flavorid\", \"vcpu_weight\", \"id\"], \"nova_object.name\": \"Flavor\"

## 子问题

["For each instance display name, what are the average and standard deviation of the memory remaining (in bytes) across its completed migrations?", "For instances in availability zone \"flare3\", list the instance UUID, display name, memory (MB), vCPUs, the instance extra flavor JSON, the system metadata key and value, and assign row numbers within each metadata key group ordered by instance UUID.", "For instances in availability zone \"flare3\", for each system metadata key show the metadata key, the total number of distinct instances in flare3 that have that key, the average (across those instances) of the instance\u2019s average memory remaining (in bytes) over completed migrations, and the maximum memory-remaining standard deviation (in bytes) observed among those instances."]
