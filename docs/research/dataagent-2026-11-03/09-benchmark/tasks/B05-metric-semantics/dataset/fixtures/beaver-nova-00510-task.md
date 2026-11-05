# 查询任务（nova）

## 问题

For instances whose display name is "forge", return the instance UUID, hostname, cached network_info JSON, and the running sum of instance IDs within each VM state (ordered by instance ID), along with the total number of "forge" instances per VM state and the average of those per-state totals across all VM states; also include (as overall migration context) the source compute, destination compute, memory processed ratio, and the total count of completed migrations for instances in the 'shelved_offloaded' VM state where more than 75% of migration memory has been processed. Do not return any rounded answers.

## 库

nova

## 涉及表

["INSTANCES", "INSTANCE_INFO_CACHES", "MIGRATIONS"]

## 连接键

[["INSTANCES.UUID", "INSTANCE_INFO_CACHES.INSTANCE_UUID"], ["INSTANCES.UUID", "MIGRATIONS.INSTANCE_UUID"]]

## 列映射

{"display name": ["INSTANCES.DISPLAY_NAME"], "instance UUID": ["INSTANCES.UUID", "INSTANCE_INFO_CACHES.INSTANCE_UUID"], "hostname": ["INSTANCES.HOSTNAME"], "cached network_info JSON": ["INSTANCE_INFO_CACHES.NETWORK_INFO"], "VM state": ["INSTANCES.VM_STATE"], "instance ID": ["INSTANCES.ID"], "instance migrations": ["MIGRATIONS.INSTANCE_UUID"], "status 'completed'": ["MIGRATIONS.STATUS"], "instances": ["INSTANCES.UUID"], "VM state 'shelved_offloaded'": ["INSTANCES.VM_STATE"], "how many": ["MIGRATIONS.INSTANCE_UUID"]}

## 领域知识

[]

## 表结构

### INSTANCE_INFO_CACHES

- 列：["CREATED_AT", "UPDATED_AT", "DELETED_AT", "ID", "NETWORK_INFO", "INSTANCE_UUID", "DELETED"]
- 类型：["DATETIME", "DATETIME", "DATETIME", "INT", "TEXT", "VARCHAR(36)", "INT"]
- 示例：[["2014-10-15T01:44:40", "2023-01-31T14:45:53", null, 509070, "[{\"profile\": {}, \"ovs_interfaceid\": \"56df437d-4c88-4a82-9358-ec300c3a00ef\", \"preserve_on_delete\": false, \"network\": {\"bridge\": \"br-int\", \"subnets\": [{\"ips\": [{\"meta\": {}, \"version\": 4, \"type\": \"fixed\", \"floating_ips\": [], \"address\": \"10.252.74.89/8\"}], \"version\": 4, \"meta\": {\"dhcp_server\": \"10.151

## 子问题

["For instances whose display name is \"forge\", show the instance UUID, its hostname, the cached network_info JSON, and the running sum of the instance IDs within each VM state ordered by instance ID.", "How many instance migrations have status 'completed' for instances that are in the 'shelved_offloaded' VM state?", "For instances whose display name is \"forge\", show the instance UUID, its hostname, the cached network_info JSON, and the running sum of the instance IDs within each VM state ordered by instance ID, along with the total number of \"forge\" instances per VM state and the average of those per-state totals across all VM states.", "For completed instance migrations involving instances in the 'shelved_offloaded' VM state, list the instance UUID, instance hostname, migration source compute, destination compute, and the percentage of migration memory that has been processed (memory_processed divided by memory_total), keeping only rows where more than 75% of the migration memory has been processed."]
