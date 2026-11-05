# 查询任务（nova）

## 问题

For confirmed migrations and for instances whose display name is 'forge', return a combined report (joined by instance display name) that includes the migration status, source and destination compute hosts, the instance display name and network_info, the dense rank within each migration status plus the overall average dense-rank across confirmed migrations and each row’s deviation from that average; and also includes the forge instance UUID, VM state, memory (MB), vCPUs, instance-extra ID and created timestamp, cached network_info JSON, the minimum instance-extra ID in a 3-preceding/1-following window ordered by memory, and whether the instance has any deleted instance-extra record. Do not return any rounded answers.

## 库

nova

## 涉及表

["MIGRATIONS", "INSTANCES", "INSTANCE_INFO_CACHES", "INSTANCE_EXTRA"]

## 连接键

[["INSTANCES.UUID", "MIGRATIONS.INSTANCE_UUID"], ["INSTANCES.UUID", "INSTANCE_INFO_CACHES.INSTANCE_UUID"], ["INSTANCES.UUID", "INSTANCE_EXTRA.INSTANCE_UUID"]]

## 列映射

{"confirmed migrations": ["MIGRATIONS.STATUS"], "migration status": ["MIGRATIONS.STATUS"], "source compute host": ["MIGRATIONS.SOURCE_COMPUTE"], "destination compute host": ["MIGRATIONS.DEST_COMPUTE"], "instance display name": ["INSTANCES.DISPLAY_NAME"], "instance network_info": ["INSTANCE_INFO_CACHES.NETWORK_INFO"], "dense rank within each migration status": ["MIGRATIONS.STATUS"], "display name": ["INSTANCES.DISPLAY_NAME"], "instance UUID": ["INSTANCES.UUID"], "VM state": ["INSTANCES.VM_STATE"], "memory in MB": ["INSTANCES.MEMORY_MB"], "vCPUs": ["INSTANCES.VCPUS"], "instance-extra record ID": ["INSTANCE_EXTRA.ID"], "instance-extra created timestamp": ["INSTANCE_EXTRA.CREATED_AT"], "cached network_info JSON": ["INSTANCE_INFO_CACHES.NETWORK_INFO"], "minimum instance-extra ID (window)": ["INSTANCE_EXTRA.ID"]}

## 领域知识

[]

## 表结构

### INSTANCES

- 列：["CREATED_AT", "UPDATED_AT", "DELETED_AT", "ID", "INTERNAL_ID", "USER_ID", "PROJECT_ID", "IMAGE_REF", "KERNEL_ID", "RAMDISK_ID", "LAUNCH_INDEX", "KEY_NAME", "KEY_DATA", "POWER_STATE", "VM_STATE", "MEMORY_MB", "VCPUS", "HOSTNAME", "HOST", "USER_DATA", "RESERVATION_ID", "SCHEDULED_AT", "LAUNCHED_AT", "TERMINATED_AT", "DISPLAY_NAME", "DISPLAY_DESCRIPTION", "AVAILABILITY_ZONE", "LOCKED", "OS_TYPE", "LAUNCHED_ON", "INSTANCE_TYPE_ID", "VM_MODE", "UUID", "ARCHITECTURE", "ROOT_DEVICE_NAME", "ACCESS_IP_V4", "ACCESS_IP_V6", "CONFIG_DRIVE", "TASK_STATE", "DEFAULT_EPHEMERAL_DEVICE", "DEFAULT_SWAP_DEVICE", "PROGRESS", "AUTO_DISK_CONFIG", "SHUTDOWN_TERMINATE", "DISABLE_TERMINATE", "ROOT_GB", "EPHEMERAL_GB", "CELL_NAME", "NODE", "DELETED", "LOCKED_BY", "CLEANED", "EPHEMERAL_KEY_UUID"]
- 类型：["DATETIME", "DATETIME", "DATETIME", "INT", "INT", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)", "INT", "VARCHAR(255)", "TEXT", "INT", "VARCHAR(255)", "INT", "INT", "VARCHAR(255)", "VARCHAR(255)", "TEXT", "VARCHAR(255)", "DATETIME", "DATETIME", "DATETIME", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)", "TINYINT(1)", "VARCHAR(255)", "TEXT", "INT", "VARCHAR(255)", "VARCHAR(36)", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(39)", "VARCHAR(39)", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)", "VARCHAR(255)", "INT", "TINYINT(1)", "TINYINT(1)", "TINYINT(1)", "INT", "INT", "VARCHAR(255)", "VARCHAR(255)", "INT", "ENUM('OWNER','ADMIN')", "INT", "VARCHAR(36)"]
- 示例：[["2014-10-15T01:44:40", "2023-01-31T16:05:25", null, 509070, null, "be417436c0174498bf721e849e119555", "d1fe1eee802541b8bd5ed61cd3a05d77", "e533ca5e-1dc0-4b4d-8023-bc15624a5e63", null, null, 0, "solar_plasm", "2f6cbc63d7af29b70f7d341260041795", 4, "shelved_offloaded", 32768, 8, "glyph-helix-nexus", "", "replaced_user_data.509070", "r-m3yx01v5", "2014-10-15T01:44:41", "2016-09-26T17:42:44", null, 

### INSTANCE_INFO_CACHES

- 列：["CREATED_AT", "UPDATED_AT", "DELETED_AT", "ID", "NETWORK_INFO", "INSTANCE_UUID", "DELETED"]
- 类型：["DATETIME", "DATETIME", "DATETIME", "INT", "TEXT", "VARCHAR(36)", "INT"]
- 示例：[["2014-10-15T01:44:40", "2023-01-31T14:45:53", null, 509070, "[{\"profile\": {}, \"ovs_interfaceid\": \"56df437d-4c88-4a82-9358-ec300c3a00ef\", \"preserve_on_delete\": false, \"network\": {\"bridge\": \"br-int\", \"subnets\": [{\"ips\": [{\"meta\": {}, \"version\": 4, \"type\": \"fixed\", \"floating_ips\": [], \"address\": \"10.252.74.89/8\"}], \"version\": 4, \"meta\": {\"dhcp_server\": \"10.151

## 子问题

["For confirmed migrations, show the migration status, source compute host, destination compute host, the instance display name, and the instance network_info, along with a dense rank within each migration status ordered by that status.", "For instances whose display name is 'forge', show the instance UUID, display name, VM state, memory in MB, vCPUs, the instance-extra record ID, the instance-extra created timestamp, the cached network_info JSON, and the minimum instance-extra ID in a window of 3 preceding and 1 following row ordered by instance memory (MB).", "For confirmed migrations, list the migration status, source compute host, destination compute host, instance display name, and instance network_info, along with the dense rank within each migration status ordered by that status; also include the overall average dense-rank value across these confirmed migrations and the deviation of each row\u2019s dense rank from that average.", "For instances whose display name is 'forge', list the instance UUID, display name, VM state, memory in MB, vCPUs, the instance-extra record ID, the instance-extra created timestamp, the cached network_info JSON, and the minimum instance-extra ID in a window of 3 preceding and 1 following row ordered by instance memory (MB). Also include, for each instance, whether it has any instance-extra record marked as deleted."]
